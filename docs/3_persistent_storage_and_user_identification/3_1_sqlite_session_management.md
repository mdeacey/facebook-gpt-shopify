# Chapter 3: Persistent Storage and User Identification
## Subchapter 3.1: SQLite-Based Session Management

This subchapter introduces SQLite-based session management to link user data across multiple platforms (e.g., Shopify and Facebook) for the GPT Messenger sales bot. A UUID, generated during the Shopify OAuth flow (Chapter 2), uniquely identifies a user’s data. To automate passing this UUID to the Facebook OAuth flow (Chapter 1) without requiring a URL parameter, we implement a session-based mechanism using a `session_id` cookie stored in a SQLite database (`sessions.db`) with encryption and Write-Ahead Logging (WAL) for concurrency. This replaces the in-memory session store from earlier designs, ensuring persistence across server restarts and supporting multiple users in production. The session is cleared after use to prevent leaks, and the design supports future platforms. Token management is covered in Subchapter 3.2.

### Step 1: Why SQLite-Based Session Management?
The sales bot integrates multiple platforms, requiring a unified identifier (UUID) to group data. Without session management, users must manually pass the UUID (e.g., `/facebook/login?uuid=<uuid>`), which is error-prone in production. The SQLite-based approach:
- Generates a UUID during Shopify OAuth to identify the user.
- Stores the UUID in `sessions.db`, keyed by a `session_id` cookie.
- Retrieves the UUID in `/facebook/login` using the cookie, eliminating URL parameters.
- Uses encryption (`cryptography`) and WAL for secure, concurrent access.
- Supports multiple users and persists across restarts, preparing for production scalability.

### Step 2: Project Structure
Building on Chapters 1 and 2, we add `shared/sessions.py` for SQLite-based session management:
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
│   └── utils.py
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `shared/sessions.py` manages session IDs and UUIDs in SQLite, replacing in-memory storage.
- `facebook_integration/routes.py` and `shopify_integration/routes.py` are updated to use sessions.
- Excludes future features (e.g., webhooks, polling, Spaces) introduced in Chapters 4–6.

### Step 3: Create `shared/sessions.py`
This module implements a SQLite-based session store with encryption and WAL.

```python
import sqlite3
import os
import time
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from typing import Optional

def get_fernet_key() -> Fernet:
    secret = os.getenv("STATE_TOKEN_SECRET").encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'salt_',
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)

class SessionStorage:
    def __init__(self, db_path: str = os.getenv("SESSION_DB_PATH", "./data/sessions.db")):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.fernet = get_fernet_key()
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        uuid TEXT NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                """)
                conn.commit()
        except sqlite3.OperationalError as e:
            raise Exception(f"Session database initialization failed: {str(e)}")

    def generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return secrets.token_urlsafe(32)

    def store_uuid(self, session_id: str, uuid: str) -> None:
        """Store UUID in the session database."""
        encrypted_uuid = self.fernet.encrypt(uuid.encode()).decode()
        created_at = int(time.time())
        for _ in range(3):
            try:
                with sqlite3.connect(self.db_path, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO sessions (session_id, uuid, created_at) VALUES (?, ?, ?)",
                        (session_id, encrypted_uuid, created_at)
                    )
                    conn.commit()
                    return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(0.1)
                else:
                    raise
        raise Exception("Session database write failed after retries")

    def get_uuid(self, session_id: str) -> Optional[str]:
        """Retrieve UUID from the session database."""
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT uuid FROM sessions WHERE session_id = ?", (session_id,))
                result = cursor.fetchone()
                if result:
                    return self.fernet.decrypt(result[0].encode()).decode()
                return None
        except sqlite3.OperationalError as e:
            raise Exception(f"Session database read failed: {str(e)}")

    def clear_session(self, session_id: str) -> None:
        """Remove session ID from the database."""
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
        except sqlite3.OperationalError as e:
            raise Exception(f"Session database delete failed: {str(e)}")
```

