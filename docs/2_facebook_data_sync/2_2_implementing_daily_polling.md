# Subchapter 2.2: Setting Up Facebook Polling for Data Consistency

## Introduction
While webhooks provide real-time updates for Facebook page events, a daily polling mechanism ensures your sales bot’s data remains consistent as a backup, capturing non-sensitive metadata like page names, descriptions, and categories. This subchapter guides you through setting up a polling system in your FastAPI application, defining a reusable polling function, scheduling a daily poll, and including an automatic test during the OAuth flow, mirroring the webhook test format.

## Prerequisites
- Completed Subchapter 2.1: Setting Up Facebook Webhooks.
- Your FastAPI application is running locally or in a production-like environment.
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) are set in your `.env` file.
- `apscheduler` is installed (`pip install apscheduler`).

---

## Step 1: Configure Environment Variables
Ensure your `.env` file includes the necessary variables for Facebook API access, as set up in Subchapter 2.1. No additional variables are required for polling.

**Updated `.env` Example**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=my_secure_verify_token
```

**Notes**:
- Verify that access tokens for pages (e.g., `FACEBOOK_ACCESS_TOKEN_<page_id>`) are stored in the environment during the OAuth flow, as set in Subchapter 2.1.
- No DigitalOcean Spaces variables are needed, as data syncing is covered in a later chapter.

## Step 2: Update `facebook_oauth/utils.py`
Add the `poll_facebook_data` function for core polling logic and `daily_poll` for the scheduled task.

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

async def poll_facebook_data(access_token: str, page_id: str) -> dict:
    """
    Polls Facebook data for a single page and returns the result.
    """
    try:
        await get_facebook_data(access_token)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def daily_poll():
    """
    Polls Facebook once a day for each authenticated page to ensure data consistency.
    """
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

## Step 3: Update `facebook_oauth/routes.py`
Enhance the OAuth callback to include the polling test after the webhook test.

**Updated File: `facebook_oauth/routes.py`**
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
    for page in pages.get("data", []):
        page_id = page["id"]
        os.environ[f"FACEBOOK_ACCESS_TOKEN_{page_id}"] = page["access_token"]

        # Register webhooks if not already subscribed
        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", "").split(",") for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,description,category' already exists for page {page_id}")

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

    # Test polling
    polling_test_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        access_token = os.getenv(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
        polling_result = await poll_facebook_data(access_token, page_id)
        polling_test_results.append({"page_id": page_id, "result": polling_result})
        print(f"Polling test result for page {page_id}: {polling_result}")

    return JSONResponse(content={
        "token_data": token_data,
        "pages": pages,
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

## Step 4: Update `app.py` with Polling Scheduler
Extend the app to include the Facebook polling scheduler alongside Shopify’s.

**Updated File: `app.py`**
```python
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from shopify_integration.utils import daily_poll as shopify_daily_poll
from facebook_oauth.utils import daily_poll as facebook_daily_poll
import atexit

load_dotenv()

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")
app.include_router(shopify_oauth_router, prefix="/shopify")

@app.get("/")
async def root():
    return {"status": "ok"}

# Set up the scheduler to run daily at midnight
scheduler = BackgroundScheduler()
scheduler.add_job(shopify_daily_poll, CronTrigger(hour=0, minute=0))
scheduler.add_job(facebook_daily_poll, CronTrigger(hour=0, minute=0))
scheduler.start()

# Ensure the scheduler shuts down when the app stops
atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

---

#### Summary
This subchapter sets up a daily polling backup system using a reusable `poll_facebook_data` function, scheduled with `daily_poll`, and includes an automatic test during the OAuth flow, mirroring the webhook test format with `{"status": "success"}`. The system fetches page metadata to ensure data consistency, preparing for DigitalOcean Spaces integration in the next chapter.

#### Next Steps
- Proceed to Subchapter 2.3 for testing webhook and polling functionality.
- Verify polling captures page metadata changes via the fetched data.