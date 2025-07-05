# Chapter 4: Facebook Data Sync
## Subchapter 4.3: Implementing Daily Polling

### Introduction
While webhooks (Subchapters 4.1 and 4.2) provide real-time updates for Facebook page metadata (e.g., `name`, `category`) and messages, they can miss events due to network issues or downtime. This subchapter implements a daily polling mechanism to fetch both page metadata and conversation history periodically, ensuring the GPT Messenger sales bot’s data remains up-to-date. Polling uses the SQLite-based `TokenStorage` (Chapter 3) for token and UUID retrieval and stores data in temporary files (`facebook/<page_id>/page_metadata.json` for metadata and `facebook/<page_id>/conversations/<sender_id>.json` for conversation payloads). We integrate polling into the OAuth flow for testing and schedule it daily using APScheduler, maintaining non-sensitive metadata and full conversation payloads consistent with Subchapters 4.1 and 4.2. The `facebook` directory reflects both metadata and messaging, aligning with the final structure in Chapter 6 (`users/<uuid>/facebook/<page_id>/...`). Testing is covered in Subchapter 4.4.

### Prerequisites
- Completed Chapters 1–3 (Facebook OAuth, Shopify OAuth, Persistent Storage and User Identification) and Subchapters 4.1–4.2.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) and `STATE_TOKEN_SECRET` set in `.env` (Chapter 1, Subchapter 4.1).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Permissions `pages_messaging`, `pages_show_list`, and `pages_manage_metadata` configured in the Meta Developer Portal (Chapter 1, Subchapter 4.2).

---

### Step 1: Why Daily Polling?
Polling complements webhooks by:
- Fetching page metadata (`name`, `category`) daily to catch missed webhook events.
- Retrieving conversation history via the `/conversations` endpoint to ensure complete message records, storing full payloads as in Subchapter 4.2.
- Using `TokenStorage` for consistent token/UUID retrieval (Chapter 3).
- Ensuring data availability for the sales bot (e.g., page details, customer interactions).
- Supporting multiple users via SQLite-based storage and temporary files.

### Step 2: Update Project Structure
The project structure remains as defined in Subchapters 4.1 and 4.2:
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
- `app.py` integrates APScheduler for scheduling.
- `shared/sessions.py` and `shared/tokens.py` support persistent storage (Chapter 3).
- No dependencies from future chapters (e.g., `digitalocean_integration` or `boto3`) are included.
- The `facebook` directory is used for temporary storage, reflecting both metadata (`page_metadata.json`) and conversations (`conversations/<sender_id>.json`), aligning with `users/<uuid>/facebook/<page_id>/...` in Chapter 6.

### Step 3: Update `app.py`
Add APScheduler to schedule daily polling for both metadata and conversations, using environment validation.

```python
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from facebook_integration.utils import daily_poll
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
    daily_poll,
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
- **Scheduler**: Uses APScheduler to run `daily_poll` daily at midnight.
- **Shutdown Hook**: Ensures clean scheduler shutdown.
- **Environment Validation**: Includes webhook variables from Subchapter 4.1.
- **Excludes Future Dependencies**: No references to Spaces or `boto3` (Chapter 6).

### Step 4: Update `facebook_integration/utils.py`
Add a `poll_facebook_conversations` function to fetch conversation history via the `/conversations` endpoint, storing full payloads. Update `poll_facebook_data` and `daily_poll` to handle both metadata and conversations.

```python
import os
import httpx
import hmac
import hashlib
import json
from datetime import datetime
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
        "subscribed_fields": "name,category,messages",
        "callback_url": webhook_address,
        "verify_token": os.getenv("FACEBOOK_VERIFY_TOKEN", "default_verify_token")
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, params=params)
        if response.status_code == 200:
            print(f"Webhook registered for page {page_id} with fields: name,category,messages")
        else:
            print(f"Failed to register webhook for page {page_id}: {response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to register webhook: {response.text}")

async def get_existing_subscriptions(page_id: str, access_token: str):
    url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("data", [])

