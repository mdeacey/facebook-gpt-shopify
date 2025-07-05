# Chapter 4: Facebook Data Sync
## Subchapter 4.2: Setting Up Facebook Messenger Webhooks

### Introduction
This subchapter extends the Facebook webhook system from Subchapter 4.1 to handle `messages` events, enabling the GPT Messenger sales bot to capture and store full conversation histories for each user-page interaction. The webhook endpoint processes incoming messages, stores the entire `messaging` event payload in a temporary file (`facebook/<page_id>/conversations/<sender_id>.json`), and identifies whether the message starts a new conversation or continues an existing one based on file existence. The conversation file is an array of raw payloads, ensuring all data (e.g., `sender`, `recipient`, `timestamp`, `message`) is preserved. Future replies by the bot will follow the same payload format for consistency. The system uses the UUID from the SQLite-based session mechanism (Chapter 3) to identify the user and updates the webhook registration to include the `messages` field, leveraging existing permissions (`pages_messaging`, `pages_show_list`, `pages_manage_metadata`) from Chapter 1. The `facebook` directory name reflects both metadata and messaging data, aligning with the final structure in Chapter 6 (`users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`). Polling for conversation history and testing are covered in Subchapters 4.3 and 4.4.

### Prerequisites
- Completed Chapters 1–3 (Facebook OAuth, Shopify OAuth, Persistent Storage and User Identification) and Subchapter 4.1.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) and `STATE_TOKEN_SECRET` set in `.env` (Chapter 1, Subchapter 4.1).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- A publicly accessible webhook URL for testing (e.g., via `ngrok http 5000`).

---

### Step 1: Verify Permissions
Ensure the Facebook app has the necessary permissions for message handling:
- Navigate to the Meta Developer Portal (`developers.facebook.com`), select your app (Subchapter 1.2), and verify that `pages_messaging` and `pages_manage_metadata` are included in the OAuth scope (set in Chapter 1).
- If needed, add `pages_messaging_subscriptions` for advanced messaging features under “Permissions and Features.” Request approval if the app is in Live Mode.

**Why?**
- `pages_messaging` allows the bot to receive messages via Messenger.
- `pages_manage_metadata` enables webhook subscriptions for `messages` events.
- Ensures compatibility with the existing OAuth flow from Chapter 1.

### Step 2: Configure Environment Variables
The `.env` file already includes the necessary variables from Subchapter 4.1. Confirm they are set correctly in your `.env` file:

**`.env.example`** (unchanged from Subchapter 4.1):
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback
# Webhook configuration
FACEBOOK_WEBHOOK_ADDRESS=http://localhost:5000/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# Database paths for SQLite storage
TOKEN_DB_PATH=./data/tokens.db
SESSION_DB_PATH=./data/sessions.db
```

**Notes**:
- `FACEBOOK_WEBHOOK_ADDRESS` must be publicly accessible (e.g., use `ngrok http 5000` for local testing).
- `FACEBOOK_VERIFY_TOKEN` is used for webhook verification (generated in Subchapter 4.1).
- **Production Note**: Use HTTPS for `FACEBOOK_WEBHOOK_ADDRESS` and a secure `STATE_TOKEN_SECRET`.

**Why?**
- Reuses existing configuration for OAuth and webhook verification.
- No new environment variables are needed, as message handling uses the same webhook endpoint as metadata.

### Step 3: Update Project Structure
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
- `facebook_integration/` is updated to handle `messages` events, reusing the existing webhook endpoint (`/facebook/webhook`).
- `shared/sessions.py` and `shared/tokens.py` provide persistent storage from Chapter 3.
- No new files or dependencies from future chapters (e.g., `digitalocean_integration/` or `boto3`) are included.
- The `facebook` directory is used for temporary storage, reflecting both metadata (`page_metadata.json`) and messaging (`conversations/<sender_id>.json`), aligning with the final structure in Chapter 6.

### Step 4: Update `facebook_integration/utils.py`
Update the `register_webhooks` function to include `messages` in `subscribed_fields`, keeping other functions unchanged to maintain focus on metadata handling from Subchapter 4.1.

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
```

**Why?**
- **Token Exchange and Data Fetching**: Reuses OAuth functions from Chapter 1 and Subchapter 4.1.
- **Webhook Verification**: Reuses HMAC verification from Subchapter 4.1.
- **Webhook Registration**: Updates `subscribed_fields` to include `messages`, enabling message event handling.
- **Existing Subscriptions**: Prevents duplicate subscriptions, checking for `name,category,messages`.
- **No Future Dependencies**: Excludes polling (Subchapter 4.3) or Spaces/`boto3` (Chapter 6).

