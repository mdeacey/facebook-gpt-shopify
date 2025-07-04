# Chapter 3: Persistent Storage and User Identification
## Subchapter 3.2: SQLite-Based Token Management

This subchapter introduces SQLite-based token management to store access tokens and UUIDs for the GPT Messenger sales bot, replacing the temporary use of environment variables (`os.environ`) from Chapters 1–2. The `TokenStorage` class in `shared/tokens.py` uses a SQLite database (`tokens.db`) with encryption (`cryptography`) and Write-Ahead Logging (WAL) for secure, concurrent access. This ensures tokens and UUIDs persist across server restarts, supporting multiple users in production. We update the Facebook and Shopify OAuth flows (Chapters 1–2) to use `TokenStorage`, preparing for data synchronization in Chapter 4. Session management was covered in Subchapter 3.1.

### Step 1: Why SQLite-Based Token Management?
Tokens and UUIDs (e.g., `FACEBOOK_ACCESS_TOKEN_{page_id}`, `SHOPIFY_ACCESS_TOKEN_{shop_key}`, `PAGE_UUID_{page_id}`, `USER_UUID_{shop_key}`) are critical for accessing platform APIs and linking user data. Using `os.environ` is not persistent and unsuitable for production. The SQLite-based approach:
- Stores tokens and UUIDs in `/app/data/tokens.db`, persisting across restarts.
- Encrypts sensitive data using `cryptography` with `STATE_TOKEN_SECRET`.
- Uses WAL for concurrent access, supporting multiple `gunicorn` workers.
- Simplifies token retrieval for future data synchronization (Chapters 4–5).
- Supports multiple users with secure, isolated storage.

### Step 2: Project Structure
Building on Subchapter 3.1, we add `shared/tokens.py`:
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
- `shared/tokens.py` manages tokens and UUIDs in SQLite.
- `facebook_integration/` and `shopify_integration/` are updated to use `TokenStorage`.
- Excludes future features (e.g., webhooks, polling, Spaces) introduced in Chapters 4–6.

### Step 3: Create `shared/tokens.py`
This module implements a SQLite-based token store with encryption and WAL.

```python
import sqlite3
import os
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from typing import Optional
from fastapi import HTTPException

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

class TokenStorage:
    def __init__(self, db_path: str = "/app/data/tokens.db"):
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
                    CREATE TABLE IF NOT EXISTS tokens (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        type TEXT NOT NULL
                    )
                """)
                conn.commit()
        except sqlite3.OperationalError as e:
            raise HTTPException(status_code=500, detail=f"Database initialization failed: {str(e)}")

    def store_token(self, key: str, value: str, type: str = "token") -> None:
        encrypted_value = self.fernet.encrypt(value.encode()).decode()
        for _ in range(3):
            try:
                with sqlite3.connect(self.db_path, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO tokens (key, value, type) VALUES (?, ?, ?)",
                        (key, encrypted_value, type)
                    )
                    conn.commit()
                    return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(0.1)
                else:
                    raise
        raise HTTPException(status_code=500, detail="Database write failed after retries")

    def get_token(self, key: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM tokens WHERE key = ?", (key,))
                result = cursor.fetchone()
                if result:
                    return self.fernet.decrypt(result[0].encode()).decode()
                return None
        except sqlite3.OperationalError as e:
            raise HTTPException(status_code=500, detail=f"Database read failed: {str(e)}")
```

**Why?**
- **SQLite Storage**: Stores tokens in `/app/data/tokens.db`, persisting across restarts.
- **Encryption**: Uses `cryptography` with `STATE_TOKEN_SECRET` to secure tokens and UUIDs.
- **WAL**: Enables concurrent access for production.
- **Retry Logic**: Handles database locking with retries.
- **Type Field**: Distinguishes tokens (`token`) from UUIDs (`uuid`) for future use (e.g., Chapter 4).
- **Production Note**: Secure file permissions for `tokens.db` (e.g., `chmod 600`).

### Step 4: Update `facebook_integration/routes.py`
Replace `os.environ` with `TokenStorage` for token and UUID storage.

```python
import os
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage

router = APIRouter()
session_storage = SessionStorage()
token_storage = TokenStorage()

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

    for page in pages.get("data", []):
        page_id = page["id"]
        token_storage.store_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}", page["access_token"], type="token")
        token_storage.store_token(f"PAGE_UUID_{page_id}", user_uuid, type="uuid")

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
- Replaces `os.environ` with `TokenStorage` for `FACEBOOK_USER_ACCESS_TOKEN`, `FACEBOOK_ACCESS_TOKEN_{page_id}`, and `PAGE_UUID_{page_id}`.
- Uses `SessionStorage` from Subchapter 3.1 for session handling.
- Excludes webhooks or polling (Chapter 4).
- **Security**: Stores encrypted tokens in `tokens.db`, excludes them from responses.

### Step 5: Update `shopify_integration/routes.py`
Replace `os.environ` with `TokenStorage` for token and UUID storage.

```python
import os
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage

