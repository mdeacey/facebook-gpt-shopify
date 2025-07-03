import os
import json
import boto3
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, verify_hmac, register_webhooks, poll_shopify_data
from shared.utils import generate_state_token, validate_state_token
from digitalocean_integration.utils import has_data_changed, upload_to_spaces
import hmac
import hashlib
import base64
import httpx

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_products,write_inventory"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify app config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    state = generate_state_token()

    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&response_type=code&state={state}"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")
    state = request.query_params.get("state")

    if not code or not shop or not state:
        raise HTTPException(status_code=400, detail="Missing code, shop, or state parameter")

    validate_state_token(state)

    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    os.environ[f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"] = token_data["access_token"]

    webhook_status = "success"
    try:
        await register_webhooks(shop, token_data["access_token"])
    except Exception as e:
        webhook_status = "failed"
        print(f"Webhook registration failed for {shop}: {str(e)}")

    shopify_data = await get_shopify_data(token_data["access_token"], shop)

    webhook_test_result = {"status": "failed", "message": "Webhook test not run"}
    if webhook_status == "success":
        test_payload = {"product": {"id": 12345, "title": "Test Product"}}
        secret = os.getenv("SHOPIFY_API_SECRET")
        hmac_signature = base64.b64encode(
            hmac.new(secret.encode(), json.dumps(test_payload).encode(), hashlib.sha256).digest()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:5000/shopify/webhook",
                headers={
                    "X-Shopify-Topic": "products/update",
                    "X-Shopify-Shop-Domain": shop,
                    "X-Shopify-Hmac-Sha256": hmac_signature,
                    "Content-Type": "application/json"
                },
                data=json.dumps(test_payload)
            )
            webhook_test_result = response.json() if response.status_code == 200 else {
                "status": "failed",
                "message": response.text
            }
        print(f"Webhook test result for {shop}: {webhook_test_result}")

    access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
    access_token = os.getenv(access_token_key)
    polling_test_result = await poll_shopify_data(access_token, shop)
    print(f"Polling test result for {shop}: {polling_test_result}")

    upload_status = "failed"
    if (
        webhook_test_result.get("status") == "success"
        and polling_test_result.get("status") == "success"
    ):
        try:
            session = boto3.session.Session()
            s3_client = session.client(
                "s3",
                region_name=os.getenv("SPACES_REGION", "nyc3"),
                endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
                aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
            )
            spaces_key = f"{shop}/shopify_data.json"
            if has_data_changed(shopify_data, spaces_key, s3_client):
                upload_to_spaces(shopify_data, spaces_key, s3_client)
                print(f"Uploaded data to Spaces for {shop}")
            else:
                print(f"No upload needed for {shop}: Data unchanged")
            upload_status = "success"
        except Exception as e:
            print(f"Failed to upload to Spaces for {shop}: {str(e)}")
            upload_status = "failed"

    return JSONResponse(content={
        "token_data": token_data,
        "shopify_data": shopify_data,
        "webhook_status": webhook_status,
        "webhook_test": webhook_test_result,
        "polling_test": polling_test_result,
        "upload_status": upload_status
    })

@router.post("/webhook")
async def shopify_webhook(request: Request):
    if not await verify_hmac(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop domain")

    access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
    access_token = os.getenv(access_token_key)
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token not found")

    payload = await request.json()
    event_type = request.headers.get("X-Shopify-Topic")
    print(f"Received {event_type} event from {shop}: {payload}")

    try:
        shopify_data = await get_shopify_data(access_token, shop)
        spaces_key = f"{shop}/shopify_data.json"
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=os.getenv("SPACES_REGION", "nyc3"),
            endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
        )
        if has_data_changed(shopify_data, spaces_key, s3_client):
            upload_to_spaces(shopify_data, spaces_key, s3_client)
            print(f"Updated data in Spaces for {shop} via {event_type}")
        else:
            print(f"No update needed in Spaces for {shop} via {event_type}: Data unchanged")
    except Exception as e:
        print(f"Failed to update Spaces for {shop} via {event_type}: {str(e)}")

    return {"status": "success"}