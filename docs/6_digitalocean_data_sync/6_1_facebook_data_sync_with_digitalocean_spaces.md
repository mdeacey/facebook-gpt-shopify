# Chapter 6: DigitalOcean Integration
## Subchapter 6.1: Facebook Data Sync with DigitalOcean Spaces

### Introduction
This subchapter transitions the temporary file storage for Facebook data (`facebook/<page_id>/page_metadata.json` and `facebook/<page_id>/conversations/<sender_id>.json` from Chapter 4) to DigitalOcean Spaces, a cloud storage solution compatible with AWS S3 APIs. The data is organized by user UUID (from Chapter 3) in the structure `users/<uuid>/facebook/<page_id>/page_metadata.json` and `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`. The existing webhook and polling mechanisms (Subchapters 4.1–4.3) are updated to upload non-sensitive metadata and conversation payloads to Spaces using `boto3`, ensuring secure, scalable, and production-ready storage for the GPT Messenger sales bot.

### Prerequisites
- Completed Chapters 1–5.
- FastAPI application running locally or in a production-like environment.
- DigitalOcean Spaces credentials (`SPACES_KEY`, `SPACES_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`) set in `.env`.
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Facebook API credentials and permissions from Chapter 1 and Subchapter 4.1.

---

### Step 1: Configure Environment Variables
Update the `.env` file to include DigitalOcean Spaces credentials.

**Updated `.env.example`**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=http://localhost:5000/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=http://localhost:5000/shopify/webhook
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# Database paths for SQLite storage
TOKEN_DB_PATH=./data/tokens.db
SESSION_DB_PATH=./data/sessions.db
# DigitalOcean Spaces credentials
SPACES_KEY=your_spaces_key
SPACES_SECRET=your_spaces_secret
SPACES_REGION=nyc3
SPACES_BUCKET=your-bucket-name
```

**Notes**:
- Obtain `SPACES_KEY` and `SPACES_SECRET` from your DigitalOcean account (Spaces > API).
- Set `SPACES_REGION` (e.g., `nyc3`) and `SPACES_BUCKET` to your bucket name.
- **Production Note**: Use secure credentials and HTTPS for webhook addresses.

**Why?**
- Enables `boto3` to authenticate with Spaces for data uploads.
- Maintains consistency with existing environment variables.

### Step 2: Update Project Structure
Add a `digitalocean_integration` directory for Spaces utilities:
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
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `digitalocean_integration/utils.py` handles Spaces uploads using `boto3`.
- Integrates with existing `facebook_integration` and `shared` modules.

### Step 3: Create `digitalocean_integration/utils.py`
Add a function to upload JSON data to Spaces.

```python
import boto3
import os
from fastapi import HTTPException
from botocore.exceptions import ClientError

def upload_to_spaces(data: dict, file_path: str):
    spaces_key = os.getenv("SPACES_KEY")
    spaces_secret = os.getenv("SPACES_SECRET")
    spaces_region = os.getenv("SPACES_REGION", "nyc3")
    spaces_bucket = os.getenv("SPACES_BUCKET")

    if not all([spaces_key, spaces_secret, spaces_region, spaces_bucket]):
        raise HTTPException(status_code=500, detail="Missing Spaces configuration")

    session = boto3.session.Session()
    client = session.client(
        "s3",
        region_name=spaces_region,
        endpoint_url=f"https://{spaces_region}.digitaloceanspaces.com",
        aws_access_key_id=spaces_key,
        aws_secret_access_key=spaces_secret
    )

    try:
        client.put_object(
            Bucket=spaces_bucket,
            Key=file_path,
            Body=json.dumps(data),
            ACL="private",
            ContentType="application/json"
        )
        print(f"Uploaded {file_path} to Spaces")
    except ClientError as e:
        print(f"Failed to upload {file_path} to Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")
