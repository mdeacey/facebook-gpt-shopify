import logging
import json
import time
import hmac
import hashlib
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse
from .utils import get_facebook_data, register_webhooks, get_existing_subscriptions, send_facebook_message
from shared.utils import generate_state_token, validate_state_token, compute_data_hash, get_previous_hash, check_endpoint_accessibility, exchange_code_for_token, verify_hmac, save_local_data, load_local_data
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
from shared.config import config
from shared.models import FacebookWebhookPayload
from integrations.digitalocean.agent import generate_agent_response
from msgspec.json import decode

logger = logging.getLogger(__name__)

router = APIRouter()
token_storage = TokenStorage()
session_storage = SessionStorage()

@router.get("/login")
async def start_oauth(request: Request):
    client_id = config.facebook_app_id
    redirect_uri = config.facebook_redirect_uri
    scope = "pages_messaging,pages_show_list,pages_manage_metadata"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Facebook app config missing")

    session_id = request.cookies.get("session_id")
    new_session_id, user_uuid = session_storage.get_or_create_session(session_id)

    token_keys = [
        key for key in token_storage.get_all_tokens_by_type("token")
        if key.startswith("FACEBOOK_ACCESS_TOKEN_") or key.startswith("PAGE_UUID_")
    ]
    for key in token_keys:
        if token_storage.get_token(key) and user_uuid == token_storage.get_token(f"PAGE_UUID_{key.replace('FACEBOOK_ACCESS_TOKEN_', '')}"):
            token_storage.delete_token(key)

    state = generate_state_token(extra_data=user_uuid)

    auth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code&state={state}"
    )
    response = RedirectResponse(auth_url)
    response.set_cookie(key="session_id", value=new_session_id, httponly=True, max_age=3600)
    return response

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    user_uuid = validate_state_token(state)
    if not user_uuid:
        raise HTTPException(status_code=400, detail="Invalid UUID in state token")

    session_id = request.cookies.get("session_id")
    session_storage.verify_session(session_id, expected_uuid=user_uuid)

    new_session_id, user_uuid = session_storage.get_or_create_session(session_id)

    token_data = await exchange_code_for_token(
        code=code,
        client_id=config.facebook_app_id,
        client_secret=config.facebook_app_secret,
        redirect_uri=config.facebook_redirect_uri,
        token_url="https://graph.facebook.com/v19.0/oauth/access_token"
    )
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    token_storage.store_token("FACEBOOK_USER_ACCESS_TOKEN", token_data["access_token"], type="token")

    data = await get_facebook_data(token_data["access_token"], user_uuid)

    webhook_test_results = []
    upload_status_results = []

    webhook_url = config.facebook_webhook_address
    is_accessible, accessibility_message = await check_endpoint_accessibility(
        endpoint=webhook_url,
        endpoint_type="webhook",
        method="GET"
    )
    if not is_accessible:
        logger.error(f"Webhook endpoint check failed: {accessibility_message}")
        webhook_test_results.append({
            "entity_id": "all",
            "result": {
                "status": "failed",
                "message": accessibility_message,
                "attempt_timestamp": int(time.time() * 1000)
            }
        })

    entities = data.get("data", [])  # Pages
    async with httpx.AsyncClient() as client:
        for page in entities:
            page_id = page["id"]
            token_storage.store_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}", page["access_token"], type="token")
            token_storage.store_token(f"PAGE_UUID_{page_id}", user_uuid, type="uuid")

            existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
            if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
                await register_webhooks(page_id, page["access_token"])
            else:
                logger.info(f"Webhook subscription for 'name,category,messages,messaging_postbacks,message_echoes' already exists for page {page_id}")

            test_metadata_payload = {
                "object": "page",
                "entry": [{"id": page_id, "changes": [{"field": "name", "value": "Test Page"}]}]
            }
            secret = config.facebook_app_secret
            hmac_signature = f"sha1={hmac.new(secret.encode(), json.dumps(test_metadata_payload).encode(), hashlib.sha1).hexdigest()}"
            logger.info(f"Sending metadata webhook test to {webhook_url} with payload {json.dumps(test_metadata_payload)}")
            start_time = time.time()
            response = await client.post(
                webhook_url,
                headers={"X-Hub-Signature": hmac_signature, "Content-Type": "application/json"},
                data=json.dumps(test_metadata_payload),
                timeout=10
            )
            logger.info(f"Metadata webhook test response: status {response.status_code}, body {response.text}")
            result = {
                "entity_id": page_id,
                "result": {
                    "status": "success" if response.status_code == 200 else "failed",
                    "message": "Metadata webhook test succeeded" if response.status_code == 200 else "Metadata webhook test failed",
                    "attempt_timestamp": int(time.time() * 1000)
                }
            }
            if start_time:
                result["result"]["response_time_ms"] = int((time.time() - start_time) * 1000)
            if response.status_code != 200:
                result["result"].update({
                    "http_status_code": response.status_code,
                    "response_body": response.text,
                    "request_payload": json.dumps(test_metadata_payload),
                    "server_response_headers": dict(response.headers),
                    "data_size_bytes": len(json.dumps(test_metadata_payload).encode())
                })
            webhook_test_results.append(result)
            logger.info(f"Metadata webhook test result for page {page_id}: {result}")

            start_time = time.time()
            has_changed = has_data_changed(data, f"users/{user_uuid}/facebook/data.json")
            result = {
                "entity_id": page_id,
                "result": {
                    "status": "skipped" if not has_changed else "failed",
                    "message": "No changes detected, upload skipped" if not has_changed else "Upload verification failed",
                    "attempt_timestamp": int(time.time() * 1000)
                }
            }
            if start_time:
                result["result"]["response_time_ms"] = int((time.time() - start_time) * 1000)
            previous_hash = get_previous_hash(f"users/{user_uuid}/facebook/data.json")
            if previous_hash:
                result["result"]["previous_hash"] = previous_hash
            if has_changed:
                try:
                    save_local_data(data, f"users/{user_uuid}/facebook/data.json")
                    result["result"].update({
                        "status": "success",
                        "message": "Data successfully saved locally",
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
            logger.info(f"Upload status result for page {page_id}: {result}")

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "data": data,
        "webhook_test_results": webhook_test_results,
        "upload_status_results": upload_status_results
    })
    response.set_cookie(key="session_id", value=new_session_id, httponly=True, max_age=3600)
    return response

