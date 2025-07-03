# Chapter 4: Facebook Data Sync
## Subchapter 4.2: Implementing Daily Polling for Redundancy

### Introduction
While webhooks (Subchapter 4.1) provide real-time updates for Facebook page metadata (e.g., name, category), they can miss events due to network issues or downtime. This subchapter implements a daily polling mechanism to fetch page data periodically, ensuring the GPT Messenger sales bot’s data remains up-to-date. Polling uses the same UUID-based identification from the session-based mechanism (Chapter 3) as webhooks, storing data temporarily in `facebook/<page_id>/page_data.json` to prepare for cloud storage in a later chapter. We integrate polling into the OAuth flow for testing and schedule it daily using APScheduler, maintaining non-sensitive metadata for secure, production-ready operation across multiple users.

### Prerequisites
- Completed Chapters 1–3 (Facebook OAuth, Shopify OAuth, UUID/session management).
- Webhook setup completed (Subchapter 4.1).
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- Page access tokens (`FACEBOOK_ACCESS_TOKEN_<page_id>`) and UUID mappings (`PAGE_UUID_<page_id>`) stored in the environment.

---

### Step 1: Why Daily Polling?
Polling complements webhooks by:
- Fetching page metadata daily to catch missed webhook events.
- Using the same UUID-based structure for consistency with webhooks.
- Ensuring data availability for the sales bot (e.g., page name, contact details).
- Supporting multiple users via session-based UUID retrieval.

### Step 2: Update Project Structure
The project structure remains as defined in Chapters 1–3, with polling logic added to `facebook_integration/utils.py`:
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
- `facebook_integration/utils.py` handles polling logic.
- `shared/session.py` supports session-based UUID retrieval (Chapter 3).
- `shared/utils.py` provides CSRF protection with UUID support.
- No new modules are needed, maintaining modularity.

### Step 3: Update `app.py`
Add APScheduler to schedule daily polling for all authenticated Facebook pages, using UUID mappings.

```python
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from facebook_integration.utils import daily_poll as facebook_daily_poll
import os
import atexit

load_dotenv()

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")
app.include_router(shopify_oauth_router, prefix="/shopify")

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Use /facebook/login or /shopify/{shop_name}/login"
    }

scheduler = BackgroundScheduler()
scheduler.add_job(
    facebook_daily_poll,
    trigger=CronTrigger(hour=0, minute=0),  # Run daily at midnight
    id="facebook_daily_poll",
    replace_existing=True
)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**Why?**
- **Scheduler**: Uses APScheduler to run `facebook_daily_poll` daily at midnight.
- **Shutdown Hook**: Ensures clean scheduler shutdown.
- **Modular Routers**: Supports both OAuth flows (Chapters 1–2).
- **CORS**: Enables frontend interaction.

### Step 4: Update `facebook_integration/utils.py`
Add a polling function to fetch page data, storing it temporarily with the UUID.

```python
import os
import httpx
import hmac
import hashlib
from fastapi import HTTPException, Request
import json

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

async def poll_facebook_data(access_token: str, page_id: str):
    try:
        page_data = await get_facebook_data(access_token)
        user_uuid = os.getenv(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            return {"status": "error", "message": f"User UUID not found for page {page_id}"}

        os.makedirs(f"facebook/{page_id}", exist_ok=True)
        with open(f"facebook/{page_id}/page_data.json", "w") as f:
            json.dump(page_data, f)
        print(f"Wrote data to facebook/{page_id}/page_data.json for page {page_id}")
        return {"status": "success"}
    except Exception as e:
        print(f"Failed to poll data for page {page_id}: {str(e)}")
        return {"status": "error", "message": str(e)}

def daily_poll():
    for key, value in os.environ.items():
        if key.startswith("FACEBOOK_ACCESS_TOKEN_") and key != "FACEBOOK_USER_ACCESS_TOKEN":
            page_id = key.replace("FACEBOOK_ACCESS_TOKEN_", "")
            access_token = value
            result = poll_facebook_data(access_token, page_id)
            print(f"Polled data for page {page_id}: {result['status']}")
```

**Why?**
- **Polling Function**: `poll_facebook_data` fetches page data, storing it in `facebook/<page_id>/page_data.json` using the UUID.
- **Daily Poll**: `daily_poll` iterates over stored page access tokens, calling `poll_facebook_data`.
- **Error Handling**: Returns status and error messages.
- **Temporary Storage**: Prepares for cloud storage in Chapter 6.

### Step 5: Update `facebook_integration/routes.py`
Integrate polling into the OAuth flow for immediate testing, using the session-based UUID.

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
        clear_session(session_id)

    token_data = await exchange_code_for_token(code)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    os.environ["FACEBOOK_USER_ACCESS_TOKEN"] = token_data["access_token"]

    pages = await get_facebook_data(token_data["access_token"])

    polling_test_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        os.environ[f"FACEBOOK_ACCESS_TOKEN_{page_id}"] = page["access_token"]
        os.environ[f"PAGE_UUID_{page_id}"] = user_uuid

        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subcriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category' already exists for page {page_id}")

        # Temporary file storage
        os.makedirs(f"facebook/{page_id}", exist_ok=True)
        with open(f"facebook/{page_id}/page_data.json", "w") as f:
            json.dump(pages, f)
        print(f"Wrote data to facebook/{page_id}/page_data.json for page {page_id}")

        # Polling test
        polling_result = await poll_facebook_data(page["access_token"], page_id)
        polling_test_results.append({"page_id": page_id, "result": polling_result})

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

        user_uuid = os.getenv(f"PAGE_UUID_{page_id}")
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
- **Login Endpoint**: Uses the `session_id` cookie to retrieve the UUID (Chapter 3).
- **Callback Endpoint**: Registers webhooks, tests polling and webhook endpoints, stores data temporarily, and returns results with `user_uuid`.
- **Webhook Endpoint**: Processes `name,category` events, storing updates in `facebook/<page_id>/page_data.json`.
- **Security**: Excludes tokens, uses HMAC, and clears sessions.

### Step 6: Update `requirements.txt`
Add APScheduler for scheduling.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
apscheduler
```

**Why?**
- `apscheduler` enables daily polling.
- Other dependencies support OAuth and webhooks.

### Step 7: Testing Preparation
To verify polling:
1. Update `.env` with `FACEBOOK_WEBHOOK_ADDRESS` and `FACEBOOK_VERIFY_TOKEN`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie.
5. Run the Facebook OAuth flow to test polling.
6. Testing details are in Subchapter 4.3.

### Summary: Why This Subchapter Matters
- **Data Redundancy**: Polling ensures data consistency alongside webhooks.
- **UUID Integration**: Uses the session-based UUID for multi-platform linking.
- **Scalability**: Async polling and scheduling support production environments.
- **Temporary Storage**: Prepares for cloud storage in a later chapter.

### Next Steps:
- Test webhooks and polling (Subchapter 4.3).
- Proceed to Chapter 5 for Shopify data synchronization.