router = APIRouter()
session_storage = SessionStorage()
token_storage = TokenStorage()

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
    token_storage.store_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}", token_data["access_token"], type="token")

    user_uuid = str(uuid.uuid4())
    token_storage.store_token(f"USER_UUID_{shop_key}", user_uuid, type="uuid")

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
- Replaces `os.environ` with `TokenStorage` for `SHOPIFY_ACCESS_TOKEN_{shop_key}` and `USER_UUID_{shop_key}`.
- Uses `SessionStorage` for session handling.
- Excludes webhooks or polling (Chapter 5).
- **Security**: Stores encrypted tokens in `tokens.db`, sets a secure `session_id` cookie.

### Step 6: Update `facebook_integration/utils.py`
Ensure compatibility with `TokenStorage` (though no changes are needed yet, as webhooks/polling are in Chapter 4).

```python
import os
import httpx
from fastapi import HTTPException

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
```

**Why?**
- Retains OAuth functions from Chapter 1.
- No token storage changes needed here, as `utils.py` doesn’t access tokens yet (updated in Chapter 4).

### Step 7: Update `shopify_integration/utils.py`
Ensure compatibility with `TokenStorage` (no changes needed yet).

```python
import os
import httpx
import asyncio
from fastapi import HTTPException

async def exchange_code_for_token(code: str, shop: str):
    url = f"https://{shop}/admin/oauth/access_token"
    data = {
        "client_id": os.getenv("SHOPIFY_API_KEY"),
        "client_secret": os.getenv("SHOPIFY_API_SECRET"),
        "code": code
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        return response.json()

async def get_shopify_data(access_token: str, shop: str, retries=3):
    url = f"https://{shop}/admin/api/2025-04/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    query = """
    query SalesBotQuery {
      shop { name primaryDomain { url } }
      products(first: 50, sortKey: RELEVANCE) {
        edges {
          node {
            title
            description
            handle
            productType
            vendor
            tags
            status
            variants(first: 10) {
              edges {
                node {
                  title
                  price
                  availableForSale
                  inventoryItem {
                    inventoryLevels(first: 5) {
                      edges {
                        node {
                          quantities(names: ["available"]) { name quantity }
                          location { name }
                        }
                      }
                    }
                  }
                }
              }
            }
            metafields(first: 10, namespace: "custom") {
              edges { node { key value } }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
      codeDiscountNodes(first: 10, sortKey: TITLE) {
        edges {
          node {
            codeDiscount {
              ... on DiscountCodeBasic {
                title
                codes(first: 5) { edges { node { code } } }
                customerGets {
                  value {
                    ... on DiscountAmount { amount { amount currencyCode } }
                    ... on DiscountPercentage { percentage }
                  }
                }
                startsAt
                endsAt
              }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
      collections(first: 10, sortKey: TITLE) {
        edges {
          node {
            title
            handle
            products(first: 5) { edges { node { title } } }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
    """

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json={"query": query})
                response.raise_for_status()
                data = response.json()
                if "errors" in data:
                    raise HTTPException(status_code=400, detail=f"GraphQL error: {data['errors']}")
                return data
        except httpx.HTTPStatusError as e:
            if attempt == retries - 1 or e.response.status_code != 429:
                raise
            await asyncio.sleep(2 ** attempt)
```

**Why?**
- Retains OAuth functions from Chapter 2.
- No token storage changes needed here, as `utils.py` doesn’t access tokens yet (updated in Chapter 5).

### Step 8: Update `app.py`
Ensure environment validation includes all required variables.

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
- Validates environment variables for both integrations.
- Excludes future features (e.g., scheduling, introduced in Chapter 4).

### Step 9: Update `.gitignore`
Ensure SQLite databases are excluded.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
```

**Why?**
- Excludes `tokens.db` and `sessions.db` to prevent committing sensitive data.
- Builds on Chapter 1’s `.gitignore`.

### Step 10: Update `requirements.txt`
Ensure `cryptography` is included.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
```

**Why?**
- `cryptography` supports encryption for both sessions and tokens.
- Excludes `apscheduler` and `boto3` (introduced in Chapters 4–6).

### Step 11: Testing Preparation
To verify token management:
- Run: `python app.py`.
- Complete Shopify OAuth (`/shopify/acme-7cu19ngr/login`) to store tokens and UUIDs in `tokens.db` and set the `session_id` cookie.
- Complete Facebook OAuth (`/facebook/login`) to store tokens and UUIDs in `tokens.db` and retrieve the UUID from `sessions.db`.
- Check `/app/data/tokens.db` exists and contains encrypted tokens/UUIDs.

**Why?**
- Ensures token storage is functional before proceeding to data synchronization.

### Summary: Why This Subchapter Matters
- **Persistent Tokens**: SQLite-based `TokenStorage` ensures tokens persist across restarts, supporting production.
- **Multi-Platform Linking**: UUIDs stored in `tokens.db` link Shopify and Facebook data.
- **Security**: Encrypts tokens and uses WAL for concurrency.
- **Gradual Progression**: Builds on session management (Subchapter 3.1), preparing for data sync in Chapter 4.

### Next Steps:
- Proceed to Chapter 4 for Facebook data synchronization.