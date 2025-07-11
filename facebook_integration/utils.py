import os
import httpx
import hmac
import hashlib
import boto3
from datetime import datetime
from fastapi import HTTPException, Request
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

async def get_facebook_data(access_token: str, user_uuid: str, s3_client: boto3.client):
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
        pages_data = response.json()

    conversations = {}
    for page in pages_data.get("data", []):
        page_id = page["id"]
        url = f"https://graph.facebook.com/v19.0/{page_id}/conversations"
        params = {
            "access_token": page["access_token"],
            "fields": "id,updated_time,participants,messages{message,from,to,created_time,id}"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"Failed to fetch conversations for page {page_id}: {response.text}")
                continue
            page_conversations = response.json().get("data", [])
            for conversation in page_conversations:
                sender_id = next((p["id"] for p in conversation["participants"]["data"] if p["id"] != page_id), None)
                if not sender_id:
                    continue
                conversations.setdefault(sender_id, [])
                for message in conversation.get("messages", {}).get("data", []):
                    message_payload = {
                        "sender": {"id": message["from"]["id"]},
                        "recipient": {"id": message["to"]["data"][0]["id"]},
                        "timestamp": int(1000 * (datetime.strptime(message["created_time"], "%Y-%m-%dT%H:%M:%S%z").timestamp())),
                        "message": {"mid": message["id"], "text": message["message"]}
                    }
                    if not any(p["message"]["mid"] == message_payload["message"]["mid"] for p in conversations[sender_id]):
                        conversations[sender_id].append(message_payload)
                print(f"Fetched conversation for sender {sender_id} on page {page_id}")

    data = pages_data.copy()
    data["conversations"] = conversations
    return data

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
        "subscribed_fields": "name,category,messages,messaging_postbacks,message_echoes",
        "callback_url": webhook_address,
        "verify_token": os.getenv("FACEBOOK_VERIFY_TOKEN", "default_verify_token")
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, params=params)
        if response.status_code == 200:
            print(f"Webhook registered for page {page_id} with fields: name,category,messages,messaging_postbacks,message_echoes")
        else:
            print(f"Failed to register webhook for page {page_id}: {response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to register webhook: {response.text}")

async def get_existing_subscriptions(page_id: str, access_token: str):
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("data", [])

async def daily_poll():
    page_ids = [
        key.replace("FACEBOOK_ACCESS_TOKEN_", "")
        for key in token_storage.get_all_tokens_by_type("token")
        if key.startswith("FACEBOOK_ACCESS_TOKEN_")
    ]
    for page_id in page_ids:
        try:
            access_token = token_storage.get_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
            user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
            if not access_token or not user_uuid:
                print(f"Missing access token or user UUID for page {page_id}")
                continue
            session = boto3.session.Session()
            s3_client = session.client(
                "s3",
                region_name=os.getenv("SPACES_REGION", "nyc3"),
                endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
                aws_access_key_id=os.getenv("SPACES_API_KEY"),
                aws_secret_access_key=os.getenv("SPACES_API_SECRET")
            )
            data = await get_facebook_data(access_token, user_uuid, s3_client)
            spaces_key = f"users/{user_uuid}/facebook/data.json"
            if has_data_changed(data, spaces_key, s3_client):
                upload_to_spaces(data, spaces_key, s3_client)
                print(f"Polled and uploaded data for page {page_id}: Success")
            else:
                print(f"Polled data for page {page_id}: No upload needed, data unchanged")
        except Exception as e:
            print(f"Daily poll failed for page {page_id}: {str(e)}")