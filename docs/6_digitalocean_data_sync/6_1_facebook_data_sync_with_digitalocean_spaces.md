# Chapter 6: DigitalOcean Integration
## Subchapter 6.1: Facebook Data Sync with DigitalOcean Spaces

### Introduction
This subchapter transitions the temporary file storage for Facebook data (`facebook/<page_id>/page_data.json` and `facebook/<page_id>/conversations/<sender_id>.json`) from Chapter 4 to DigitalOcean Spaces for persistent, scalable storage of page metadata and conversation histories for the GPT Messenger sales bot. We update the webhook and polling mechanisms to upload non-sensitive metadata to `users/<uuid>/facebook_messenger/<page_id>/page_data.json` and conversation payloads to `users/<uuid>/facebook_messenger/<page_id>/conversations/<sender_id>.json`, using the UUID from the SQLite-based `TokenStorage` (Chapter 3). The implementation uses `boto3` for S3-compatible storage, ensuring secure, production-ready data management with `TokenStorage` and `SessionStorage`.

### Prerequisites
- Completed Chapters 1–5 (Facebook OAuth, Shopify OAuth, Persistent Storage, Data Sync).
- FastAPI application running on a DigitalOcean Droplet or locally (e.g., `http://localhost:5000`).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- DigitalOcean Spaces bucket and credentials configured (Subchapter 6.3).
- Environment variables for Spaces, OAuth, and webhooks set in `.env` (Chapters 1–4, Subchapter 6.3).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- A publicly accessible webhook URL for testing (e.g., via `ngrok http 5000`).

---

### Step 1: Why DigitalOcean Spaces?
Spaces provides:
- Scalable, S3-compatible storage for page metadata and conversation histories.
- Persistent storage for multiple users, organized by UUID (`users/<uuid>/...`).
- Integration with webhook and polling systems for metadata (`name`, `category`) and messages (Chapter 4).
- Preparation for backups in Chapter 7.

### Step 2: Update Project Structure
The project structure builds on Chapters 1–5, adding a new utility module for Spaces:
```
.
├── app.py
├── facebook_integration/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shopify_integration/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── digitalocean_integration/
│   ├── __init__.py
│   └── utils.py
├── shared/
│   ├── __init__.py
│   ├── sessions.py
│   ├── tokens.py
│   └── utils.py
├── scripts/
│   ├── backup_tokens_db.sh
│   └── backup_sessions_db.sh
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `digitalocean_integration/utils.py` provides reusable Spaces upload functions.
- `facebook_integration/` updates webhook and polling to use Spaces for metadata and conversations.
- `shared/tokens.py` and `shared/sessions.py` provide persistent storage (Chapter 3).
- `scripts/` includes backup scripts (Chapter 7).

### Step 3: Configure Environment Variables
Update `.env.example` to include Spaces credentials, alongside existing OAuth and webhook variables.

**Updated `.env.example`**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback
# Webhook configuration
FACEBOOK_WEBHOOK_ADDRESS=http://localhost:5000/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
# DigitalOcean Spaces credentials
SPACES_API_KEY=your_spaces_key
SPACES_API_SECRET=your_spaces_secret
SPACES_REGION=nyc3
SPACES_BUCKET=gpt-messenger-data
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# Database paths for SQLite storage
TOKEN_DB_PATH=./data/tokens.db
SESSION_DB_PATH=./data/sessions.db
```

**Notes**:
- Obtain `SPACES_API_KEY`, `SPACES_API_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`, and `SPACES_ENDPOINT` from Subchapter 6.3.
- **Production Note**: Use HTTPS for `FACEBOOK_WEBHOOK_ADDRESS` and a secure `STATE_TOKEN_SECRET`. Store Spaces credentials securely.

**Why?**
- Enables Spaces integration for metadata and conversations.
- Reuses OAuth and webhook variables from Chapters 1–4.
- Includes database paths for backups (Chapter 7).

### Step 4: Create `digitalocean_integration/utils.py`
Add utility functions for Spaces uploads and data comparison, introduced in Chapter 6.

```python
import json
import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
import hashlib

def compute_data_hash(data: dict) -> str:
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()

def has_data_changed(data: dict, key: str, s3_client: boto3.client) -> bool:
    new_hash = compute_data_hash(data)
    try:
        response = s3_client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=key)
        existing_data = response["Body"].read().decode()
        existing_hash = hashlib.sha256(existing_data.encode()).hexdigest()
        return existing_hash != new_hash
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return True
        raise HTTPException(status_code=500, detail=f"Failed to fetch existing data: {str(e)}")

def upload_to_spaces(data: dict, key: str, s3_client: boto3.client):
    try:
        s3_client.put_object(
            Bucket=os.getenv("SPACES_BUCKET"),
            Key=key,
            Body=json.dumps(data, ensure_ascii=False),
            ContentType="application/json",
            ACL="private"
        )
        print(f"Uploaded data to Spaces: {key}")
    except Exception as e:
        print(f"Failed to upload to Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")
```