@router.post("/webhook")
async def facebook_webhook(request: Request):
    logger.info(f"Received webhook request: headers {dict(request.headers)}")
    if not await verify_hmac(request, config.facebook_app_secret, signature_header="X-Hub-Signature", hash_algorithm=hashlib.sha1):
        logger.error("Invalid HMAC signature")
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    payload = decode(await request.body(), type=FacebookWebhookPayload)
    if payload.object != "page":
        raise HTTPException(status_code=400, detail="Invalid webhook object")

    for entry in payload.entry:
        page_id = entry.get("id")
        if not page_id:
            continue

        access_token = token_storage.get_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
        if not access_token:
            logger.error(f"Access token not found for page {page_id}")
            continue

        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            logger.error(f"User UUID not found for page {page_id}")
            continue

        logger.info(f"Received webhook event for page {page_id}: {entry}")

        spaces_key = f"users/{user_uuid}/facebook/data.json"
        existing_data = await load_local_data(spaces_key) or {"data": [], "paging": {}, "conversations": {}}

        if "messaging" in entry:
            for message_event in entry.get("messaging", []):
                sender_id = message_event.get("sender", {}).get("id")
                recipient_id = message_event.get("recipient", {}).get("id")
                if not sender_id or not recipient_id or sender_id == page_id:
                    continue

                message_text = message_event.get("message", {}).get("text")
                if not message_text:
                    continue

                existing_data["conversations"].setdefault(sender_id, [])
                if not any(msg["message"]["mid"] == message_event["message"]["mid"] for msg in existing_data["conversations"][sender_id]):
                    existing_data["conversations"][sender_id].append(message_event)
                    logger.info(f"Added message to conversations for sender {sender_id} on page {page_id}")

                try:
                    agent_response = await generate_agent_response(page_id, sender_id, message_text, user_uuid)
                    response_text = agent_response["text"]
                    sent_message_id = await send_facebook_message(page_id, sender_id, response_text, access_token)

                    agent_payload = {
                        "sender": {"id": page_id},
                        "recipient": {"id": sender_id},
                        "timestamp": int(time.time() * 1000),
                        "message": {"mid": sent_message_id, "text": response_text}
                    }
                    existing_data["conversations"][sender_id].append(agent_payload)
                    logger.info(f"Added AI response to conversations for sender {sender_id} on page {page_id}")
                except Exception as e:
                    logger.error(f"Failed to generate or send AI response for sender {sender_id} on page {page_id}: {str(e)}")

        if "changes" in entry:
            try:
                user_access_token = token_storage.get_token("FACEBOOK_USER_ACCESS_TOKEN")
                if not user_access_token:
                    logger.error(f"User access token not found for user {user_uuid}")
                    continue
                updated_data = await get_facebook_data(user_access_token, user_uuid)
                existing_data["data"] = updated_data["data"]
                existing_data["paging"] = updated_data["paging"]
                logger.info(f"Updated page data for page {page_id}")
            except Exception as e:
                logger.error(f"Failed to update page data for page {page_id}: {str(e)}")

        if has_data_changed(existing_data, spaces_key):
            save_local_data(existing_data, spaces_key)
            logger.info(f"Saved data locally: {spaces_key}")

    return {"status": "success"}

@router.get("/webhook")
async def verify_webhook_subscription(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    logger.info(f"Webhook verification: mode={mode}, token={token}, challenge={challenge}")
    
    if mode == "subscribe" and token == config.facebook_verify_token:
        return PlainTextResponse(challenge)
    
    if not mode:
        return JSONResponse(content={"status": "ok"}, status_code=200)
    
    raise HTTPException(status_code=403, detail="Verification failed")