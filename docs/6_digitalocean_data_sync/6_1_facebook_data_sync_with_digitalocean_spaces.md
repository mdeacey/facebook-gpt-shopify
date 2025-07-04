# Chapter 6: DigitalOcean Integration
## Subchapter 6.1: Facebook Data Sync with DigitalOcean Spaces

### Introduction
This subchapter transitions the temporary file storage (`facebook/<page_id>/page_data.json`) from Chapter 4 to DigitalOcean Spaces for persistent, scalable storage of Facebook page metadata for the GPT Messenger sales bot. We update the webhook and polling mechanisms to upload non-sensitive page data to Spaces (`users/<uuid>/facebook/<page_id>/page_data.json`) using the UUID from the SQLite-based `TokenStorage` (Chapter 3). The implementation uses `boto3` for S3-compatible storage, ensuring secure, production-ready data management with `TokenStorage` and `SessionStorage`.

### Prerequisites
- Completed Chapters 1–5 (Facebook OAuth, Shopify OAuth, Persistent Storage, Data Sync).
- FastAPI application running on a DigitalOcean Droplet or locally.
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- DigitalOcean Spaces bucket and credentials configured (Subchapter 6.3).
- Environment variables for Spaces and OAuth set in `.env`.

---

### Step 1: Why DigitalOcean Spaces?
Spaces provides:
- Scalable, S3-compatible storage for page metadata.
- Persistent storage for multiple users, using UUIDs to organize data.
- Integration with existing webhook and polling systems (Chapter 4).
- Preparation for backups in Chapter 7.

### Step 2: Update Project Structure
The project structure builds on Chapters 1–5:
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
- `facebook_integration/` updates webhook and polling to use Spaces.
- `shared/tokens.py` and `shared/sessions.py` provide persistent storage (Chapter 3).
- Excludes backup scripts (Chapter 7).

### Step 3: Configure Environment Variables
Update `.env.example` to include Spaces credentials.

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
# DigitalOcean Spaces credentials
SPACES_KEY=your_spaces_key
SPACES_SECRET=your_spaces_secret
SPACES_REGION=nyc3
SPACES_BUCKET=your-bucket-name
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Notes**:
- Obtain `SPACES_KEY`, `SPACES_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`, and `SPACES_ENDPOINT` from Subchapter 6.3.
- **Production Note**: Use HTTPS for webhook addresses and secure `STATE_TOKEN_SECRET`.

**Why?**
- Enables Spaces integration for data storage.
- Reuses OAuth and webhook variables from Chapters 1–5.

### Step 4: Update `requirements.txt`
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
- `boto3` enables S3-compatible uploads to Spaces.
- Other dependencies support OAuth, webhooks, and polling (Chapters 1–5).

### Step 5: Update `facebook_integration/utils.py`
Update polling to upload data to Spaces using `TokenStorage`.

```python
import os
import httpx
import hmac
import hashlib
import json
import boto3
from fastapi import HTTPException, Request
from botocore.exceptions import ClientError
from shared.tokens import TokenStorage

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

def upload_to_spaces(data: dict, object_key: str):
    session = boto3.session.Session()
    client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION"),
        endpoint_url=os.getenv("SPACES_ENDPOINT"),
        aws_access_key_id=os.getenv("SPACES_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET")
    )
    try:
        client.put_object(
            Bucket=os.getenv("SPACES_BUCKET"),
            Key=object_key,
            Body=json.dumps(data),
            ContentType="application/json",
            ACL="private"
        )
        print(f"Uploaded data to Spaces: {object_key}")
    except ClientError as e:
        print(f"Failed to upload to Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")

async def poll_facebook_data(access_token: str, page_id: str) -> dict:
    try:
        user_access_token = token_storage.get_token("FACEBOOK_USER_ACCESS_TOKEN")
        if not user_access_token:
            raise HTTPException(status_code=500, detail="User access token not found")
        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            raise HTTPException(status_code=500, detail=f"User UUID not found for page {page_id}")
        page_data = await get_facebook_data(user_access_token)
        upload_to_spaces(page_data, f"users/{user_uuid}/facebook/{page_id}/page_data.json")
        return {"status": "success"}
    except Exception as e:
        print(f"Failed to poll data for page {page_id}: {str(e)}")
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
                result = await poll_facebook_data(access_token, page_id)
                if result["status"] == "success":
                    print(f"Polled data for page {page_id}: Success")
                else:
                    print(f"Polling failed for page {page_id}: {result['message']}")
        except Exception as e:
            print(f"Daily poll failed for page {page_id}: {str(e)}")
```