**Why?**
- **Data Hashing**: `compute_data_hash` creates a SHA-256 hash to compare data.
- **Change Detection**: `has_data_changed` checks if new data differs from existing data in Spaces.
- **Upload Function**: `upload_to_spaces` uploads JSON data to Spaces with private ACL.
- **No Future Dependencies**: Self-contained for Chapter 6.

### Step 5: Update `facebook_integration/utils.py`
Update polling to upload metadata and conversation payloads to Spaces, including `messages` in `subscribed_fields`.

```python
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
        spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/page_data.json"
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
                spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/conversations/{sender_id}.json"
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
```

**Why?**
- **Updated Imports**: Removed `compute_data_hash` import, keeping only `has_data_changed` and `upload_to_spaces`.
- **Updated `poll_facebook_data`**: Removed unused `access_token` parameter, using `user_access_token` from `TokenStorage`.
- **Conversation Handling**: Included `poll_facebook_conversations` for conversation payloads, with new vs. continuing checks.
- **Webhook Support**: Included `messages` in `subscribed_fields` for `register_webhooks`, aligning with Subchapter 4.2.
- **Chapter 7 Alignment**: Compatible with backup scripts and Spaces configuration.

### Step 6: Update `facebook_integration/routes.py`
Update the webhook and OAuth callback to upload metadata and conversation payloads to Spaces, including upload status verification.

```python
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

        # Test metadata webhook
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

        # Test message webhook
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

        # Test polling
        metadata_result = await poll_facebook_data(page_id)
        polling_test_results.append({"page_id": page_id, "type": "metadata", "result": metadata_result})
        print(f"Metadata polling test result for page {page_id}: {metadata_result}")
        conv_result = await poll_facebook_conversations(page["access_token"], page_id)
        polling_test_results.append({"page_id": page_id, "type": "conversations", "result": conv_result})
        print(f"Conversation polling test result for page {page_id}: {conv_result}")

        # Verify upload status
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

        # Handle message events
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

        # Handle metadata events (name, category)
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
```

**Why?**
- **Login Endpoint**: Unchanged, uses `SessionStorage` for UUID retrieval (Chapter 3).
- **Callback Endpoint**: Uploads metadata to Spaces, tests webhooks and polling for metadata and conversations, verifies upload status with `upload_status_results`, and returns results.
- **Webhook Endpoint**: Uploads `messaging` payloads to Spaces, maintaining new vs. continuing conversation checks.
- **Security**: Excludes tokens, uses HMAC verification, and clears sessions.
- **Spaces Integration**: Uses `has_data_changed` and `upload_to_spaces` for efficient uploads.

### Step 7: Update `requirements.txt`
Ensure `boto3` is included for Spaces integration.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
boto3
```

**Why?**
- `boto3` enables S3-compatible uploads to Spaces.
- Other dependencies support OAuth, webhooks, polling, and backups (Chapters 1–7).

### Step 8: Update `.gitignore`
Ensure SQLite databases and backup scripts are excluded, removing temporary file exclusions as they are replaced by Spaces.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
/app/backups/
/app/scripts/backup_tokens_db.sh
/app/scripts/backup_sessions_db.sh
```

**Why?**
- Excludes `tokens.db`, `sessions.db`, backup files, and scripts.
- Removes `facebook/` as data is stored in Spaces.

### Step 9: Testing Preparation
To verify Spaces integration for Facebook data:
1. Update `.env` with Spaces credentials (Subchapter 6.3).
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie.
5. Run the Facebook OAuth flow to test Spaces uploads.
6. Testing details are in Subchapter 6.4.

### Summary: Why This Subchapter Matters
- **Persistent Storage**: Transitions Facebook metadata and conversation histories to Spaces for scalability.
- **UUID Integration**: Organizes data by UUID for multi-platform linking.
- **Security**: Uses `TokenStorage` and encrypted storage.
- **Scalability**: Supports production with async processing and efficient uploads.
- **Conversation Support**: Stores full `messaging` payloads, preserving all data for future use.

### Next Steps:
- Implement Shopify data sync with Spaces (Subchapter 6.2).
- Set up Spaces bucket (Subchapter 6.3).
- Test Spaces integration (Subchapter 6.4).