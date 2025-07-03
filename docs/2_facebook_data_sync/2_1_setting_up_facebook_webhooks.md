# Subchapter 2.1: Setting Up Facebook Webhooks for Real-Time Updates

## Introduction
Facebook webhooks enable your application to receive real-time notifications about page events, such as page name, description, or category changes, to keep your sales bot’s data up-to-date. This subchapter guides you through setting up a secure webhook endpoint in your FastAPI application, integrating HMAC verification, registering webhooks during the OAuth flow with appropriate permissions, and including an automatic test to verify functionality.

## Prerequisites
- Completed Facebook OAuth setup from Chapter 1.
- Your FastAPI application is running locally or in a production-like environment.
- Required permissions: `pages_show_list` and `pages_manage_metadata` for webhook subscriptions.
- `apscheduler` is installed (`pip install apscheduler`).

---

## Step 1: Configure Environment Variables
Ensure your `.env` file includes Facebook-specific variables required for webhook functionality and data syncing to DigitalOcean Spaces.

**Updated `.env` Example**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# DigitalOcean Spaces credentials
SPACES_BUCKET=your_spaces_bucket
SPACES_REGION=nyc3
SPACES_ACCESS_KEY=your_spaces_access_key
SPACES_SECRET_KEY=your_spaces_secret_key
```

**Notes**:
- Replace placeholders (e.g., `your_facebook_app_id`) with actual values from your Facebook Developer App.
- `FACEBOOK_WEBHOOK_ADDRESS` must be a publicly accessible URL in production (e.g., via ngrok for testing).
- `FACEBOOK_VERIFY_TOKEN` is a custom string you define for webhook verification.

## Step 2: Update `facebook_oauth/utils.py`
Add utility functions to support webhook registration and verification for Facebook page events, subscribing to `name`, `description`, and `category` fields to capture relevant page metadata.

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
        response.raise_for_status()
        return response.json()

async def get_facebook_data(access_token: str):
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {
        "access_token": access_token,
        "fields": "id,name,description,category,access_token"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
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
        "subscribed_fields": "name,description,category",
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

## Step 3: Update `facebook_oauth/routes.py`
Configure the webhook endpoint, OAuth flow, and integrated test for webhooks.

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
from digitalocean_integration.utils import has_data_changed, upload_to_spaces
import boto3
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

    pages = await get_facebook_data(token_data["access_token"])

    # Store access token for each page and register webhooks
    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
        aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
    )
    for page in pages.get("data", []):
        page_id = page["id"]
        os.environ[f"FACEBOOK_ACCESS_TOKEN_{page_id}"] = page["access_token"]

        # Register webhooks if not already subscribed
        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", "").split(",") for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,description,category' already exists for page {page_id}")

        # Sync initial page data to Spaces
        spaces_key = f"facebook/{page_id}/page_data.json"
        if has_data_changed(pages, spaces_key, s3_client):
            upload_to_spaces(pages, spaces_key, s3_client)
            print(f"Uploaded initial data to Spaces for page {page_id}")
        else:
            print(f"No upload needed for page {page_id}: Data unchanged")

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

    return JSONResponse(content={
        "token_data": token_data,
        "pages": pages,
        "webhook_test": webhook_test_result
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

        print(f"Received webhook event for page {page_id}: {entry}")

        try:
            page_data = await get_facebook_data(access_token)
            spaces_key = f"facebook/{page_id}/page_data.json"
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

---

#### Summary
This subchapter sets up a webhook system focused on non-sensitive data (e.g., page name, description, and category changes), integrating HMAC verification, webhook registration during the OAuth flow, and an automatic test to verify functionality. The system syncs page data to DigitalOcean Spaces, reusing utilities from the Shopify integration for consistency.

#### Next Steps
- Proceed to Subchapter 2.2 for polling setup.
- Verify webhook notifications for page metadata changes via the `name`, `description`, and `category` fields.