```

**Why?**
- Uses `boto3` to upload JSON data to Spaces with private ACL.
- Validates environment variables to prevent misconfiguration.
- Logs success or failure for debugging.

### Step 4: Update `facebook_integration/utils.py`
Update polling and webhook functions to upload to Spaces instead of local files.

```python
import os
import httpx
import hmac
import hashlib
import json
from datetime import datetime
from fastapi import HTTPException, Request
from shared.tokens import TokenStorage
from digitalocean_integration.utils import upload_to_spaces

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
        upload_to_spaces(page_data, f"users/{user_uuid}/facebook/{page_id}/page_metadata.json")
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
            for conversation in conversations:
                sender_id = next((p["id"] for p in conversation["participants"]["data"] if p["id"] != page_id), None)
                if not sender_id:
                    continue
                conversation_file = f"users/{user_uuid}/facebook/{page_id}/conversations/{sender_id}.json"
                existing_payloads = []
                is_new_conversation = False
                try:
                    # Attempt to download existing conversation from Spaces
                    session = boto3.session.Session()
                    client = session.client(
                        "s3",
                        region_name=os.getenv("SPACES_REGION", "nyc3"),
                        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
                        aws_access_key_id=os.getenv("SPACES_KEY"),
                        aws_secret_access_key=os.getenv("SPACES_SECRET")
                    )
                    response = client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=conversation_file)
                    existing_payloads = json.loads(response["Body"].read().decode())
                    print(f"Updating conversation for sender {sender_id} on page {page_id}")
                except client.exceptions.NoSuchKey:
                    is_new_conversation = True
                    print(f"New conversation polled for sender {sender_id} on page {page_id}")

                for message in conversation.get("messages", {}).get("data", []):
                    message_payload = {
                        "sender": {"id": message["from"]["id"]},
                        "recipient": {"id": message["to"]["data"][0]["id"]},
                        "timestamp": int(1000 * (datetime.strptime(message["created_time"], "%Y-%m-%dT%H:%M:%S%z").timestamp())),
                        "message": {"mid": message["id"], "text": message["message"]}
                    }
                    if not any(p["message"]["mid"] == message_payload["message"]["mid"] for p in existing_payloads):
                        existing_payloads.append(message_payload)

                upload_to_spaces(existing_payloads, conversation_file)
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
- **Polling Functions**: Update `poll_facebook_data` and `poll_facebook_conversations` to upload to Spaces (`users/<uuid>/facebook/<page_id>/page_metadata.json` and `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`) instead of local files.
- **Conversation Tracking**: Attempts to download existing conversation data from Spaces to append new messages, maintaining consistency with Subchapter 4.2.
- **Directory Rename**: Uses `facebook` instead of `facebook_messenger`, reflecting both metadata and messaging.

### Step 5: Update `facebook_integration/routes.py`
Update the webhook and OAuth callback to use Spaces for storage.

```python
import os
import re
import json
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data, verify_webhook, register_webhooks, get_existing_subscriptions, poll_facebook_data, poll_facebook_conversations
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
from digitalocean_integration.utils import upload_to_spaces
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

    webhook_test_results = []
    polling_test_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        token_storage.store_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}", page["access_token"], type="token")
        token_storage.store_token(f"PAGE_UUID_{page_id}", user_uuid, type="uuid")

        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category,messages' already exists for page {page_id}")

        # Upload metadata to Spaces
        upload_to_spaces(pages, f"users/{user_uuid}/facebook/{page_id}/page_metadata.json")

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
        "polling_test": polling_test_results
    })

@router.post("/webhook")
async def facebook_webhook(request: Request):
    if not await verify_webhook(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    payload = await request.json()
    if payload.get("object") != "page":
        raise HTTPException(status_code=400, detail="Invalid webhook object")

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

                conversation_file = f"users/{user_uuid}/facebook/{page_id}/conversations/{sender_id}.json"
                conversation = []
                is_new_conversation = False
                try:
                    session = boto3.session.Session()
                    client = session.client(
                        "s3",
                        region_name=os.getenv("SPACES_REGION", "nyc3"),
                        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
                        aws_access_key_id=os.getenv("SPACES_KEY"),
                        aws_secret_access_key=os.getenv("SPACES_SECRET")
                    )
                    response = client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=conversation_file)
                    conversation = json.loads(response["Body"].read().decode())
                    print(f"Continuing conversation for sender {sender_id} on page {page_id}")
                except client.exceptions.NoSuchKey:
                    is_new_conversation = True
                    print(f"New conversation started for sender {sender_id} on page {page_id}")

                conversation.append(message_event)
                upload_to_spaces(conversation, conversation_file)
                print(f"Uploaded conversation payload to {conversation_file} for sender {sender_id} on page {page_id} (new: {is_new_conversation})")

        # Handle metadata events
        if "changes" in entry:
            try:
                page_data = await get_facebook_data(access_token)
                upload_to_spaces(page_data, f"users/{user_uuid}/facebook/{page_id}/page_metadata.json")
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
- **Callback Endpoint**: Uploads metadata to Spaces during OAuth.
- **Webhook Endpoint**: Uploads metadata and conversation payloads to Spaces, checking for existing conversations to append messages.
- **Security**: Excludes tokens and uses `TokenStorage` for UUID retrieval.
- **Directory Rename**: Uses `facebook` directory, aligning with metadata and messaging.

### Step 6: Update `requirements.txt`
Add `boto3` for Spaces integration.

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
- `boto3` enables Spaces integration.
- Retains dependencies from previous chapters.

### Step 7: Testing Preparation
To verify Spaces integration:
1. Update `.env` with Spaces credentials.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth to set the `session_id` cookie.
5. Run the Facebook OAuth flow to test webhook and polling uploads.
6. Testing details are in Subchapter 6.4.

**Expected Output** (example logs):
```
Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json to Spaces
Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json to Spaces
```

### Summary: Why This Subchapter Matters
- **Scalable Storage**: Moves Facebook data to Spaces for production-ready storage.
- **UUID Organization**: Uses `users/<uuid>/facebook/<page_id>/...` for multi-user support.
- **Consistency**: Maintains metadata and conversation payload formats from Chapter 4.
- **Security**: Uses private ACL and secure token storage.

### Next Steps:
- Implement Shopify data sync with Spaces (Subchapter 6.2).
- Test Spaces integration (Subchapter 6.4).