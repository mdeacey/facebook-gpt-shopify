import logging
import json
import boto3
import hmac
import hashlib
import base64
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import get_shopify_data, register_webhooks
from shared.utils import generate_state_token, validate_state_token, compute_data_hash, get_previous_hash, check_endpoint_accessibility, exchange_code_for_token, verify_hmac
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
from shared.config import config
from shared.models import ShopifyWebhookPayload
from integrations.digitalocean.spaces import has_data_changed, upload_to_spaces
from msgspec.json import decode
from msgspec.structs import asdict
import time

logger = logging.getLogger(__name__)

router = APIRouter()
token_storage = TokenStorage()
session_storage = SessionStorage()

@router.get("/{shop_name}/login")
async def start_oauth(request: Request, shop_name: str):
    request_id = request.state.request_id
    logger.info(f"[{request_id}] Starting Shopify OAuth for shop {shop_name}")
    
    client_id = config.shopify_api_key
    redirect_uri = config.shopify_redirect_uri
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_products,write_inventory"

    if not client_id or not redirect_uri:
        logger.error(f"[{request_id}] Shopify app config missing")
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
    logger.info(f"[{request_id}] Redirecting to Shopify OAuth URL")
    return response

@router.get("/callback")
async def oauth_callback(request: Request):
    request_id = request.state.request_id
    logger.info(f"[{request_id}] Shopify OAuth callback started")
    
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")
    state = request.query_params.get("state")

    if not code or not shop or not state:
        logger.error(f"[{request_id}] Missing code, shop, or state parameter")
        raise HTTPException(status_code=400, detail="Missing code, shop, or state parameter")

    user_uuid = validate_state_token(state)
    if not user_uuid:
        logger.error(f"[{request_id}] Invalid UUID in state token")
        raise HTTPException(status_code=400, detail="Invalid UUID in state token")

    session_id = request.cookies.get("session_id")
    session_storage.verify_session(session_id, expected_uuid=user_uuid)

    new_session_id, user_uuid = session_storage.get_or_create_session(session_id)

    if not config.shopify_api_key:
        logger.error(f"[{request_id}] SHOPIFY_API_KEY is not set")
        raise HTTPException(status_code=500, detail="SHOPIFY_API_KEY is not set")
    if not config.shopify_api_secret:
        logger.error(f"[{request_id}] SHOPIFY_API_SECRET is not set")
        raise HTTPException(status_code=500, detail="SHOPIFY_API_SECRET is not set")
    if not config.shopify_redirect_uri:
        logger.error(f"[{request_id}] SHOPIFY_REDIRECT_URI is not set")
        raise HTTPException(status_code=500, detail="SHOPIFY_REDIRECT_URI is not set")
    logger.info(f"[{request_id}] Shopify OAuth callback: shop={shop}, redirect_uri={config.shopify_redirect_uri}")

    token_data = await exchange_code_for_token(
        code=code,
        client_id=config.shopify_api_key,
        client_secret=config.shopify_api_secret,
        redirect_uri=config.shopify_redirect_uri,
        token_url=f"https://{shop}/admin/oauth/access_token",
        method="POST"
    )
    if "access_token" not in token_data:
        logger.error(f"[{request_id}] Token exchange failed: {token_data}")
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    shop_key = shop.replace('.', '_')
    token_storage.store_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}", token_data["access_token"], type="token")
    token_storage.store_token(f"USER_UUID_{shop_key}", user_uuid, type="uuid")

    webhook_test_results = []
    upload_status_results = []

    webhook_url = config.shopify_webhook_address
    is_accessible, accessibility_message = await check_endpoint_accessibility(
        endpoint=webhook_url,
        endpoint_type="webhook",
        method="GET"
    )
    if not is_accessible:
        logger.error(f"[{request_id}] Shopify webhook endpoint check failed: {accessibility_message}")
        webhook_test_results.append({
            "entity_id": "all",
            "result": {
                "status": "failed",
                "message": accessibility_message,
                "attempt_timestamp": int(time.time() * 1000)
            }
        })

    data = await get_shopify_data(token_data["access_token"], shop, request_id=request_id)
    entities = [{"id": shop}]

    async with httpx.AsyncClient() as client:
        for entity in entities:
            shop_id = entity["id"]
            try:
                await register_webhooks(shop_id, token_data["access_token"], request_id=request_id)
                test_payload = {"product": {"id": 12345, "title": "Test Product"}}
                secret = config.shopify_api_secret
                hmac_signature = base64.b64encode(
                    hmac.new(secret.encode(), json.dumps(test_payload).encode(), hashlib.sha256).digest()
                ).decode()
                logger.info(f"[{request_id}] Sending products/update webhook test to {webhook_url} for {shop_id}")
                start_time = time.time()
                response = await client.post(
                    webhook_url,
                    headers={
                        "X-Shopify-Topic": "products/update",
                        "X-Shopify-Shop-Domain": shop_id,
                        "X-Shopify-Hmac-Sha256": hmac_signature,
                        "Content-Type": "application/json",
                        "X-Request-ID": request_id
                    },
                    data=json.dumps(test_payload)
                )
                logger.info(f"[{request_id}] Webhook test response for {shop_id}: status {response.status_code}, body {response.text}")
                result = {
                    "entity_id": shop_id,
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
                        "server_response_headers": dict(response.headers),
                        "data_size_bytes": len(json.dumps(test_payload).encode())
                    })
                webhook_test_results.append(result)
                logger.info(f"[{request_id}] Webhook test result for {shop_id}: {result}")
            except Exception as e:
                result = {
                    "entity_id": shop_id,
                    "result": {
                        "status": "failed",
                        "message": f"Webhook setup failed: {str(e)}",
                        "attempt_timestamp": int(time.time() * 1000),
                        "error_details": str(e),
                        "data_size_bytes": len(json.dumps(test_payload).encode()) if 'test_payload' in locals() else 0
                    }
                }
                webhook_test_results.append(result)
                logger.error(f"[{request_id}] Webhook setup failed for {shop_id}: {str(e)}")

            session = boto3.session.Session()
            s3_client = session.client(
                "s3",
                region_name=config.spaces_region,
                endpoint_url=config.spaces_endpoint,
                aws_access_key_id=config.spaces_api_key,
                aws_secret_access_key=config.spaces_api_secret
            )

            start_time = time.time()
            has_changed = has_data_changed(data, f"users/{user_uuid}/shopify/data.json", s3_client)
            result = {
                "entity_id": shop_id,
                "result": {
                    "status": "skipped" if not has_changed else "failed",
                    "message": "No changes detected, upload skipped" if not has_changed else "Upload verification failed",
                    "attempt_timestamp": int(time.time() * 1000)
                }
            }
            if start_time:
                result["result"]["response_time_ms"] = int((time.time() - start_time) * 1000)
            previous_hash = get_previous_hash(s3_client, config.spaces_bucket, f"users/{user_uuid}/shopify/data.json")
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
            upload_status_results.append(result)
            logger.info(f"[{request_id}] Upload status result for {shop_id}: {result}")

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "data": data,
        "webhook_test_results": webhook_test_results,
        "upload_status_results": upload_status_results
    })
    response.set_cookie(key="session_id", value=new_session_id, httponly=True, max_age=3600)
    logger.info(f"[{request_id}] Shopify OAuth callback completed successfully")
    return response