async def poll_facebook_data(page_id: str) -> dict:
    try:
        user_access_token = token_storage.get_token("FACEBOOK_USER_ACCESS_TOKEN")
        if not user_access_token:
            raise HTTPException(status_code=500, detail="User access token not found")
        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            raise HTTPException(status_code=500, detail=f"User UUID not found for page {page_id}")
        page_data = await get_facebook_data(user_access_token)
        os.makedirs(f"facebook/{page_id}", exist_ok=True)
        with open(f"facebook/{page_id}/page_metadata.json", "w") as f:
            json.dump(page_data, f)
        print(f"Wrote metadata to facebook/{page_id}/page_metadata.json for page {page_id}")
        return {"status": "success"}
    except Exception as e:
        print(f"Failed to poll metadata for page {page_id}: {str(e)}")
        return {"status": "error", "message": str(e)}

async def poll_facebook_conversations(access_token: str, page_id: str) -> dict:
    try:
        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            raise HTTPException(status_code=500, detail=f"User UUID not found for page {page_id}")
        url = f"https://graph.facebook.com/v19.0/{page_id}/conversations"
        params = {
            "access_token": access_token,
            "fields": "id,updated_time,participants,messages{message,from,to,created_time,id}"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                print(f"Failed to fetch conversations for page {page_id}: {response.text}")
                raise HTTPException(status_code=500, detail=f"Conversation fetch failed: {response.text}")
            conversations = response.json().get("data", [])
            for conversation in conversations:
                sender_id = next((p["id"] for p in conversation["participants"]["data"] if p["id"] != page_id), None)
                if not sender_id:
                    continue
                conversation_file = f"facebook/{page_id}/conversations/{sender_id}.json"
                existing_payloads = []
                is_new_conversation = False
                try:
                    with open(conversation_file, "r") as f:
                        existing_payloads = json.load(f)
                        print(f"Updating conversation for sender {sender_id} on page {page_id}")
                except FileNotFoundError:
                    is_new_conversation = True
                    print(f"New conversation polled for sender {sender_id} on page {page_id}")

                for message in conversation.get("messages", {}).get("data", []):
                    message_payload = {
                        "sender": {"id": message["from"]["id"]},
                        "recipient": {"id": message["to"]["data"][0]["id"]},
                        "timestamp": int(1000 * (datetime.strptime(message["created_time"], "%Y-%m-%dT%H:%M:%S%z").timestamp())),
                        "message": {"mid": message["id"], "text": message["message"]}
                    }
                    if not any(p["message"]["mid"] == message_payload["message"]["mid"] for p in existing_payloads):
                        existing_payloads.append(message_payload)

                os.makedirs(f"facebook/{page_id}/conversations", exist_ok=True)
                with open(conversation_file, "w") as f:
                    json.dump(existing_payloads, f)
                print(f"Wrote conversation payloads to {conversation_file} for sender {sender_id} on page {page_id} (new: {is_new_conversation})")
            return {"status": "success"}
    except Exception as e:
        print(f"Failed to poll conversations for page {page_id}: {str(e)}")
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
                result = await poll_facebook_data(page_id)
                if result["status"] == "success":
                    print(f"Polled metadata for page {page_id}: Success")
                else:
                    print(f"Metadata polling failed for page {page_id}: {result['message']}")
                conv_result = await poll_facebook_conversations(access_token, page_id)
                if conv_result["status"] == "success":
                    print(f"Polled conversations for page {page_id}: Success")
                else:
                    print(f"Conversation polling failed for page {page_id}: {conv_result['message']}")
        except Exception as e:
            print(f"Daily poll failed for page {page_id}: {str(e)}")
```

**Why?**
- **Polling Functions**: `poll_facebook_data` fetches metadata, storing in `facebook/<page_id>/page_metadata.json`. `poll_facebook_conversations` fetches conversation history, storing full payloads in `facebook/<page_id>/conversations/<sender_id>.json`, consistent with Subchapter 4.2.
- **Conversation Tracking**: Checks file existence to identify new vs. continuing conversations, appending unique payloads based on `message.mid`.
- **Daily Poll**: Schedules both metadata and conversation polling daily, using `TokenStorage` for tokens/UUIDs.
- **Temporary Storage**: Uses `facebook/<page_id>/...`, preparing for Spaces (`users/<uuid>/facebook/<page_id>/...`) in Chapter 6.
- **Error Handling**: Returns status and error messages for debugging.

### Step 5: Update `facebook_integration/routes.py`
Integrate polling tests into the OAuth flow, testing both metadata and conversation polling.

```python
import os
import re
import json
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data, verify_webhook, register_webhooks, get_existing_subscriptions, poll_facebook_data, poll_facebook_conversations
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

    webhook_test_results = []
    polling_test_results = []
    for page in pages.get("data", []):
        page_id = page["id"]
        token_storage.store_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}", page["access_token"], type="token")
        token_storage.store_token(f"PAGE_UUID_{page_id}", user_uuid, type="uuid")

        existing_subscriptions = await get_existing_subscriptions(page_id, page["access_token"])
        if not any("name" in sub.get("subscribed_fields", []) for sub in existing_subscriptions):
            await register_webhooks(page_id, page["access_token"])
        else:
            print(f"Webhook subscription for 'name,category,messages' already exists for page {page_id}")

        # Temporary file storage for metadata
        os.makedirs(f"facebook/{page_id}", exist_ok=True)
        with open(f"facebook/{page_id}/page_metadata.json", "w") as f:
            json.dump(pages, f)
        print(f"Wrote metadata to facebook/{page_id}/page_metadata.json for page {page_id}")

        # Test metadata webhook
        test_metadata_payload = {
            "object": "page",
            "entry": [{"id": page_id, "changes": [{"field": "name", "value": "Test Page"}]}]
        }
        secret = os.getenv("FACEBOOK_APP_SECRET")
        hmac_signature = f"sha1={hmac.new(secret.encode(), json.dumps(test_metadata_payload).encode(), hashlib.sha1).hexdigest()}"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('FACEBOOK_WEBHOOK_ADDRESS', 'http://localhost:5000/facebook/webhook')}",
                headers={"X-Hub-Signature": hmac_signature, "Content-Type": "application/json"},
                data=json.dumps(test_metadata_payload)
            )
            webhook_test_result = response.json() if response.status_code == 200 else {
                "status": "error", "message": response.text
            }
            webhook_test_results.append({"page_id": page_id, "type": "metadata", "result": webhook_test_result})
            print(f"Metadata webhook test result for page {page_id}: {webhook_test_result}")

        # Test message webhook
        test_message_payload = {
            "object": "page",
            "entry": [
                {
                    "id": page_id,
                    "messaging": [
                        {
                            "sender": {"id": "test_user_id"},
                            "recipient": {"id": page_id},
                            "timestamp": 1697051234567,
                            "message": {"mid": "test_mid", "text": "Test message"}
                        }
                    ]
                }
            ]
        }
        hmac_signature = f"sha1={hmac.new(secret.encode(), json.dumps(test_message_payload).encode(), hashlib.sha1).hexdigest()}"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('FACEBOOK_WEBHOOK_ADDRESS', 'http://localhost:5000/facebook/webhook')}",
                headers={"X-Hub-Signature": hmac_signature, "Content-Type": "application/json"},
                data=json.dumps(test_message_payload)
            )
            webhook_test_result = response.json() if response.status_code == 200 else {
                "status": "error", "message": response.text
            }
            webhook_test_results.append({"page_id": page_id, "type": "messages", "result": webhook_test_result})
            print(f"Message webhook test result for page {page_id}: {webhook_test_result}")

        # Test polling
        metadata_result = await poll_facebook_data(page_id)
        polling_test_results.append({"page_id": page_id, "type": "metadata", "result": metadata_result})
        print(f"Metadata polling test result for page {page_id}: {metadata_result}")
        conv_result = await poll_facebook_conversations(page["access_token"], page_id)
        polling_test_results.append({"page_id": page_id, "type": "conversations", "result": conv_result})
        print(f"Conversation polling test result for page {page_id}: {conv_result}")

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
        "webhook_test": webhook_test_results,
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

        # Handle message events
        if "messaging" in entry:
            for message_event in entry.get("messaging", []):
                sender_id = message_event.get("sender", {}).get("id")
                recipient_id = message_event.get("recipient", {}).get("id")
                if not sender_id or not recipient_id or sender_id == page_id:
                    continue

                # Store the entire messaging event payload
                conversation_file = f"facebook/{page_id}/conversations/{sender_id}.json"
                conversation = []
                is_new_conversation = False
                try:
                    with open(conversation_file, "r") as f:
                        conversation = json.load(f)
                        print(f"Continuing conversation for sender {sender_id} on page {page_id}")
                except FileNotFoundError:
                    is_new_conversation = True
                    print(f"New conversation started for sender {sender_id} on page {page_id}")

                conversation.append(message_event)
                os.makedirs(f"facebook/{page_id}/conversations", exist_ok=True)
                with open(conversation_file, "w") as f:
                    json.dump(conversation, f)
                print(f"Wrote conversation payload to {conversation_file} for sender {sender_id} on page {page_id} (new: {is_new_conversation})")

        # Handle metadata events (name, category)
        if "changes" in entry:
            try:
                page_data = await get_facebook_data(access_token)
                os.makedirs(f"facebook/{page_id}", exist_ok=True)
                with open(f"facebook/{page_id}/page_metadata.json", "w") as f:
                    json.dump(page_data, f)
                print(f"Wrote metadata to facebook/{page_id}/page_metadata.json for page {page_id}")
            except Exception as e:
                print(f"Failed to write metadata for page {page_id}: {str(e)}")

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
- **Login Endpoint**: Reuses `SessionStorage` for UUID retrieval (Chapter 3).
- **Callback Endpoint**: Tests both metadata and conversation polling, storing results in `polling_test_results`, alongside webhook tests from Subchapter 4.2.
- **Webhook Endpoint**: Unchanged from Subchapter 4.2, included for completeness.
- **Security**: Excludes tokens, uses HMAC verification, and clears sessions.
- **Temporary Storage**: Uses `facebook/<page_id>/page_metadata.json` and `facebook/<page_id>/conversations/<sender_id>.json`, preparing for Spaces in Chapter 6 (`users/<uuid>/facebook/<page_id>/...`).
- **Polling Tests**: Verifies both data types during OAuth, preparing for Subchapter 4.4.

