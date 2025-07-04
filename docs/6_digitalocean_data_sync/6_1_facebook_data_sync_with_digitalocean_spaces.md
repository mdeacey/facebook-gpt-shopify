# Chapter 6: DigitalOcean Integration
## Subchapter 6.1: Facebook Data Sync with DigitalOcean Spaces

### Introduction
This subchapter integrates DigitalOcean Spaces to store Facebook page metadata for the GPT Messenger sales bot, replacing the temporary file storage (`facebook/<page_id>/page_data.json`) from Chapter 4 with a UUID-based bucket structure (`users/<uuid>/facebook_messenger/<page_id>/page_data.json`). The webhook and polling systems (Subchapters 4.1 and 4.2) are updated to use Spaces, leveraging the UUID from the session-based mechanism (Chapter 3) to organize data. This ensures secure, scalable storage for multiple users, maintaining non-sensitive metadata for the sales bot’s interactions.

### Prerequisites
- Completed Chapters 1–5 (Facebook OAuth, Shopify OAuth, UUID/session management, Facebook data sync, Shopify data sync).
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- Page access tokens (`FACEBOOK_ACCESS_TOKEN_<page_id>`) and UUID mappings (`PAGE_UUID_<page_id>`) stored in the environment.
- DigitalOcean Spaces credentials and bucket set up (Subchapter 6.3).
- `boto3` installed (`pip install boto3`).

---

### Step 1: Configure Environment Variables
Update the `.env` file to include DigitalOcean Spaces credentials, in addition to credentials from Chapters 1–5.

**Updated `.env.example`**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=https://your-app.com/shopify/webhook
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# DigitalOcean Spaces credentials
SPACES_ACCESS_KEY=your_access_key
SPACES_SECRET_KEY=your_secret_key
SPACES_BUCKET=your_bucket_name
SPACES_REGION=nyc3
```

**Notes**:
- Replace placeholders with values from your DigitalOcean account (Subchapter 6.3).
- `SPACES_REGION` defaults to `nyc3` (adjust as needed).
- **Production Note**: Ensure `SPACES_ACCESS_KEY` and `SPACES_SECRET_KEY` have appropriate permissions, and use HTTPS for webhook addresses.

**Why?**
- Enables secure storage of Facebook data in Spaces using the UUID-based structure.

### Step 2: Update Project Structure
Add `digitalocean_integration/` to the project structure from Chapters 1–5:
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
│   ├── session.py
│   └── utils.py
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `digitalocean_integration/utils.py` provides reusable functions for Spaces operations.
- `shared/session.py` supports session-based UUID retrieval (Chapter 3).
- Modular design ensures scalability and consistency.

### Step 3: Create `digitalocean_integration/utils.py`
This module provides functions to check for data changes and upload to Spaces.

```python
import os
import boto3
import json
import hashlib
from fastapi import HTTPException
from botocore.exceptions import ClientError

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")
```

**Why?**
- **Data Comparison**: `has_data_changed` checks if new data differs from existing data in Spaces using a hash comparison.
- **Upload**: `upload_to_spaces` stores data in the specified bucket and key with private access.
- **Error Handling**: Handles missing objects and upload failures with clear HTTP exceptions.

### Step 4: Update `facebook_integration/utils.py`
Update polling to use Spaces with the `users/` prefix instead of temporary file storage.

```python
import os
import httpx
import hmac
import hashlib
from fastapi import HTTPException, Request
import boto3
from digitalocean_integration.utils import has_data_changed, upload_to_spaces

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
        "subscribed_fields": "name,category",
        "callback_url": webhook_address,
        "verify_token": os.getenv("FACEBOOK_VERIFY_TOKEN", "default_verify_token")
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, params=params)
        if response.status_code == 200:
            print(f"Webhook registered for page {page_id}")
        else:
            print(f"Failed to register webhook for page {page_id}: {response.text}")

async def get_existing_subscriptions(page_id: str, access_token: str):
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("data", [])

async def poll_facebook_data(access_token: str, page_id: str) -> dict:
    try:
        user_access_token = os.getenv("FACEBOOK_USER_ACCESS_TOKEN")
        if not user_access_token:
            raise HTTPException(status_code=500, detail="User access token not found")
        user_uuid = os.getenv(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            raise HTTPException(status_code=500, detail=f"User UUID not found for page {page_id}")
        page_data = await get_facebook_data(user_access_token)
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=os.getenv("SPACES_REGION", "nyc3"),
            endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
        )
        spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/page_data.json"
        if has_data_changed(page_data, spaces_key, s3_client):
            upload_to_spaces(page_data, spaces_key, s3_client)
            print(f"Polled and uploaded data for page {page_id}: Success")
        else:
            print(f"Polled data for page {page_id}: No upload needed, data unchanged")
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def daily_poll():
    page_ids = [
        key.replace("FACEBOOK_ACCESS_TOKEN_", "")
        for key in os.environ
        if key.startswith("FACEBOOK_ACCESS_TOKEN_")
    ]

    for page_id in page_ids:
        try:
            access_token_key = f"FACEBOOK_ACCESS_TOKEN_{page_id}"
            access_token = os.getenv(access_token_key)
            if access_token:
                result = await poll_facebook_data(access_token, page_id)
                if result["status"] == "success":
                    print(f"Polled data for page {page_id}: Success")
                else:
                    print(f"Polling failed for page {page_id}: {result['message']}")
        except Exception as e:
            print(f"Daily poll failed for page {page_id}: {str(e)}")