### Step 5: Update `facebook_integration/routes.py`
Extend the `/webhook` endpoint to store the entire `messaging` event payload, identifying new vs. continuing conversations based on file existence. Update the `/callback` endpoint to test message webhooks.

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

    webhook_test_results = []
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
        "webhook_test": webhook_test_results
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
- **Callback Endpoint**: Registers webhooks for `name,category,messages`, tests both metadata and message webhooks, stores metadata in temporary files (`facebook/<page_id>/page_metadata.json`), and returns non-sensitive page data with `user_uuid` and `webhook_test` results. The `facebook` directory reflects both metadata and messaging, aligning with `users/<uuid>/facebook/<page_id>/...` in Chapter 6.
- **Webhook Endpoint**: Stores the entire `messaging` event payload in `facebook/<page_id>/conversations/<sender_id>.json` as an array, identifying new vs. continuing conversations via file existence. Handles `name,category` events as in Subchapter 4.1, using `page_metadata.json`.
- **Security**: Excludes tokens, uses HMAC verification, and clears sessions.
- **Temporary Storage**: Uses file-based storage, preparing for Spaces in Chapter 6.
- **Conversation Tracking**: Logs “New conversation started” or “Continuing conversation” based on file existence, using the payload’s `sender_id` and `timestamp` for organization.

### Step 6: Update `requirements.txt`
Ensure only dependencies from Chapters 1–3 are included.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
```

**Why?**
- `cryptography` supports `TokenStorage` and `SessionStorage` (Chapter 3).
- Excludes `apscheduler` (introduced in Subchapter 4.3) and `boto3` (Chapter 6).
- Supports OAuth and webhook functionality.

### Step 7: Update `.gitignore`
Ensure SQLite databases and conversation files are excluded.

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
To verify the message webhook setup:
1. Update `.env` with `FACEBOOK_WEBHOOK_ADDRESS` and `FACEBOOK_VERIFY_TOKEN`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
5. Run the Facebook OAuth flow (Chapter 1) to test webhook registration:
   ```
   http://localhost:5000/facebook/login
   ```
6. Send a test message to the connected Facebook page via Messenger (e.g., “Hello, I’m interested in snowboards”).
7. Check server logs for new vs. continuing conversation handling.
8. Testing details are in Subchapter 4.4.

**Expected Output**:
- For a new conversation (first message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  New conversation started for sender 123456789 on page 101368371725791
  Wrote conversation payload to facebook/101368371725791/conversations/123456789.json for sender 123456789 on page 101368371725791 (new: True)
  ```
- For a continuing conversation (subsequent message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  Continuing conversation for sender 123456789 on page 101368371725791
  Wrote conversation payload to facebook/101368371725791/conversations/123456789.json for sender 123456789 on page 101368371725791 (new: False)
  ```
- Example conversation JSON (`facebook/101368371725791/conversations/123456789.json`):
  ```json
  [
    {
      "sender": {"id": "123456789"},
      "recipient": {"id": "101368371725791"},
      "timestamp": 1697051234567,
      "message": {"mid": "m_abc123", "text": "Hello, I'm interested in snowboards"}
    },
    {
      "sender": {"id": "123456789"},
      "recipient": {"id": "101368371725791"},
      "timestamp": 1697051250000,
      "message": {"mid": "m_def456", "text": "Can you send the price list?"}
    }
  ]
  ```

### Summary: Why This Subchapter Matters
- **Real-Time Conversations**: Webhooks capture `messages` events, storing full payloads to preserve all data (e.g., `timestamp`, `text`, `attachments`).
- **New vs. Continuing Conversations**: File existence checks distinguish new conversations (no file) from continuations (file exists), using the payload’s `sender_id` and `timestamp`.
- **Reply Consistency**: Prepares for future replies to match the incoming payload format (to be implemented later).
- **Security**: HMAC verification, `TokenStorage`, and `SessionStorage` ensure secure, multi-user operation.
- **UUID Integration**: Organizes conversation data by UUID from Chapter 3.
- **Scalability**: Async processing supports high traffic.
- **Temporary Storage**: Uses `facebook/<page_id>/...`, preparing for Spaces in Chapter 6 (`users/<uuid>/facebook/<page_id>/...`).

### Next Steps:
- Implement polling for metadata and conversations (Subchapter 4.3).
- Test webhooks and polling for both data types (Subchapter 4.4).