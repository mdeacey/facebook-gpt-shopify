import logging
import os
import httpx
import hmac
import hashlib
import time
from datetime import datetime
from fastapi import HTTPException, Request
from shared.tokens import TokenStorage
from shared.utils import retry_async, save_local_data, load_local_data, has_data_changed

logger = logging.getLogger(__name__)

token_storage = TokenStorage()

@retry_async
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
        logger.info(f"Facebook token exchange response: {response.status_code}, {response.text}")
        response.raise_for_status()
        return response.json()

@retry_async
async def get_facebook_data(access_token: str, user_uuid: str):
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {
        "access_token": access_token,
        "fields": "id,name,category,about,website,link,picture,fan_count,verification_status,location,phone,email,created_time,access_token"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        logger.info(f"Facebook accounts data response: {response.status_code}, {response.text}")
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
                logger.error(f"Failed to fetch conversations for page {page_id}: {response.text}")
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
                logger.info(f"Fetched conversation for sender {sender_id} on page {page_id}")

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

@retry_async
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
        logger.info(f"Facebook webhook registration response for page {page_id}: {response.status_code}, {response.text}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to register webhook: {response.text}")
        logger.info(f"Webhook registered for page {page_id} with fields: name,category,messages,messaging_postbacks,message_echoes")

@retry_async
async def get_existing_subscriptions(page_id: str, access_token: str):
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        logger.info(f"Facebook subscriptions response for page {page_id}: {response.status_code}, {response.text}")
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
                logger.error(f"Missing access token or user UUID for page {page_id}")
                continue
            data = await get_facebook_data(access_token, user_uuid)
            spaces_key = f"users/{user_uuid}/facebook/data.json"
            if has_data_changed(data, spaces_key):
                save_local_data(data, spaces_key)
                logger.info(f"Polled and saved data for page {page_id}: Success")
            else:
                logger.info(f"Polled data for page {page_id}: No save needed, data unchanged")
        except Exception as e:
            logger.error(f"Daily poll failed for page {page_id}: {str(e)}")

@retry_async
async def send_facebook_message(page_id: str, recipient_id: str, message_text: str, access_token: str) -> str:
    if not recipient_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid recipient ID: must be a numeric string")
    logger.info(f"Sending Facebook message to recipient {recipient_id} on page {page_id}")
    url = f"https://graph.facebook.com/v19.0/{page_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        logger.info(f"Facebook API response: {response.status_code}, {response.text}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Message send failed: {response.text}")
        return response.json().get("message_id", f"sent_mid_{int(time.time())}")