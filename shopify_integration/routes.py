import os
import json
import boto3
import hmac
import hashlib
import base64
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, verify_hmac, register_webhooks
from shared.utils import generate_state_token, validate_state_token, compute_data_hash, get_previous_hash
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
from digitalocean_integration.utils import has_data_changed, upload_to_spaces
import httpx
import time

router = APIRouter()
token_storage = TokenStorage()
session_storage = SessionStorage()

@router.get("/{shop_name}/login")
async def start_oauth(request: Request, shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_products,write_inventory"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify app config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    session_id = request.cookies.get("session_id")
    new_session_id, user_uuid = session_storage.get_or_create_session(session_id)

    state = generate_state_token(extra_data=user_uuid)

    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&response_type=code&state={state}"
    )
    response = RedirectResponse(auth_url)
    response.set_cookie(key="session_id", value=new_session_id, httponly=True, max_age=3600)
    return response

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")
    state = request.query_params.get("state")

    if not code or not shop or not state:
        raise HTTPException(status_code=400, detail="Missing code, shop, or state parameter")

    user_uuid = validate_state_token(state)
    if not user_uuid:
        raise HTTPException(status_code=400, detail="Invalid UUID in state token")

    session_id = request.cookies.get("session_id")
    session_storage.verify_session(session_id, expected_uuid=user_uuid)

    new_session_id, user_uuid = session_storage.get_or_create_session(session_id)

    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    shop_key = shop.replace('.', '_')
    token_storage.store_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}", token_data["access_token"], type="token")
    token_storage.store_token(f"USER_UUID_{shop_key}", user_uuid, type="uuid")

    webhook_test_result = None
    try:
        await register_webhooks(shop, token_data["access_token"])
        test_payload = {"product": {"id": 12345, "title": "Test Product"}}
        secret = os.getenv("SHOPIFY_API_SECRET")
        hmac_signature = base64.b64encode(
            hmac.new(secret.encode(), json.dumps(test_payload).encode(), hashlib.sha256).digest()
        ).decode()
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('SHOPIFY_WEBHOOK_ADDRESS', 'http://localhost:5000/shopify/webhook')}",
                headers={
                    "X-Shopify-Topic": "products/update",
                    "X-Shopify-Shop-Domain": shop,
                    "X-Shopify-Hmac-Sha256": hmac_signature,
                    "Content-Type": "application/json"
                },
                data=json.dumps(test_payload)
            )
        result = {
            "entity_id": shop,
            "result": {
                "status": "success" if response.status_code == 200 else "failed",
                "message": "Products/update webhook test succeeded" if response.status_code == 200 else "Products/update webhook test failed",
                "attempt_timestamp": int(time.time() * 1000)
            }
        }
        if start_time:
            result["result"]["response_time_ms"] = int((time.time() - start_time) * 1000)
        if response.status_code != 200:
            result["result"].update({
                "http_status_code": response.status_code,
                "response_body": response.text,
                "request_payload": json.dumps(test_payload),
                "server_response_headers": dict(response.headers)
            })
        webhook_test_result = result
        print(f"Webhook test result for {shop}: {webhook_test_result}")
    except Exception as e:
        result = {
            "entity_id": shop,
            "result": {
                "status": "failed",
                "message": f"Webhook setup failed: {str(e)}",
                "attempt_timestamp": int(time.time() * 1000)
            }
        }
        result["result"]["error_details"] = str(e)
        if test_payload:
            result["result"]["data_size_bytes"] = len(json.dumps(test_payload).encode())
        webhook_test_result = result
        print(f"Webhook setup failed for {shop}: {str(e)}")

    data = await get_shopify_data(token_data["access_token"], shop)

    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
        aws_access_key_id=os.getenv("SPACES_API_KEY"),
        aws_secret_access_key=os.getenv("SPACES_API_SECRET")
    )

    start_time = time.time()
    has_changed = has_data_changed(data, f"users/{user_uuid}/shopify/data.json", s3_client)
    result = {
        "entity_id": shop,
        "result": {
            "status": "skipped" if not has_changed else "failed",
            "message": "No changes detected, upload skipped" if not has_changed else "Upload verification failed",
            "attempt_timestamp": int(time.time() * 1000)
        }
    }
    if start_time:
        result["result"]["response_time_ms"] = int((time.time() - start_time) * 1000)
    previous_hash = get_previous_hash(s3_client, os.getenv("SPACES_BUCKET"), f"users/{user_uuid}/shopify/data.json")
    if previous_hash:
        result["result"]["previous_hash"] = previous_hash
    if has_changed:
        try:
            upload_to_spaces(data, f"users/{user_uuid}/shopify/data.json", s3_client)
            result["result"].update({
                "status": "success",
                "message": "Data successfully uploaded to Spaces",
                "upload_timestamp": int(time.time() * 1000),
                "bytes_uploaded": len(json.dumps(data).encode()),
                "data_hash": compute_data_hash(data),
                "upload_duration_ms": int((time.time() - start_time) * 1000)
            })
        except Exception as e:
            result["result"].update({
                "status": "failed",
                "message": f"Upload verification failed: {str(e)}",
                "error_details": str(e),
                "data_size_bytes": len(json.dumps(data).encode()) if data else 0
            })
    upload_status_result = result
    print(f"Upload status result for {shop}: {upload_status_result}")

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "data": data,
        "webhook_test": webhook_test_result,
        "upload_status": upload_status_result
    })
    response.set_cookie(key="session_id", value=new_session_id, httponly=True, max_age=3600)
    return response

@router.post("/webhook")
async def shopify_webhook(request: Request):
    if not await verify_hmac(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop domain")

    shop_key = shop.replace('.', '_')
    access_token = token_storage.get_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}")
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token not found")

    user_uuid = token_storage.get_token(f"USER_UUID_{shop_key}")
    if not user_uuid:
        raise HTTPException(status_code=500, detail="User UUID not found for shop")

    payload = await request.json()
    event_type = request.headers.get("X-Shopify-Topic")
    print(f"Received {event_type} event from {shop}: {payload}")

    try:
        data = await get_shopify_data(access_token, shop)
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=os.getenv("SPACES_REGION", "nyc3"),
            endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv("SPACES_API_KEY"),
            aws_secret_access_key=os.getenv("SPACES_API_SECRET")
        )
        spaces_key = f"users/{user_uuid}/shopify/data.json"
        if has_data_changed(data, spaces_key, s3_client):
            upload_to_spaces(data, spaces_key, s3_client)
            print(f"Updated data in Spaces for {shop} via {event_type}")
    except Exception as e:
        print(f"Failed to update Spaces for {shop} via {event_type}: {str(e)}")

    return {"status": "success"}