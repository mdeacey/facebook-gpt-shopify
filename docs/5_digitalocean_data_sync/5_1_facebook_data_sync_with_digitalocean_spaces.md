# Chapter 5: DigitalOcean Integration

## Subchapter 5.1: Facebook Data Synchronization with DigitalOcean Spaces

### Introduction
This subchapter integrates DigitalOcean Spaces into your FastAPI application to store and keep Facebook page data updated for the GPT Messenger sales bot. We’ll configure environment variables, reuse utilities for checking data changes and uploading to Spaces, update the Facebook callback route to test webhook and polling functionality before uploading initial page data post-OAuth (if changed), enhance webhook handling for real-time updates, and leverage daily polling to ensure data consistency. This builds on the Facebook integration from Chapter 2, assuming a Facebook app and DigitalOcean Spaces setup (Subchapter 5.2). The focus is on code implementation, ensuring webhooks and polling work reliably before syncing non-sensitive page metadata (e.g., name, description, category) to Spaces, with uploads optimized to occur only when data differs.

---

### Step 1: Why Synchronize Facebook Data with DigitalOcean Spaces?
The sales bot requires up-to-date Facebook page data to manage page interactions and generate accurate recommendations. Storing and updating this data in DigitalOcean Spaces:
- **Ensures Fresh Data**: Combines initial uploads, real-time webhook updates, and daily polling for consistency.
- **Scales Efficiently**: Uses cloud storage to handle data for multiple pages, offloading the app.
- **Optimizes Resources**: Uploads only when data changes, reducing API calls and costs.

We’ll reuse the `digitalocean_integration/utils.py` functions (`compute_data_hash`, `has_data_changed`, `upload_to_spaces`), update the Facebook callback to test and upload data, enhance the webhook endpoint for incremental updates, and update polling to sync data, ensuring uploads only occur after successful tests and when data differs. The existing `generate_state_token` and `validate_state_token` functions from `shared/utils.py` secure the OAuth flow, so no additional state token logic is needed. All status fields (`webhook_test`, `polling_test`, `upload_status_result`) will use a consistent structure (`{"status": "success"}` or `{"status": "failed", "message": "..."}`) and `*_result` naming convention.

---

### Step 2: Project Structure
The codebase includes `facebook_integration`, `shopify_integration`, `digitalocean_integration`, and `shared` modules. We’ll update the Facebook integration to include Spaces syncing, leveraging existing utilities:

```
└── ./
    ├── digitalocean_integration/
    │   ├── __init__.py
    │   └── utils.py         # Contains Spaces utilities
    ├── facebook_integration/
    │   ├── __init__.py
    │   ├── routes.py        # Update for Spaces syncing
    │   └── utils.py         # Update for polling with Spaces
    ├── shopify_integration/
    │   ├── __init__.py
    │   ├── routes.py
    │   └── utils.py
    ├── shared/
    │   ├── __init__.py
    │   └── utils.py
    ├── .env
    └── app.py               # Schedules polls
```

- **`digitalocean_integration/utils.py`**: Handles data change checks and uploads, reused for Facebook.
- **`facebook_integration/routes.py`**: Updated to test webhooks/polling before initial upload and enhance webhook processing.
- **`facebook_integration/utils.py`**: Updated for polling with Spaces integration.
- **`.env`**: Extended with Spaces credentials (Step 3).
- **`app.py`**: Already schedules `facebook_daily_poll`.

This structure maintains modularity, keeping functionality grouped and reusable.

---

### Step 3: Configure Environment Variables
**Action**: Ensure `.env` includes DigitalOcean Spaces credentials alongside Facebook credentials.

**Why?**  
These variables authenticate Spaces operations, keeping sensitive data secure, consistent with the codebase’s approach. They’ll be used for Facebook data uploads, similar to Shopify’s setup in Chapter 3.

**Instructions**:  
Update `.env` with:

```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=my_secure_verify_token

# DigitalOcean Spaces credentials
SPACES_ACCESS_KEY=your_access_key
SPACES_SECRET_KEY=your_secret_key
SPACES_BUCKET=your_bucket_name
SPACES_REGION=nyc3
```

**Why?**  
- **New Variables**: Adds Spaces credentials, bucket, and region for Facebook data syncing.
- **Consistency**: Aligns with Shopify’s `.env` setup, ensuring centralized configuration.

---

### Step 4: Update `facebook_integration/utils.py`
**Action**: Update `poll_facebook_data` to upload page data to Spaces (if changed) and modify `daily_poll` to integrate Spaces syncing.