**Why?**
- **SQLite Storage**: Stores sessions in a configurable path (`SESSION_DB_PATH` or `./data/sessions.db`), persisting across restarts and avoiding permission issues in restricted environments.
- **Encryption**: Uses `cryptography` with `STATE_TOKEN_SECRET` to encrypt UUIDs.
- **WAL**: Enables concurrent access for multiple `gunicorn` workers in production.
- **Retry Logic**: Handles database locking with retries.
- **Production Note**: Set `SESSION_DB_PATH` to a writable directory in production (e.g., `/var/app/data/sessions.db` or a mounted volume). Ensure file permissions (`chmod 600`) and ownership (`chown app_user:app_user`) for security.

### Step 4: Update `shopify_integration/routes.py`
Modify `/callback` to set a `session_id` cookie using `SessionStorage`.

```python
import os
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage

router = APIRouter()
session_storage = SessionStorage()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    state = generate_state_token()
    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&state={state}"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")
    state = request.query_params.get("state")

    if not code or not shop or not state:
        raise HTTPException(status_code=400, detail="Missing code/shop/state")

    validate_state_token(state)
    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    shop_key = shop.replace('.', '_')
    os.environ[f"SHOPIFY_ACCESS_TOKEN_{shop_key}"] = token_data["access_token"]

    user_uuid = str(uuid.uuid4())
    os.environ[f"USER_UUID_{shop_key}"] = user_uuid

    session_id = session_storage.generate_session_id()
    session_storage.store_uuid(session_id, user_uuid)

    shopify_data = await get_shopify_data(token_data["access_token"], shop)

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "token_data": token_data,
        "shopify_data": shopify_data
    })
    response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=3600)
    return response
```

**Why?**
- Generates a UUID and stores it in `os.environ` (persistent storage in Subchapter 3.2).
- Sets a `session_id` cookie using `SessionStorage` for `/facebook/login` to retrieve the UUID.
- Returns `user_uuid` for compatibility.
- Uses `os.environ` for tokens, as token management is introduced in Subchapter 3.2.
- Excludes webhooks or polling (Chapter 5).

### Step 5: Update `facebook_integration/routes.py`
Update `/facebook/login` to use the `session_id` cookie and `/callback` to clear the session, passing the UUID via the state token.

```python
import os
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage

router = APIRouter()
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

    os.environ["FACEBOOK_USER_ACCESS_TOKEN"] = token_data["access_token"]

    pages = await get_facebook_data(token_data["access_token"])

    for page in pages.get("data", []):
        page_id = page["id"]
        os.environ[f"FACEBOOK_ACCESS_TOKEN_{page_id}"] = page["access_token"]
        os.environ[f"PAGE_UUID_{page_id}"] = user_uuid

    safe_pages = {
        "data": [
            {k: v for k, v in page.items() if k != "access_token"}
            for page in pages.get("data", [])
        ],
        "paging": pages.get("paging", {})
    }

    return JSONResponse(content={
        "user_uuid": user_uuid,
        "pages": safe_pages
    })
```

**Why?**
- **Login Endpoint**: Uses `SessionStorage` to retrieve the UUID from the `session_id` cookie, passing it via the state token.
- **Callback Endpoint**: Clears the session to prevent leaks, stores tokens and UUIDs in `os.environ` (persistent storage in Subchapter 3.2), and returns non-sensitive page data with `user_uuid`.
- **Security**: Excludes tokens from responses, uses encrypted session storage.
- **No Webhooks**: Webhooks are introduced in Chapter 4.

### Step 6: Update `shared/utils.py`
Update to support `extra_data` for passing UUIDs in state tokens.