@router.get("/webhook")
async def verify_webhook_subscription(request: Request):
    request_id = request.state.request_id
    mode = request.query_params.get("mode")
    token = request.query_params.get("verify_token")
    challenge = request.query_params.get("challenge")
    logger.info(f"[{request_id}] Webhook verification: mode={mode}, token={token}, challenge={challenge}")
    
    if mode == "subscribe" and token == config.shopify_verify_token:
        return PlainTextResponse(challenge)
    
    if not mode:
        return JSONResponse(content={"status": "ok"}, status_code=200)
    
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def shopify_webhook(request: Request):
    request_id = request.state.request_id
    logger.info(f"[{request_id}] Received webhook request: headers {dict(request.headers)}")
    
    if not await verify_hmac(request, config.shopify_api_secret, signature_header="X-Shopify-Hmac-Sha256", hash_algorithm=hashlib.sha256):
        logger.error(f"[{request_id}] Invalid HMAC signature")
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop:
        logger.error(f"[{request_id}] Missing shop domain")
        raise HTTPException(status_code=400, detail="Missing shop domain")

    payload = decode(await request.body(), type=ShopifyWebhookPayload)

    shop_key = shop.replace('.', '_')
    access_token = token_storage.get_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}")
    if not access_token:
        logger.error(f"[{request_id}] Access token not found for shop {shop}")
        raise HTTPException(status_code=500, detail="Access token not found")

    user_uuid = token_storage.get_token(f"USER_UUID_{shop_key}")
    if not user_uuid:
        logger.error(f"[{request_id}] User UUID not found for shop {shop}")
        raise HTTPException(status_code=500, detail="User UUID not found for shop")

    event_type = request.headers.get("X-Shopify-Topic")
    logger.info(f"[{request_id}] Received {event_type} event from {shop}: {asdict(payload)}")

    try:
        data = await get_shopify_data(access_token, shop, request_id=request_id)
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=config.spaces_region,
            endpoint_url=config.spaces_endpoint,
            aws_access_key_id=config.spaces_api_key,
            aws_secret_access_key=config.spaces_api_secret
        )
        spaces_key = f"users/{user_uuid}/shopify/data.json"
        if has_data_changed(data, spaces_key, s3_client):
            upload_to_spaces(data, spaces_key, s3_client)
            logger.info(f"[{request_id}] Updated data in Spaces for {shop} via {event_type}")
    except Exception as e:
        logger.error(f"[{request_id}] Failed to update Spaces for {shop} via {event_type}: {str(e)}")

    return {"status": "success"}