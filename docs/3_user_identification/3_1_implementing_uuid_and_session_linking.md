# Chapter 3: UUID and Session Management
## Subchapter 3.1: Implementing UUID Generation and Session-Based Linking

This subchapter introduces UUID generation and session management to link data across multiple platforms (e.g., Shopify and Facebook) for the GPT Messenger sales bot. A UUID, generated during the Shopify OAuth flow (Chapter 2), uniquely identifies a user’s data. To automate passing this UUID to the Facebook OAuth flow (Chapter 1) without requiring a URL parameter, we implement a session-based mechanism using a cookie and an in-memory session store. This ensures a seamless, production-ready flow for multiple users, allowing `/facebook/login` to retrieve the UUID from a `session_id` cookie set by Shopify’s `/callback`. The session is cleared after use to prevent memory leaks, and the design supports future platforms (e.g., OnlyFans, WhatsApp).

### Step 1: Why UUID and Session Management?
The sales bot integrates multiple platforms, requiring a unified identifier (UUID) to group data. Without session management, users must manually pass the UUID (e.g., `/facebook/login?uuid=<uuid>`), which is error-prone and breaks in production with multiple users. The session-based approach:
- Generates a UUID during Shopify OAuth to identify the user.
- Stores the UUID in a session store, keyed by a `session_id` cookie.
- Retrieves the UUID in `/facebook/login` using the cookie, eliminating URL parameters.
- Supports multiple users by isolating sessions, preparing for production scalability.

### Step 2: Project Structure
Building on Chapters 1 and 2, we add `shared/session.py`:
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
- `shared/session.py` manages session IDs and UUIDs for multi-user support.
- `facebook_integration/routes.py` is updated to use sessions.
- `shopify_integration/routes.py` sets the session cookie.

### Step 3: Create `shared/session.py`
This module implements an in-memory session store for UUIDs.

```python
import secrets
from typing import Dict, Optional

# In-memory session store (replace with Redis in production)
SESSION_STORE: Dict[str, str] = {}

def generate_session_id() -> str:
    """Generate a unique session ID."""
    return secrets.token_urlsafe(32)

def store_uuid(session_id: str, uuid: str) -> None:
    """Store UUID in the session store."""
    SESSION_STORE[session_id] = uuid

def get_uuid(session_id: str) -> Optional[str]:
    """Retrieve UUID from the session store."""
    return SESSION_STORE.get(session_id)

def clear_session(session_id: str) -> None:
    """Remove session ID from the store."""
    SESSION_STORE.pop(session_id, None)
```

**Why?**
- `SESSION_STORE` maps session IDs to UUIDs, isolating user data.
- `generate_session_id` creates secure session IDs.
- `store_uuid` and `get_uuid` manage UUIDs.
- `clear_session` prevents memory leaks.
- **Production Note**: Replace with Redis (e.g., `redis.set(session_id, uuid, ex=3600)`) for scalability.

### Step 4: Update `shopify_integration/routes.py`
Modify `/callback` to set a `session_id` cookie.

```python
import os
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data
from shared.utils import generate_state_token, validate_state_token
from shared.session import generate_session_id, store_uuid

router = APIRouter()

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

    session_id = generate_session_id()
    store_uuid(session_id, user_uuid)

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
- Generates a UUID and stores it in `os.environ` and `SESSION_STORE`.
- Sets a `session_id` cookie for `/facebook/login` to retrieve the UUID.
- Returns `user_uuid` for compatibility.

### Step 5: Update `facebook_integration/routes.py`
Update `/facebook/login` to use the `session_id` cookie and clear the session in `/callback`.

```python
import os
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data
from shared.utils import generate_state_token, validate_state_token
from shared.session import get_uuid, clear_session

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
- Removes the `uuid` parameter, using the `session_id` cookie.
- Clears the session in `/callback` to prevent leaks.
- Stores page-to-UUID mappings for future use.
- Returns `user_uuid` for consistency.

### Step 6: Update `shared/utils.py`
Update to support `extra_data` for UUID passing.

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
- Supports `extra_data` for passing UUIDs.
- Ensures secure CSRF protection.
- Reusable for future platforms.

### Step 7: Configure Environment Variables
Use the same `.env` as Chapter 2.

```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Why?**
- Supports both OAuth flows.
- No new variables needed for sessions.

### Step 8: Testing Preparation
Testing is covered in Chapters 1 and 2, but you can:
- Run: `python app.py`.
- Complete Shopify OAuth (`/shopify/acme-7cu19ngr/login`) to set the `session_id` cookie.
- Navigate to `/facebook/login` to verify the UUID is retrieved.

### Summary: Why This Subchapter Matters
- **Multi-Platform Linking**: UUIDs and sessions link Shopify and Facebook data.
- **Seamless Flow**: Eliminates URL parameters for production readiness.
- **Scalability**: Supports multiple users with session isolation.
- **Extensibility**: Prepares for future platforms.

### Next Steps:
- Proceed to Chapter 4 for Facebook data synchronization.