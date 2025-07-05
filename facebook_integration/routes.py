import os
import re
import json
import hmac
import hashlib
import boto3
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data, verify_webhook, register_webhooks, get_existing_subscriptions, poll_facebook_data, poll_facebook_conversations
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
from digitalocean_integration.utils import has_data_changed, upload_to_spaces
import httpx

router = APIRouter()
token_storage = TokenStorage()
session_storage = SessionStorage()

@router.get("/login")
async def start_oauth(request: Request):
    client_id = os.getenv("FACEBOOK_APP_ID")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
    scope = "pages_messaging,pages_show_list,pages_manage_metadata"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Facebook app config missing")

    if not re.match(r'^\d{15,20}$', client_id):
        raise HTTPException(status_code=500, detail="Invalid FACEBOOK_APP_ID format")

    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id cookie")
    user_uuid = session_storage.get_uuid(session_id)
    if not user_uuid:
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    state = generate_state_token(extra_data=user_uuid)

    auth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code&state={state}"
    )
    return RedirectResponse(auth_url)

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
    if session_id:
        session_storage.clear_session(session_id)

    token_data = await exchange_code_for_token(code)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    token_storage.store_token("FACEBOOK_USER_ACCESS_TOKEN", token_data["access_token"], type="token")

    pages = await get_facebook_data(token_data["access_token"])

    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
        aws_access_key_id=os.getenv("SPACES_API_KEY"),
        aws_secret_access_key=os.getenv("SPACES_API_SECRET")
    )

    webhook_test_results = []
    polling_test_results = []
    upload_status_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        token_storage.store_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}", page["access_token"], type="token")
        token_storage.store_token(f"PAGE_UUID_{page_id}", user_uuid, type="uuid")

        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category,messages' already exists for page {page_id}")

        spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/page_data.json"
        if has_data_changed(pages, spaces_key, s3_client):
            upload_to_spaces(pages, spaces_key, s3_client)
            print(f"Uploaded metadata to Spaces for page {page_id}")

        test_metadata_payload = {
            "object": "page",
            "entry": [{"id": page_id, "changes": [{"field": "name", "value": "Test Page"}]}]
        }
        secret = os.getenv("FACEBOOK_APP_SECRET")
        hmac_signature = f"sha1={hmac.new(secret.encode(), json.dumps(test_metadata_payload).encode(), hashlib.sha1).hexdigest()}"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('FACEBOOK_WEBHOOK_ADDRESS', 'http://localhost:5000/facebook/webhook')}",
                headers={"X-Hub-Signature": hmac_signature, "Content-Type": "application/json"},
                data=json.dumps(test_metadata_payload)
            )
            webhook_test_result = response.json() if response.status_code == 200 else {
                "status": "error", "message": response.text
            }
            webhook_test_results.append({"page_id": page_id, "type": "metadata", "result": webhook_test_result})
            print(f"Metadata webhook test result for page {page_id}: {webhook_test_result}")

        test_message_payload = {
            "object": "page",
            "entry": [
                {
                    "id": page_id,
                    "messaging": [
                        {
                            "sender": {"id": "test_user_id"},
                            "recipient": {"id": page_id},
                            "timestamp": 1697051234567,
                            "message": {"mid": "test_mid", "text": "Test message"}
                        }
                    ]
                }
            ]
        }
        hmac_signature = f"sha1={hmac.new(secret.encode(), json.dumps(test_message_payload).encode(), hashlib.sha1).hexdigest()}"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('FACEBOOK_WEBHOOK_ADDRESS', 'http://localhost:5000/facebook/webhook')}",
                headers={"X-Hub-Signature": hmac_signature, "Content-Type": "application/json"},
                data=json.dumps(test_message_payload)
            )
            webhook_test_result = response.json() if response.status_code == 200 else {
                "status": "error", "message": response.text
            }
            webhook_test_results.append({"page_id": page_id, "type": "messages", "result": webhook_test_result})
            print(f"Message webhook test result for page {page_id}: {webhook_test_result}")

        metadata_result = await poll_facebook_data(page_id)
        polling_test_results.append({"page_id": page_id, "type": "metadata", "result": metadata_result})
        print(f"Metadata polling test result for page {page_id}: {metadata_result}")
        conv_result = await poll_facebook_conversations(page["access_token"], page_id)
        polling_test_results.append({"page_id": page_id, "type": "conversations", "result": conv_result})
        print(f"Conversation polling test result for page {page_id}: {conv_result}")

        upload_status_result = {"status": "failed", "message": "Tests failed"}
        if (webhook_test_results[-2]["result"].get("status") == "success" and
            webhook_test_results[-1]["result"].get("status") == "success" and
            metadata_result.get("status") == "success" and
            conv_result.get("status") == "success"):
            try:
                metadata_key = f"users/{user_uuid}/facebook_messenger/{page_id}/page_data.json"
                response = s3_client.head_object(Bucket=os.getenv("SPACES_BUCKET"), Key=metadata_key)
                if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                    conversation_key = f"users/{user_uuid}/facebook_messenger/{page_id}/conversations/test_user_id.json"
                    response = s3_client.head_object(Bucket=os.getenv("SPACES_BUCKET"), Key=conversation_key)
                    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                        upload_status_result = {"status": "success"}
                        print(f"Upload status verified for page {page_id}: Success")
                    else:
                        upload_status_result = {"status": "failed", "message": "Conversation upload not found"}
                        print(f"Conversation upload not found for page {page_id}")
                else:
                    upload_status_result = {"status": "failed", "message": "Metadata upload not found"}
                    print(f"Metadata upload not found for page {page_id}")
            except Exception as e:
                upload_status_result = {"status": "failed", "message": f"Upload verification failed: {str(e)}"}
                print(f"Upload verification failed for page {page_id}: {str(e)}")
        upload_status_results.append({"page_id": page_id, "result": upload_status_result})

    safe_pages = {
        "data": [
            {k: v for k, v in page.items() if k != "access_token"}
            for page in pages.get("data", [])
        ],
        "paging": pages.get("paging", {})
    }

    return JSONResponse(content={
        "user_uuid": user_uuid,
        "pages": safe_pages,
        "webhook_test": webhook_test_results,
        "polling_test": polling_test_results,
        "upload_status": upload_status_results
    })