### Step 6: Update `requirements.txt`
Add APScheduler for polling, keeping only dependencies up to this point.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
```

**Why?**
- `apscheduler` enables daily polling, introduced in this subchapter.
- `cryptography` supports `TokenStorage` and `SessionStorage` (Chapter 3).
- Excludes `boto3` (Chapter 6) and other future dependencies.

### Step 7: Update `.gitignore`
Ensure SQLite databases and temporary files are excluded.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
facebook/
```

**Why?**
- Excludes `tokens.db`, `sessions.db`, and temporary files (`facebook/<page_id>/...`) to prevent committing sensitive data.
- Covers metadata (`page_metadata.json`) and conversation files (`conversations/<sender_id>.json`) in the `facebook` directory.

### Step 8: Testing Preparation
To verify polling:
1. Update `.env` with required variables (Subchapter 4.1).
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie.
5. Run the Facebook OAuth flow to test polling.
6. Testing details are in Subchapter 4.4.

**Expected Output** (example logs during OAuth):
```
Webhook subscription for 'name,category,messages' already exists for page 101368371725791
Wrote metadata to facebook/101368371725791/page_metadata.json for page 101368371725791
Metadata webhook test result for page 101368371725791: {'status': 'success'}
Message webhook test result for page 101368371725791: {'status': 'success'}
Metadata polling test result for page 101368371725791: {'status': 'success'}
Conversation polling test result for page 101368371725791: {'status': 'success'}
```

### Summary: Why This Subchapter Matters
- **Data Redundancy**: Polling ensures metadata and conversation data are complete, complementing webhooks.
- **UUID Integration**: Uses `TokenStorage` for multi-platform linking.
- **Scalability**: Async polling and scheduling support production environments.
- **Temporary Storage**: Uses `facebook/<page_id>/...`, preparing for cloud storage enhancements in Chapter 6 (`users/<uuid>/facebook/<page_id>/...`).
- **Conversation Tracking**: Maintains consistency with webhook payload storage, tracking new vs. continuing conversations.

### Next Steps:
- Test webhooks and polling for both metadata and conversations (Subchapter 4.4).
- Proceed to Chapter 5 for Shopify data synchronization.