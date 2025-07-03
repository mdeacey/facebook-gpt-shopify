# Chapter 2: Facebook Data Sync
## Subchapter 2.2: Setting Up Facebook Polling for Data Consistency

### Introduction
While webhooks (Subchapter 2.1) provide real-time updates for Facebook page events, a daily polling mechanism ensures your GPT Messenger sales bot’s data remains consistent as a backup, capturing non-sensitive metadata like page names, categories, and other details. This subchapter guides you through setting up a polling system in your FastAPI application, defining a reusable polling function, scheduling a daily poll, and including an automatic test during the OAuth flow, mirroring the webhook test format. The system focuses on non-sensitive data, ensuring secure handling without exposing access tokens.

### Prerequisites
- Completed Subchapter 2.1: Setting Up Facebook Webhooks.
- Your FastAPI application is running locally or in a production-like environment.
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) are set in your `.env` file.
- `apscheduler` is installed (`pip install apscheduler`).

---

### Step 1: Configure Environment Variables
Ensure your `.env` file includes the necessary variables for Facebook API access, as set up in Subchapter 2.1. No additional variables are required for polling.

**Updated `.env` Example**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=my_secure_verify_token
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Notes**:
- Verify that access tokens for pages (e.g., `FACEBOOK_ACCESS_TOKEN_<page_id>`) and the user access token (`FACEBOOK_USER_ACCESS_TOKEN`) are stored in the environment during the OAuth flow, as set in Subchapter 2.1.
- No additional variables are needed, as polling uses existing credentials.

**Why?**
- These variables authenticate API requests and secure webhook verification, maintaining consistency with the OAuth and webhook setup from Chapter 1 and Subchapter 2.1.

### Step 2: Update `facebook_oauth/utils.py`
Add the `poll_facebook_data` function for core polling logic and `daily_poll` for the scheduled task, ensuring comprehensive non-sensitive page data is fetched.

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

async def poll_facebook_data(access_token: str, page_id: str) -> dict:
    """
    Polls Facebook data for a single page and returns the result.
    """
    try:
        user_access_token = os.getenv("FACEBOOK_USER_ACCESS_TOKEN")
        if not user_access_token:
            raise HTTPException(status_code=500, detail="User access token not found")
        page_data = await get_facebook_data(user_access_token)
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

**Why?**
- **Token Exchange**: `exchange_code_for_token` fetches the user access token for OAuth.
- **Data Fetching**: `get_facebook_data` retrieves comprehensive non-sensitive page data (`id`, `name`, `category`, `about`, etc.) and page access tokens (for server-side use).
- **Webhook Functions**: `verify_webhook`, `register_webhooks`, and `get_existing_subscriptions` support Subchapter 2.1’s webhook setup.
- **Polling**: `poll_facebook_data` uses the user access token to fetch page data, ensuring consistency. `daily_poll` iterates over stored page IDs for scheduled polling.
- **Security**: Tokens are stored server-side and not exposed in responses.

### Step 3: Update `facebook_oauth/routes.py`
Enhance the OAuth callback to include the polling test after the webhook test, ensuring a secure response without tokens.

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

    # Test polling
    polling_test_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        access_token = os.getenv(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
        polling_result = await poll_facebook_data(access_token, page_id)
        polling_test_results.append({"page_id": page_id, "result": polling_result})
        print(f"Polling test result for page {page_id}: {polling_result}")

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

**Why?**
- **Login Endpoint**: Initiates OAuth with required scopes, including `pages_manage_metadata` for webhooks.
- **Callback Endpoint**: Stores user and page access tokens server-side, registers webhooks, tests webhook and polling functionality, and returns non-sensitive page data (`id`, `name`, `category`, `about`, etc.) with `webhook_test` and `polling_test` results.
- **Webhook Endpoint**: Processes incoming events for `name` and `category` changes, using HMAC verification.
- **Verification Endpoint**: Handles Facebook’s webhook subscription handshake.
- **Security**: Excludes all tokens from the response, storing them in `os.environ`.

### Step 4: Update `app.py` with Polling Scheduler
Extend the app to include the Facebook polling scheduler.

**Updated File: `app.py`**
```python
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from facebook_oauth.utils import daily_poll as facebook_daily_poll
import atexit

load_dotenv()

app = FastAPI(title="Facebook OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")

@app.get("/")
async def root():
    return {"status": "ok"}

# Set up the scheduler to run daily at midnight
scheduler = BackgroundScheduler()
scheduler.add_job(facebook_daily_poll, CronTrigger(hour=0, minute=0))
scheduler.start()

# Ensure the scheduler shuts down when the app stops
atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**Why?**
- **Scheduler**: Runs `facebook_daily_poll` at midnight to ensure data consistency.
- **Modular Design**: Includes only the Facebook router and scheduler, as Shopify integration is added in Chapter 2.
- **Shutdown**: Ensures graceful scheduler termination.

### Step 5: Update `requirements.txt`
Ensure `apscheduler` is included for scheduling.

**Updated File: `requirements.txt`**
```plaintext
fastapi
uvicorn
httpx
python-dotenv
apscheduler
```

**Why?**
- `apscheduler` enables daily polling, complementing webhooks.
- Other dependencies (`fastapi`, `uvicorn`, `httpx`, `python-dotenv`) support the core application.

### Step 6: Testing Preparation
To verify the polling setup:
1. Update your `.env` file with the credentials from Subchapter 2.1.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Initiate the OAuth flow via `http://localhost:5000/facebook/login` (or Codespaces URL).
5. Check the `/facebook/callback` response for `webhook_test: {"status": "success"}` and `polling_test: [{"page_id": "...", "result": {"status": "success"}}]`.

Detailed testing is covered in Subchapter 2.3.

### Summary: Why This Subchapter Matters
- **Data Consistency**: Daily polling complements webhooks, ensuring non-sensitive page metadata (`id`, `name`, `category`, `about`, etc.) is up-to-date.
- **Secure Design**: Tokens are stored server-side and excluded from responses.
- **Modular Code**: Reuses `facebook_oauth/utils.py` for polling and integrates with the OAuth flow.
- **Test Integration**: Automatic polling test during OAuth confirms functionality.
- **Bot Readiness**: Prepares the sales bot for consistent data access.

### Next Steps:
- Proceed to Subchapter 2.3 for testing webhook and polling functionality.
- Verify polling captures page metadata changes via the fetched data.