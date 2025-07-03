# Chapter 2: Facebook Data Sync
## Subchapter 2.1: Setting Up Facebook Webhooks for Real-Time Updates

### Introduction
Facebook webhooks enable your application to receive real-time notifications about page events, such as changes to page name, category, or other metadata, to keep your GPT Messenger sales bot’s data up-to-date. This subchapter guides you through setting up a secure webhook endpoint in your FastAPI application, integrating HMAC verification, registering webhooks during the OAuth flow with appropriate permissions, and including an automatic test to verify functionality. The webhook system focuses on non-sensitive metadata, ensuring secure data handling without exposing access tokens.

### Prerequisites
- Completed Facebook OAuth setup from Chapter 1.
- Your FastAPI application is running locally or in a production-like environment.
- Required permissions: `pages_show_list` and `pages_manage_metadata` for webhook subscriptions.
- `apscheduler` is installed (`pip install apscheduler`).

---

### Step 1: Configure Environment Variables
Ensure your `.env` file includes Facebook-specific variables required for webhook functionality.

**Updated `.env` Example**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Notes**:
- Replace placeholders (e.g., `your_facebook_app_id`) with actual values from your Facebook Developer App (Subchapter 1.2).
- `FACEBOOK_WEBHOOK_ADDRESS` must be a publicly accessible URL in production (e.g., via ngrok for testing).
- `FACEBOOK_VERIFY_TOKEN` is a custom string you define for webhook verification (generate via `python -c "import secrets; print(secrets.token_urlsafe(32))"`).
- `STATE_TOKEN_SECRET` is used for CSRF protection, as set in Subchapter 1.1.

**Why?**
- These variables authenticate the OAuth flow, secure webhook verification, and ensure CSRF protection, aligning with the secure setup from Chapter 1.

### Step 2: Update `facebook_oauth/utils.py`
Add utility functions to support webhook registration and verification for Facebook page events, subscribing to `name` and `category` fields to capture relevant page metadata.

**Updated File: `facebook_oauth/utils.py`**
```python
import os
import httpx
import hmac
import hashlib
from fastapi import HTTPException, Request

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
    """
    Verifies the HMAC signature of incoming Facebook webhook requests.
    """
    signature = request.headers.get("X-Hub-Signature")
    if not signature:
        return False

    body = await request.body()
    secret = os.getenv("FACEBOOK_APP_SECRET")
    expected_hmac = hmac.new(
        secret.encode(), body, hashlib.sha1
    ).hexdigest()
    expected_signature = f"sha1={expected_hmac}"

    return hmac.compare_digest(signature, expected_signature)

async def register_webhooks(page_id: str, access_token: str):
    """
    Registers webhooks for a specific Facebook page.
    """
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
    """
    Retrieves existing webhook subscriptions for a page.
    """
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("data", [])
```

**Why?**
- **Token Exchange**: `exchange_code_for_token` fetches the user access token for OAuth, used in the callback.
- **Data Fetching**: `get_facebook_data` retrieves comprehensive non-sensitive page data (`id`, `name`, `category`, `about`, etc.) and the page access token (for server-side use).
- **Webhook Verification**: `verify_webhook` ensures incoming webhook requests are authentic using HMAC signatures.
- **Webhook Registration**: `register_webhooks` subscribes to `name,category` events, requiring `pages_manage_metadata`.
- **Subscription Check**: `get_existing_subscriptions` prevents duplicate webhook registrations.
- **Security**: Excludes sensitive tokens from responses, with error logging for debugging.

### Step 3: Update `facebook_oauth/routes.py`
Configure the webhook endpoint, OAuth flow, and integrated test for webhooks, ensuring a secure response without tokens.

**Updated File: `facebook_oauth/routes.py`**
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
import httpx

router = APIRouter()

