# Chapter 4: Facebook Data Sync
## Subchapter 4.1: Setting Up Facebook Webhooks for Real-Time Updates

### Introduction
Facebook webhooks enable real-time notifications for page events (e.g., changes to page name or category) to keep the GPT Messenger sales bot’s data up-to-date. This subchapter sets up a secure webhook endpoint in the FastAPI application, integrating HMAC verification and registering webhooks during the OAuth flow with appropriate permissions (`pages_show_list`, `pages_manage_metadata`). The webhook system uses the UUID from the SQLite-based session mechanism (Chapter 3) to identify the user and temporarily stores data in a file-based structure (`facebook/<page_id>/page_data.json`), preparing for cloud storage in Chapter 6. The focus is on non-sensitive metadata, using `TokenStorage` and `SessionStorage` for secure, persistent data management.

### Prerequisites
- Completed Chapters 1–3 (Facebook OAuth, Shopify OAuth, Persistent Storage and User Identification).
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`) and `STATE_TOKEN_SECRET` set in `.env` (Chapter 1).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- A publicly accessible webhook URL for testing (e.g., via ngrok).

---

### Step 1: Configure Environment Variables
Update the `.env` file to include webhook-specific variables for Facebook, in addition to the OAuth credentials from Chapters 1–3.

**Updated `.env.example`**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback
# Webhook configuration
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Notes**:
- Replace placeholders with values from your Facebook Developer App (Subchapter 1.2).
- `FACEBOOK_WEBHOOK_ADDRESS` must be publicly accessible (e.g., use ngrok for local testing: `ngrok http 5000`).
- `FACEBOOK_VERIFY_TOKEN` is a custom string for webhook verification (generate via `python -c "import secrets; print(secrets.token_urlsafe(32))"`).
- **Production Note**: Ensure `STATE_TOKEN_SECRET` is secure and unique, and use HTTPS for `FACEBOOK_WEBHOOK_ADDRESS`.

**Why?**
- Authenticates the OAuth flow and secures webhook verification.
- Prepares for webhook registration and event processing.
- Excludes Spaces variables (introduced in Chapter 6).

### Step 2: Update Project Structure
The project structure builds on Chapters 1–3:
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
- `facebook_integration/` contains webhook routes and utilities, using `TokenStorage` and `SessionStorage`.
- `shared/sessions.py` and `shared/tokens.py` manage persistent sessions and tokens (Chapter 3).
- Excludes Spaces integration (Chapter 6).

### Step 3: Update `facebook_integration/utils.py`
Add utility functions for webhook verification and registration, using `TokenStorage`.

```python
import os
import httpx
import hmac
import hashlib
from fastapi import HTTPException, Request
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
```

**Why?**
- **Token Exchange and Data Fetching**: Reuses OAuth functions from Chapter 1.
- **Webhook Verification**: Validates incoming webhook events with HMAC.
- **Webhook Registration**: Subscribes to `name,category` events during OAuth.
- **Existing Subscriptions**: Prevents duplicate subscriptions.
- **TokenStorage**: Initialized for future use (e.g., polling in Subchapter 4.2).
- **No Storage**: Webhook data storage is handled in `routes.py`.

### Step 4: Update `facebook_integration/routes.py`
Update the OAuth flow to register webhooks, add a webhook endpoint, and use `TokenStorage` and `SessionStorage` with temporary file storage.

```python
import os
import re
import json
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data, verify_webhook, register_webhooks, get_existing_subscriptions
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

    for page in pages.get("data", []):
        page_id = page["id"]
        token_storage.store_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}", page["access_token"], type="token")
        token_storage.store_token(f"PAGE_UUID_{page_id}", user_uuid, type="uuid")

        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category' already exists for page {page_id}")

        # Temporary file storage
        os.makedirs(f"facebook/{page_id}", exist_ok=True)
        with open(f"facebook/{page_id}/page_data.json", "w") as f:
            json.dump(pages, f)
        print(f"Wrote data to facebook/{page_id}/page_data.json for page {page_id}")

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
        "webhook_test": webhook_test_result
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
            os.makedirs(f"facebook/{page_id}", exist_ok=True)
            with open(f"facebook/{page_id}/page_data.json", "w") as f:
                json.dump(page_data, f)
            print(f"Wrote data to facebook/{page_id}/page_data.json for page {page_id}")
        except Exception as e:
            print(f"Failed to write data for page {page_id}: {str(e)}")

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
- **Login Endpoint**: Uses `SessionStorage` to retrieve the UUID from the `session_id` cookie (Chapter 3).
- **Callback Endpoint**: Registers webhooks, tests the webhook endpoint, stores data in `facebook/<page_id>/page_data.json`, uses `TokenStorage` for tokens/UUIDs, and returns non-sensitive page data with `user_uuid` and `webhook_test`.
- **Webhook Endpoint**: Processes `name,category` events, storing updates in temporary files using `TokenStorage` for token/UUID retrieval.
- **Security**: Excludes tokens, uses HMAC verification, clears sessions.
- **Temporary Storage**: Prepares for cloud storage in Chapter 6.

### Step 5: Configure Webhook in Facebook Developer Portal
**Action**: Set up the webhook in the Meta Developer Portal:
1. Log into `developers.facebook.com` and navigate to your app (Subchapter 1.2).
2. Add “Webhooks” under “Products” (click “Add Product” if not added).
3. Select “Page” as the webhook object.
4. Click “Add Callback URL” and enter:
   - **Callback URL**: `FACEBOOK_WEBHOOK_ADDRESS` (e.g., `https://your-app.com/facebook/webhook` or `http://localhost:5000/facebook/webhook` via ngrok).
   - **Verify Token**: `FACEBOOK_VERIFY_TOKEN` from `.env`.
5. Click “Verify and Save”.
6. Subscribe to `name` and `category` fields under “Page Subscriptions”.

**Expected Output**: The portal confirms webhook verification.

**Screenshot Reference**: Webhooks settings page showing the “Page” webhook, Callback URL, and Verify Token fields.

**Why?**
- Configures Facebook to send real-time events to `/facebook/webhook`.
- Requires `pages_manage_metadata` permission.
- Ngrok ensures local testing accessibility.
- Uses `FACEBOOK_WEBHOOK_ADDRESS` for flexibility.

### Step 6: Update `requirements.txt`
Add `cryptography` for session/token encryption.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
```

**Why?**
- `cryptography` supports `TokenStorage` and `SessionStorage` (Chapter 3).
- Excludes `apscheduler` and `boto3` (introduced in Subchapter 4.2 and Chapter 6).
- Supports OAuth and webhooks.

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
- Excludes `tokens.db` and `sessions.db` to prevent committing sensitive data.

### Step 8: Testing Preparation
To verify the webhook setup:
1. Update `.env` with `FACEBOOK_WEBHOOK_ADDRESS` and `FACEBOOK_VERIFY_TOKEN`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie.
5. Run the Facebook OAuth flow (Chapter 1) to test webhook registration.
6. Testing details are in Subchapter 4.3.

### Summary: Why This Subchapter Matters
- **Real-Time Updates**: Webhooks keep page metadata current for the sales bot.
- **Security**: HMAC verification, `TokenStorage`, and `SessionStorage` ensure secure, multi-user operation.
- **UUID Integration**: Links data using the UUID from Chapter 3.
- **Scalability**: Async processing supports high traffic.
- **Temporary Storage**: Prepares for cloud storage in Chapter 6.

### Next Steps:
- Implement daily polling for redundancy (Subchapter 4.2).
- Test webhooks and polling (Subchapter 4.3).