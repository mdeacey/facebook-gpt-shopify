import os
import httpx
import hmac
import hashlib
import json
import boto3
from datetime import datetime
from fastapi import HTTPException, Request
from botocore.exceptions import ClientError
from shared.tokens import TokenStorage
from digitalocean_integration.utils import has_data_changed, upload_to_spaces

token_storage = TokenStorage()

async def exchange_code_for_token(code: str):
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "client_id": os.getenv("FACEBOOK_APP_ID"),
        "redirect_uri": os.getenv("FACEBOOK_REDIRECT_URI"),
        "client_secret": os.getenv("FACEBOOK_APP_SECRET"),
        "code": code
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            print(f"Facebook API error: {response.status_code} - {response.text}")
            response.raise_for_status()
        return response.json()

async def get_facebook_data(access_token: str):
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {
        "access_token": access_token,
        "fields": "id,name,category,about,website,link,picture,fan_count,verification_status,location,phone,email,created_time,access_token"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            print(f"Facebook API error: {response.status_code} - {response.text}")
            response.raise_for_status()
        return response.json()

async def verify_webhook(request: Request) -> bool:
    signature = request.headers.get("X-Hub-Signature")
    if not signature:
        return False
    body = await request.body()
    secret = os.getenv("FACEBOOK_APP_SECRET")
    expected_hmac = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    expected_signature = f"sha1={expected_hmac}"
    return hmac.compare_digest(signature, expected_signature)

async def register_webhooks(page_id: str, access_token: str):
    webhook_address = os.getenv("FACEBOOK_WEBHOOK_ADDRESS")
    if not webhook_address:
        raise HTTPException(status_code=500, detail="FACEBOOK_WEBHOOK_ADDRESS not set")
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "subscribed_fields": "name,category,messages",
        "callback_url": webhook_address,
        "verify_token": os.getenv("FACEBOOK_VERIFY_TOKEN", "default_verify_token")
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, params=params)
        if response.status_code == 200:
            print(f"Webhook registered for page {page_id} with fields: name,category,messages")
        else:
            print(f"Failed to register webhook for page {page_id}: {response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to register webhook: {response.text}")

async def get_existing_subscriptions(page_id: str, access_token: str):
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("data", [])

async def poll_facebook_data(page_id: str) -> dict:
    try:
        user_access_token = token_storage.get_token("FACEBOOK_USER_ACCESS_TOKEN")
        if not user_access_token:
            raise HTTPException(status_code=500, detail="User access token not found")
        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            raise HTTPException(status_code=500, detail=f"User UUID not found for page {page_id}")
        page_data = await get_facebook_data(user_access_token)
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=os.getenv("SPACES_REGION", "nyc3"),
            endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
            aws_access_key_id=os.getenv("SPACES_API_KEY"),
            aws_secret_access_key=os.getenv("SPACES_API_SECRET")
        )
        spaces_key = f"users/{user_uuid}/facebook/{page_id}/page_metadata.json"
        if has_data_changed(page_data, spaces_key, s3_client):
            upload_to_spaces(page_data, spaces_key, s3_client)
            print(f"Polled and uploaded metadata for page {page_id}: Success")
        else:
            print(f"Polled metadata for page {page_id}: No upload needed, data unchanged")
        return {"status": "success"}
    except Exception as e:
        print(f"Failed to poll metadata for page {page_id}: {str(e)}")
        return {"status": "error", "message": str(e)}

async def poll_facebook_conversations(access_token: str, page_id: str) -> dict:
    try:
        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            raise HTTPException(status_code=500, detail=f"User UUID not found for page {page_id}")
        url = f"https://graph.facebook.com/v19.0/{page_id}/conversations"
        params = {
            "access_token": access_token,
            "fields": "id,updated_time,participants,messages{message,from,to,created_time,id}"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"Failed to fetch conversations for page {page_id}: {response.text}")
                raise HTTPException(status_code=500, detail=f"Conversation fetch failed: {response.text}")
            conversations = response.json().get("data", [])
            session = boto3.session.Session()
            s3_client = session.client(
                "s3",
                region_name=os.getenv("SPACES_REGION", "nyc3"),
                endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
                aws_access_key_id=os.getenv("SPACES_API_KEY"),
                aws_secret_access_key=os.getenv("SPACES_API_SECRET")
            )
            for conversation in conversations:
                sender_id = next((p["id"] for p in conversation["participants"]["data"] if p["id"] != page_id), None)
                if not sender_id:
                    continue
                spaces_key = f"users/{user_uuid}/facebook/{page_id}/conversations/{sender_id}.json"
                existing_payloads = []
                is_new_conversation = False
                try:
                    response = s3_client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=spaces_key)
                    existing_payloads = json.loads(response["Body"].read().decode())
                    print(f"Updating conversation for sender {sender_id} on page {page_id}")
                except ClientError as e:
                    if e.response["Error"]["Code"] == "NoSuchKey":
                        is_new_conversation = True
                        print(f"New conversation polled for sender {sender_id} on page {page_id}")
                    else:
                        raise HTTPException(status_code=500, detail=f"Failed to fetch conversation: {str(e)}")
                for message in conversation.get("messages", {}).get("data", []):
                    message_payload = {
                        "sender": {"id": message["from"]["id"]},
                        "recipient": {"id": message["to"]["data"][0]["id"]},
                        "timestamp": int(1000 * (datetime.strptime(message["created_time"], "%Y-%m-%dT%H:%M:%S%z").timestamp())),
                        "message": {"mid": message["id"], "text": message["message"]}
                    }
                    if not any(p["message"]["mid"] == message_payload["message"]["mid"] for p in existing_payloads):
                        existing_payloads.append(message_payload)
                if has_data_changed(existing_payloads, spaces_key, s3_client):
                    upload_to_spaces(existing_payloads, spaces_key, s3_client)
                    print(f"Uploaded conversation payloads to Spaces: {spaces_key} (new: {is_new_conversation})")
            return {"status": "success"}
    except Exception as e:
        print(f"Failed to poll conversations for page {page_id}: {str(e)}")
        return {"status": "error", "message": str(e)}

async def daily_poll():
    page_ids = [
        key.replace("FACEBOOK_ACCESS_TOKEN_", "")
        for key in token_storage.get_all_tokens_by_type("token")
        if key.startswith("FACEBOOK_ACCESS_TOKEN_")
    ]
    for page_id in page_ids:
        try:
            access_token = token_storage.get_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
            if access_token:
                result = await poll_facebook_data(page_id)
                if result["status"] == "success":
                    print(f"Polled metadata for page {page_id}: Success")
                else:
                    print(f"Metadata polling failed for page {page_id}: {result['message']}")
                conv_result = await poll_facebook_conversations(access_token, page_id)
                if conv_result["status"] == "success":
                    print(f"Polled conversations for page {page_id}: Success")
                else:
                    print(f"Conversation polling failed for page {page_id}: {conv_result['message']}")
        except Exception as e:
            print(f"Daily poll failed for page {page_id}: {str(e)}")