**Why?**
- **OAuth Functions**: Reuses token exchange and data fetching from Chapter 4.
- **Webhook Functions**: Reuses verification and registration from Subchapter 4.1.
- **Spaces Upload**: `upload_to_spaces` stores data in `users/<uuid>/facebook/<page_id>/page_data.json`.
- **Polling**: Updates `poll_facebook_data` to use Spaces with `TokenStorage`.
- **Error Handling**: Ensures robust uploads and logging.

### Step 6: Update `facebook_integration/routes.py`
Update webhook and OAuth callback to use Spaces for storage.

```python
import os
import re
import json
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data, verify_webhook, register_webhooks, get_existing_subscriptions, poll_facebook_data, upload_to_spaces
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
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

    polling_test_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        token_storage.store_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}", page["access_token"], type="token")
        token_storage.store_token(f"PAGE_UUID_{page_id}", user_uuid, type="uuid")

        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category' already exists for page {page_id}")

        upload_to_spaces(pages, f"users/{user_uuid}/facebook/{page_id}/page_data.json")

        polling_result = await poll_facebook_data(page["access_token"], page_id)
        polling_test_results.append({"page_id": page_id, "result": polling_result})

    test_payload = {"object": "page", "entry": [{"id": "test_page_id", "changes": [{"field": "name", "value": "Test Page"}]}]}
    secret = os.getenv("FACEBOOK_APP_SECRET")
    hmac_signature = f"sha1={hmac.new(secret.encode(), json.dumps(test_payload).encode(), hashlib.sha1).hexdigest()}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{os.getenv('FACEBOOK_WEBHOOK_ADDRESS', 'http://localhost:5000/facebook/webhook')}",
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

        try:
            page_data = await get_facebook_data(access_token)
            upload_to_spaces(page_data, f"users/{user_uuid}/facebook/{page_id}/page_data.json")
        except Exception as e:
            print(f"Failed to upload data for page {page_id}: {str(e)}")

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
- **Login Endpoint**: Uses `SessionStorage` for UUID retrieval (Chapter 3).
- **Callback Endpoint**: Uploads data to Spaces, tests webhook and polling, and returns results.
- **Webhook Endpoint**: Processes `name,category` events, uploading to Spaces with `TokenStorage`.
- **Security**: Excludes tokens, uses HMAC, and clears sessions.

### Step 7: Update `.gitignore`
Ensure SQLite databases are excluded.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
```

**Why?**
- Excludes `tokens.db` and `sessions.db`.

### Step 8: Testing Preparation
To verify Spaces integration:
1. Update `.env` with Spaces credentials (Subchapter 6.3).
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie.
5. Run the Facebook OAuth flow to test Spaces uploads.
6. Testing details are in Subchapter 6.4.

### Summary: Why This Subchapter Matters
- **Persistent Storage**: Transitions Facebook data to Spaces for scalability.
- **UUID Integration**: Organizes data by UUID for multi-platform linking.
- **Security**: Uses `TokenStorage` and encrypted storage.
- **Scalability**: Supports production with async processing.

### Next Steps:
- Implement Shopify data sync with Spaces (Subchapter 6.2).
- Set up Spaces bucket (Subchapter 6.3).
- Test Spaces integration (Subchapter 6.4).