```python
import os
import time
import hmac
import hashlib
import base64
import secrets
from fastapi import HTTPException

STATE_TOKEN_SECRET = os.getenv("STATE_TOKEN_SECRET", "changeme-in-prod")

def generate_state_token(expiry_seconds: int = 300, extra_data: str = None) -> str:
    timestamp = int(time.time())
    nonce = secrets.token_urlsafe(8)
    payload = f"{timestamp}:{nonce}"
    if extra_data:
        payload += f":{extra_data}"
    signature = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode()
    return f"{timestamp}:{nonce}:{encoded_sig}" if not extra_data else f"{timestamp}:{nonce}:{extra_data}:{encoded_sig}"

def validate_state_token(state_token: str, max_age: int = 300):
    try:
        parts = state_token.split(":")
        if len(parts) == 3:
            timestamp_str, nonce, provided_sig = parts
            extra_data = None
        elif len(parts) == 4:
            timestamp_str, nonce, extra_data, provided_sig = parts
        else:
            raise HTTPException(status_code=400, detail="Malformed state token")
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed state token")

    if abs(time.time() - timestamp) > max_age:
        raise HTTPException(status_code=400, detail="Expired state token")

    payload = f"{timestamp}:{nonce}" if not extra_data else f"{timestamp}:{nonce}:{extra_data}"
    expected_sig = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    expected_sig_encoded = base64.urlsafe_b64encode(expected_sig).decode()

    if not hmac.compare_digest(provided_sig, expected_sig_encoded):
        raise HTTPException(status_code=400, detail="Invalid state token")

    return extra_data
```

**Why?**
- Supports `extra_data` for passing UUIDs in state tokens.
- Ensures secure CSRF protection, reusing `STATE_TOKEN_SECRET` from Chapters 1–2.
- Excludes future features (e.g., webhooks, polling).

### Step 7: Configure Environment Variables
Update `.env.example` to include the session database path.

```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# Database path for session storage
SESSION_DB_PATH=./data/sessions.db
```

**Why?**
- Supports both OAuth flows and session encryption.
- `SESSION_DB_PATH` allows custom database paths, with a fallback to `./data/sessions.db` for development.
- Excludes future variables (e.g., webhook or Spaces settings, introduced in Chapters 4–6).
- **Production Note**: Set `SESSION_DB_PATH` to a secure, writable directory (e.g., `/var/app/data/sessions.db`) and ensure secure permissions (`chmod 600`, `chown app_user:app_user`).

### Step 8: Update `requirements.txt`
Add `cryptography` for session encryption.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
```

**Why?**
- `cryptography` enables secure UUID encryption in `sessions.db`.
- Other dependencies support OAuth flows from Chapters 1–2.
- Excludes `apscheduler` and `boto3` (introduced in Chapters 4–6).

### Step 9: Update `app.py`
Ensure `app.py` validates environment variables for both integrations.

```python
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

# Validate required environment variables
required_env_vars = [
    "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI",
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**Why?**
- Validates environment variables for reliability.
- Includes both routers for Facebook and Shopify OAuth.
- Excludes future features (e.g., scheduling, introduced in Chapter 4).

### Step 10: Update `.gitignore`
Add SQLite database files to prevent committing sensitive data.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
```

**Why?**
- Excludes `sessions.db` (and `tokens.db`, introduced in Subchapter 3.2).
- Maintains security by preventing database commits.

### Step 11: Testing Preparation
Testing is covered in Chapters 1–2, but you can verify session management:
- Run: `python app.py`.
- Complete Shopify OAuth (`/shopify/acme-7cu19ngr/login`) to set the `session_id` cookie.
- Navigate to `/facebook/login` to verify the UUID is retrieved from `sessions.db`.
- Check the session database (defined by `SESSION_DB_PATH` or `./data/sessions.db`) exists and contains encrypted UUIDs. Use `sqlite3 "${SESSION_DB_PATH:-./data/sessions.db}" "SELECT session_id, created_at FROM sessions;"`.

**Why?**
- Ensures session storage is functional before proceeding to token management.

### Summary: Why This Subchapter Matters
- **Persistent Sessions**: SQLite-based `SessionStorage` ensures sessions persist across restarts, supporting production environments.
- **Multi-Platform Linking**: UUIDs and sessions link Shopify and Facebook data securely.
- **Seamless Flow**: Eliminates URL parameters for production readiness.
- **Security**: Encrypts UUIDs and uses WAL for concurrency.
- **Gradual Progression**: Builds on OAuth (Chapters 1–2), with token management in Subchapter 3.2.

### Next Steps:
- Implement SQLite-based token management (Subchapter 3.2).
- Proceed to Chapter 4 for data synchronization.