```

**Why?**
- **OAuth and Webhook Functions**: Reuses functions from Chapter 4.
- **Polling Function**: Updates `poll_facebook_data` to use Spaces with `users/<uuid>/facebook_messenger/<page_id>/page_data.json`.
- **Daily Poll**: Iterates over page access tokens, storing data in Spaces.
- **Error Handling**: Returns status and messages.

### Step 5: Update `facebook_integration/routes.py`
Update the OAuth flow, webhook, and polling to use Spaces with the `users/` prefix.

```python
import os
import re
import json
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data, verify_webhook, register_webhooks, get_existing_subscriptions, poll_facebook_data
from shared.utils import generate_state_token, validate_state_token
from shared.session import get_uuid, clear_session
import boto3
import httpx

router = APIRouter()

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
    user_uuid = get_uuid(session_id)
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
    incoming_state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    if not incoming_state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    user_uuid = validate_state_token(incoming_state)
    if not user_uuid:
        raise HTTPException(status_code=400, detail="Invalid UUID in state token")

    session_id = request.cookies.get("session_id")
    if session_id:
        clear_session(session_id)

    token_data = await exchange_code_for_token(code)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    os.environ["FACEBOOK_USER_ACCESS_TOKEN"] = token_data["access_token"]

    pages = await get_facebook_data(token_data["access_token"])

    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
        aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
    )

    polling_test_results = []
    upload_status_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        os.environ[f"FACEBOOK_ACCESS_TOKEN_{page_id}"] = page["access_token"]
        os.environ[f"PAGE_UUID_{page_id}"] = user_uuid

        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category' already exists for page {page_id}")

        polling_result = await poll_facebook_data(page["access_token"], page_id)
        polling_test_results.append({"page_id": page_id, "result": polling_result})

        upload_status_result = {"status": "failed", "message": "Tests failed"}
        if polling_result.get("status") == "success":
            try:
                spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/page_data.json"
                if has_data_changed(pages, spaces_key, s3_client):
                    upload_to_spaces(pages, spaces_key, s3_client)
                    print(f"Uploaded data to Spaces for page {page_id}")
                else:
                    print(f"No upload needed for page {page_id}: Data unchanged")
                upload_status_result = {"status": "success"}
            except Exception as e:
                upload_status_result = {"status": "failed", "message": f"Spaces upload failed: {str(e)}"}
                print(f"Failed to upload to Spaces for page {page_id}: {str(e)}")
        upload_status_results.append({"page_id": page_id, "result": upload_status_result})

    test_payload = {"object": "page", "entry": [{"id": "test_page_id", "changes": [{"field": "name", "value": "Test Page"}]}]}
    secret = os.getenv("FACEBOOK_APP_SECRET")
    hmac_signature = f"sha1={hmac.new(secret.encode(), json.dumps(test_payload).encode(), hashlib.sha1).hexdigest()}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:5000/facebook/webhook",
            headers={
                "X-Hub-Signature": hmac_signature,
                "Content-Type": "application/json"
            },
            data=json.dumps(test_payload)
        )
        webhook_test_result = response.json() if response.status_code == 200 else {"status": "error", "message": response.text}
        print(f"Webhook test result: {webhook_test_result}")

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
        "webhook_test": webhook_test_result,
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
        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
        aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
    )

    for entry in payload.get("entry", []):
        page_id = entry.get("id")
        if not page_id:
            continue

        access_token_key = f"FACEBOOK_ACCESS_TOKEN_{page_id}"
        access_token = os.getenv(access_token_key)
        if not access_token:
            print(f"Access token not found for page {page_id}")
            continue

        user_uuid = os.getenv(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            print(f"User UUID not found for page {page_id}")
            continue

        print(f"Received webhook event for page {page_id}: {entry}")

        try:
            page_data = await get_facebook_data(access_token)
            spaces_key = f"users/{user_uuid}/facebook_messenger/{page_id}/page_data.json"
            if has_data_changed(page_data, spaces_key, s3_client):
                upload_to_spaces(page_data, spaces_key, s3_client)
                print(f"Updated data in Spaces for page {page_id}")
            else:
                print(f"No update needed in Spaces for page {page_id}: Data unchanged")
        except Exception as e:
            print(f"Failed to update Spaces for page {page_id}: {str(e)}")

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
- **Login Endpoint**: Uses the `session_id` cookie to retrieve the UUID (Chapter 3).
- **Callback Endpoint**: Registers webhooks, tests polling and webhooks, uploads to Spaces with `users/` prefix, and returns results with `user_uuid`.
- **Webhook Endpoint**: Processes `name,category` events, storing updates in `users/<uuid>/facebook_messenger/<page_id>/page_data.json`.
- **Security**: Excludes tokens, uses HMAC, and clears sessions.

### Step 6: Update `requirements.txt`
Add `boto3` for Spaces integration.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
apscheduler
boto3
```

**Why?**
- `boto3` enables Spaces API interactions.
- Other dependencies support OAuth, webhooks, and polling.

### Step 7: Testing Preparation
To verify Spaces integration:
1. Update `.env` with `SPACES_*` variables (Subchapter 6.3).
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie.
5. Run the Facebook OAuth flow to test Spaces uploads.
6. Testing details are in Subchapter 6.4.

### Summary: Why This Subchapter Matters
- **Cloud Storage**: Replaces temporary file storage with DigitalOcean Spaces.
- **UUID Integration**: Organizes data in `users/<uuid>/facebook_messenger/<page_id>/page_data.json`.
- **Security**: Ensures non-sensitive data storage and session-based UUID retrieval.
- **Scalability**: Supports multiple users in production.

### Next Steps:
- Integrate Shopify data with Spaces (Subchapter 6.2).
- Set up a Spaces bucket (Subchapter 6.3).
- Test Spaces integration (Subchapter 6.4).