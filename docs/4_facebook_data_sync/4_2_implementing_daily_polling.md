# Chapter 4: Facebook Data Sync
## Subchapter 4.2: Implementing Daily Polling for Redundancy

### Introduction
While webhooks (Subchapter 4.1) provide real-time updates for Facebook page metadata (e.g., name, category), they can miss events due to network issues or downtime. This subchapter implements a daily polling mechanism to fetch page data periodically, ensuring the GPT Messenger sales bot’s data remains up-to-date. Polling uses the SQLite-based `TokenStorage` (Chapter 3) for token and UUID retrieval and temporarily stores data in `facebook/<page_id>/page_data.json`, preparing for cloud storage in Chapter 6. We integrate polling into the OAuth flow for testing and schedule it daily using APScheduler, maintaining non-sensitive metadata for secure, production-ready operation.

### Prerequisites
- Completed Chapters 1–3 and Subchapter 4.1.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) and `STATE_TOKEN_SECRET` set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).

---

### Step 1: Why Daily Polling?
Polling complements webhooks by:
- Fetching page metadata daily to catch missed webhook events.
- Using `TokenStorage` for consistent token/UUID retrieval (Chapter 3).
- Ensuring data availability for the sales bot (e.g., page name, contact details).
- Supporting multiple users via SQLite-based storage.

### Step 2: Update Project Structure
The project structure remains as defined in Subchapter 4.1:
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
- `facebook_integration/utils.py` handles polling logic using `TokenStorage`.
- `shared/sessions.py` and `shared/tokens.py` support persistent storage.
- Excludes Spaces integration (Chapter 6).

### Step 3: Update `app.py`
Add APScheduler to schedule daily polling for Facebook pages, using environment validation.

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

required_env_vars = [
    "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI",
    "FACEBOOK_WEBHOOK_ADDRESS", "FACEBOOK_VERIFY_TOKEN",
    "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_REDIRECT_URI",
    "STATE_TOKEN_SECRET"
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

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
- **Environment Validation**: Includes webhook variables.
- **Excludes Shopify Polling**: Shopify polling is introduced in Chapter 5.

### Step 4: Update `facebook_integration/utils.py`
Add a polling function using `TokenStorage`, storing data temporarily.

```python
import os
import httpx
import hmac
import hashlib
from fastapi import HTTPException, Request
import json
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

async def poll_facebook_data(access_token: str, page_id: str) -> dict:
    try:
        user_access_token = token_storage.get_token("FACEBOOK_USER_ACCESS_TOKEN")
        if not user_access_token:
            raise HTTPException(status_code=500, detail="User access token not found")
        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            raise HTTPException(status_code=500, detail=f"User UUID not found for page {page_id}")
        page_data = await get_facebook_data(user_access_token)
        os.makedirs(f"facebook/{page_id}", exist_ok=True)
        with open(f"facebook/{page_id}/page_data.json", "w") as f:
            json.dump(page_data, f)
        print(f"Wrote data to facebook/{page_id}/page_data.json for page {page_id}")
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
- **Polling Function**: `poll_facebook_data` fetches page data using `TokenStorage`, storing in temporary files.
- **Daily Poll**: `daily_poll` iterates over page tokens in `tokens.db`, calling `poll_facebook_data`.
- **Error Handling**: Returns status and error messages.
- **Temporary Storage**: Prepares for cloud storage in Chapter 6.

### Step 5: Update `facebook_integration/routes.py`
Integrate polling into the OAuth flow for immediate testing.

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
- **Login Endpoint**: Uses `SessionStorage` for UUID retrieval.
- **Callback Endpoint**: Registers webhooks, tests polling and webhook endpoints, stores data temporarily, and returns results with `user_uuid`.
- **Webhook Endpoint**: Processes `name,category` events, storing updates in temporary files.
- **Security**: Uses `TokenStorage`, excludes tokens, uses HMAC, and clears sessions.

### Step 6: Update `requirements.txt`
Add APScheduler for scheduling.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
```

**Why?**
- `apscheduler` enables daily polling.
- `cryptography` supports `TokenStorage` and `SessionStorage`.
- Excludes `boto3` (introduced in Chapter 6).

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
To verify polling:
1. Update `.env` with `FACEBOOK_WEBHOOK_ADDRESS` and `FACEBOOK_VERIFY_TOKEN`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie.
5. Run the Facebook OAuth flow to test polling.
6. Testing details are in Subchapter 4.3.

### Summary: Why This Subchapter Matters
- **Data Redundancy**: Polling ensures data consistency alongside webhooks.
- **UUID Integration**: Uses `TokenStorage` for multi-platform linking.
- **Scalability**: Async polling and scheduling support production environments.
- **Temporary Storage**: Prepares for cloud storage in Chapter 6.

### Next Steps:
- Test webhooks and polling (Subchapter 4.3).
- Proceed to Chapter 5 for Shopify data synchronization.