@router.post("/webhook")
async def facebook_webhook(request: Request):
    if not await verify_webhook(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    payload = await request.json()
    if payload.get("object") != "page":
        raise HTTPException(status_code=400, detail="Invalid webhook object")

    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
        aws_access_key_id=os.getenv("SPACES_API_KEY"),
        aws_secret_access_key=os.getenv("SPACES_API_SECRET")
    )

    for entry in payload.get("entry", []):
        page_id = entry.get("id")
        if not page_id:
            continue

        access_token = token_storage.get_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
        if not access_token:
            print(f"Access token not found for page {page_id}")
            continue

        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            print(f"User UUID not found for page {page_id}")
            continue

        print(f"Received webhook event for page {page_id}: {entry}")

        if "messaging" in entry:
            for message_event in entry.get("messaging", []):
                sender_id = message_event.get("sender", {}).get("id")
                recipient_id = message_event.get("recipient", {}).get("id")
                if not sender_id or not recipient_id or sender_id == page_id:
                    continue

                spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/conversations/{sender_id}.json"
                conversation = []
                is_new_conversation = False
                try:
                    response = s3_client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=spaces_key)
                    conversation = json.loads(response["Body"].read().decode())
                    print(f"Continuing conversation for sender {sender_id} on page {page_id}")
                except s3_client.exceptions.NoSuchKey:
                    is_new_conversation = True
                    print(f"New conversation started for sender {sender_id} on page {page_id}")

                conversation.append(message_event)
                if has_data_changed(conversation, spaces_key, s3_client):
                    upload_to_spaces(conversation, spaces_key, s3_client)
                    print(f"Uploaded conversation payload to Spaces: {spaces_key} (new: {is_new_conversation})")

        if "changes" in entry:
            try:
                page_data = await get_facebook_data(access_token)
                spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/page_data.json"
                if has_data_changed(page_data, spaces_key, s3_client):
                    upload_to_spaces(page_data, spaces_key, s3_client)
                    print(f"Uploaded metadata to Spaces for page {page_id}")
            except Exception as e:
                print(f"Failed to upload metadata for page {page_id}: {str(e)}")

    return {"status": "success"}

@router.get("/webhook")
async def verify_webhook_subscription(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == os.getenv("FACEBOOK_VERIFY_TOKEN", "default_verify_token"):
        return challenge
    raise HTTPException(status_code=403, detail="Verification failed")