@router.get("/login")
async def start_oauth():
    client_id = os.getenv("FACEBOOK_APP_ID")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
    scope = "pages_messaging,pages_show_list,pages_manage_metadata"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Facebook app config missing")

    if not re.match(r'^\d{15,20}$', client_id):
        raise HTTPException(status_code=500, detail="Invalid FACEBOOK_APP_ID format")

    state = generate_state_token()

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

    validate_state_token(incoming_state)

    token_data = await exchange_code_for_token(code)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    # Store user access token for server-side use
    os.environ["FACEBOOK_USER_ACCESS_TOKEN"] = token_data["access_token"]

    pages = await get_facebook_data(token_data["access_token"])

    # Store page access tokens and register webhooks
    for page in pages.get("data", []):
        page_id = page["id"]
        os.environ[f"FACEBOOK_ACCESS_TOKEN_{page_id}"] = page["access_token"]

        # Register webhooks if not already subscribed
        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category' already exists for page {page_id}")

    # Test webhook
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

    # Prepare response with non-sensitive page details
    safe_pages = {
        "data": [
            {k: v for k, v in page.items() if k != "access_token"}
            for page in pages.get("data", [])
        ],
        "paging": pages.get("paging", {})
    }

    return JSONResponse(content={
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

        access_token_key = f"FACEBOOK_ACCESS_TOKEN_{page_id}"
        access_token = os.getenv(access_token_key)
        if not access_token:
            print(f"Access token not found for page {page_id}")
            continue

        print(f"Received webhook event for page {page_id}: {entry}")

    return {"status": "success"}

@router.get("/webhook")
async def verify_webhook_subscription(request: Request):
    """
    Verifies the webhook subscription with Facebook.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == os.getenv("FACEBOOK_VERIFY_TOKEN", "default_verify_token"):
        return challenge
    raise HTTPException(status_code=403, detail="Verification failed")
```

**Why?**
- **Login Endpoint**: Initiates OAuth with required scopes, including `pages_manage_metadata` for webhooks.
- **Callback Endpoint**: Stores user and page access tokens server-side, registers webhooks, tests the webhook endpoint, and returns non-sensitive page data (`id`, `name`, `category`, `about`, etc.) with a `webhook_test` result.
- **Webhook Endpoint**: Processes incoming events for `name` and `category` changes, using HMAC verification for security.
- **Verification Endpoint**: Handles Facebook’s webhook subscription handshake using `FACEBOOK_VERIFY_TOKEN`.
- **Security**: Excludes all tokens from the response, storing them in `os.environ` for internal use.

### Step 4: Configure Webhook in Facebook Developer Portal
**Action**: Set up the webhook in the Meta Developer Portal to receive page events.
1. Log into `developers.facebook.com` and navigate to your app (created in Subchapter 1.2).
2. In the left sidebar, under “Products”, add “Webhooks” (click “Add Product” if not already added).
3. Select “Page” as the webhook object.
4. In the “Webhooks” settings, click “Add Callback URL” and enter:
   - **Callback URL**: Your `FACEBOOK_WEBHOOK_ADDRESS` from `.env` (e.g., `https://your-app.com/facebook/webhook` or `http://localhost:5000/facebook/webhook` via ngrok for testing).
   - **Verify Token**: Your `FACEBOOK_VERIFY_TOKEN` from `.env`.
5. Click “Verify and Save”.
6. Subscribe to `name` and `category` fields under “Page Subscriptions”.

**Expected Output**: The portal confirms the webhook is verified, and your app starts receiving events for the specified fields.

**Screenshot Reference**: Webhooks settings page showing the “Page” webhook, Callback URL, and Verify Token fields.
**Why?**
- Configures Facebook to send real-time events to your `/facebook/webhook` endpoint.
- The `pages_manage_metadata` permission (from Subchapter 1.1) allows subscribing to `name,category`.
- Using ngrok for local testing ensures the webhook URL is publicly accessible.

### Step 5: Testing Preparation
To verify the webhook setup:
1. Update your `.env` file with `FACEBOOK_WEBHOOK_ADDRESS` and `FACEBOOK_VERIFY_TOKEN`.
2. Install dependencies: `pip install -r requirements.txt` (including `apscheduler` for later subchapters).
3. Run the app: `python app.py`.
4. Initiate the OAuth flow via `http://localhost:5000/facebook/login` (or Codespaces URL).
5. After authorization, check the `/facebook/callback` response for `webhook_test: {"status": "success"}` and non-sensitive page data.

Detailed testing is covered in Subchapter 2.3.

### Summary: Why This Subchapter Matters
- **Real-Time Updates**: Webhooks enable instant notifications for page metadata changes, keeping the sales bot’s data current.
- **Secure Design**: HMAC verification and CSRF protection ensure robust security, with tokens stored server-side.
- **Modular Code**: Reuses `shared/utils.py` for CSRF and adds webhook-specific utilities in `facebook_oauth/utils.py`.
- **Comprehensive Data**: Captures extensive non-sensitive page data for bot interactions.
- **Test Integration**: Automatic webhook testing during OAuth confirms functionality.

### Next Steps:
- Proceed to Subchapter 2.2 for polling setup to complement webhooks.
- Verify webhook notifications for page metadata changes via the `name` and `category` fields in Subchapter 2.3.