**Why?**  
Updating `poll_facebook_data` to include Spaces uploads aligns with Shopify’s polling, ensuring data consistency. `daily_poll` fetches data after a successful poll, maintaining efficiency. The consistent status structure (`{"status": "success"}`) is returned for compatibility with the OAuth callback.

**Instructions**:  
Update `facebook_integration/utils.py`, preserving existing functions and adding Spaces imports:

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
        "fields": "id,name,description,category,access_token"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def verify_webhook(request: Request) -> bool:
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
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("data", [])

async def poll_facebook_data(access_token: str, page_id: str) -> dict:
    """
    Polls Facebook data for a single page and uploads to Spaces if changed.
    """
    try:
        page_data = await get_facebook_data(access_token)
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=os.getenv("SPACES_REGION", "nyc3"),
            endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
        )
        spaces_key = f"facebook/{page_id}/page_data.json"
        if has_data_changed(page_data, spaces_key, s3_client):
            upload_to_spaces(page_data, spaces_key, s3_client)
            print(f"Polled and uploaded data for page {page_id}: Success")
        else:
            print(f"Polled data for page {page_id}: No upload needed, data unchanged")
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

---

### Step 5: Update `facebook_integration/routes.py`
**Action**: Modify the `/facebook/callback` endpoint to test webhook and polling functionality before uploading initial page data to Spaces (if changed), and enhance the `/facebook/webhook` endpoint for incremental updates.

**Why?**  
The callback, triggered post-OAuth, is ideal for initializing data storage, with `validate_state_token` ensuring security. We’ll verify webhook and polling functionality before uploading, returning `webhook_test`, `polling_test`, and `upload_status_result` with consistent structures. The webhook endpoint processes real-time updates, uploading only when data changes, aligning with Shopify’s approach.

**Instructions**:  
Update `facebook_integration/routes.py`:

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

    # Initialize S3 client for Spaces
    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
        aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
    )

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

    # Test polling and upload to Spaces
    polling_test_results = []
    upload_status_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        access_token = os.getenv(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
        polling_result = await poll_facebook_data(access_token, page_id)
        polling_test_results.append({"page_id": page_id, "result": polling_result})
        print(f"Polling test result for page {page_id}: {polling_result}")

        # Upload to Spaces if webhook and polling tests succeed
        upload_status_result = {"status": "failed", "message": "Tests failed"}
        if webhook_test_result.get("status") == "success" and polling_result.get("status") == "success":
            try:
                spaces_key = f"facebook/{page_id}/page_data.json"
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

    return JSONResponse(content={
        "token_data": token_data,
        "pages": pages,
        "webhook_test": webhook_test_result,
        "polling_test": polling_test_results,
        "upload_status_result": upload_status_results
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

### Step 6: Verify Existing Files
**Action**: Ensure `digitalocean_integration/utils.py` and `app.py` are unchanged, as they already support Spaces syncing and scheduling.

**Why?**  
- `digitalocean_integration/utils.py` contains `compute_data_hash`, `has_data_changed`, and `upload_to_spaces`, which are reused for Facebook.
- `app.py` schedules `facebook_daily_poll` at midnight, requiring no changes.

**Instructions**:  
No updates are needed for these files.

---

### Step 7: Update `requirements.txt`
**Action**: Ensure `boto3` is included for Spaces integration.

**Instructions**:  
Verify `requirements.txt`:

```plaintext
fastapi
uvicorn
httpx
python-dotenv
apscheduler
boto3
```

**Why?**  
- `boto3` is required for Spaces API interactions, already included for Shopify.

---

### Summary: Why This Subchapter Matters
- **Data Synchronization**: Integrates Spaces for Facebook page metadata (name, description, category), ensuring initial uploads, real-time webhook updates, and daily polling maintain consistency.
- **Efficient Design**: Uploads only when data changes, reusing `has_data_changed` and `upload_to_spaces`.
- **Modular Design**: Updates `facebook_integration` while leveraging `digitalocean_integration` utilities, maintaining codebase modularity.
- **Consistent Response**: Uses uniform status structures (`{"status": "success"}` or `{"status": "failed", "message": "..."}`) and `*_result` naming for `webhook_test`, `polling_test`, and `upload_status_result`.
- **Bot Readiness**: Ensures the sales bot has up-to-date page data for interactions and recommendations.

### Next Steps:
- Integrate Shopify data synchronization with Spaces (Subchapter 5.2).
- Set up a DigitalOcean Spaces bucket and obtain credentials (Subchapter 5.3).
- Test the full synchronization flow for Facebook data (Subchapter 5.4).