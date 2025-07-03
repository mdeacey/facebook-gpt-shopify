# Chapter 1: Facebook Integration
## Subchapter 1.1: Facebook OAuth with FastAPI — Secure, Scalable & Modular

This subchapter introduces the FastAPI implementation of Facebook OAuth for a GPT Messenger sales bot, enabling secure authentication to access Facebook Pages and Messenger APIs. We build a modular backend that supports sending product recommendations and promotions via Messenger. The code uses async programming, environment variables, and stateless CSRF protection via signed state tokens. The OAuth flow retrieves comprehensive, non-sensitive page data while securely storing access tokens server-side. This forms the first part of Chapter 1, followed by creating a Facebook app (Subchapter 1.2) and testing the OAuth flow (Subchapter 1.3).

### Step 1: Project Structure
To keep the project modular, we organize it as follows:
```
.
573├── app.py
├── facebook_integration/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shared/
│   ├── __init__.py
│   └── utils.py
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- **Separation of Concerns**: The `facebook_integration/` module isolates Facebook-specific logic.
- **Shared Logic**: `shared/utils.py` provides CSRF protection, reusable for future integrations.
- **Scalability**: Modular design supports testing and maintenance.

### Step 2: Create `app.py`
The main application file initializes FastAPI, sets up CORS, and includes the Facebook OAuth router.

```python
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Facebook OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Use /facebook/login for OAuth"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**Why?**
- **FastAPI Setup**: Initializes the app and loads environment variables.
- **CORS**: Enables frontend-backend interaction for OAuth redirects.
- **Router**: Mounts Facebook OAuth routes under `/facebook`.
- **Root Endpoint**: Guides users to the OAuth endpoint.

### Step 3: Define Facebook OAuth Routes — `facebook_integration/routes.py`
This module defines two endpoints: `/facebook/login` to start the OAuth flow and `/facebook/callback` to handle the redirect and fetch page data.

```python
import os
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_facebook_data
from shared.utils import generate_state_token, validate_state_token

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
    state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    validate_state_token(state)

    token_data = await exchange_code_for_token(code)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    os.environ["FACEBOOK_USER_ACCESS_TOKEN"] = token_data["access_token"]

    pages = await get_facebook_data(token_data["access_token"])

    for page in pages.get("data", []):
        page_id = page["id"]
        os.environ[f"FACEBOOK_ACCESS_TOKEN_{page_id}"] = page["access_token"]

    safe_pages = {
        "data": [
            {k: v for k, v in page.items() if k != "access_token"}
            for page in pages.get("data", [])
        ],
        "paging": pages.get("paging", {})
    }

    return JSONResponse(content={"pages": safe_pages})
```

**Why?**
- **Login Endpoint**: Initiates OAuth with scopes for Messenger and page data, using a state token for CSRF protection.
- **Callback Endpoint**: Validates the state token, exchanges the code for a user access token, stores it server-side, and returns non-sensitive page data.
- **Security**: Excludes tokens from the response, storing them in `os.environ`.

### Step 4: Facebook-Specific Helpers — `facebook_integration/utils.py`
This module contains helper functions for token exchange and data retrieval.

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
- **Token Exchange**: Fetches a user access token.
- **Data Fetching**: Retrieves non-sensitive page data for Messenger interactions.
- **Error Handling**: Logs API errors.
- **Async HTTP**: Uses `httpx` for non-blocking requests.

### Step 5: Stateless CSRF Protection — `shared/utils.py`
This module provides reusable CSRF protection.

```python
import os
import time
import hmac
import hashlib
import base64
import secrets
from fastapi import HTTPException

STATE_TOKEN_SECRET = os.getenv("STATE_TOKEN_SECRET", "changeme-in-prod")

def generate_state_token(expiry_seconds: int = 300) -> str:
    timestamp = int(time.time())
    nonce = secrets.token_urlsafe(8)
    payload = f"{timestamp}:{nonce}"
    signature = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode()
    return f"{timestamp}:{nonce}:{encoded_sig}"

def validate_state_token(state_token: str, max_age: int = 300):
    try:
        timestamp_str, nonce, provided_sig = state_token.split(":")
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed state token")

    if abs(time.time() - timestamp) > max_age:
        raise HTTPException(status_code=400, detail="Expired state token")

    expected_sig = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        f"{timestamp}:{nonce}".encode(),
        hashlib.sha256
    ).digest()
    expected_sig_encoded = base64.urlsafe_b64encode(expected_sig).decode()

    if not hmac.compare_digest(provided_sig, expected_sig_encoded):
        raise HTTPException(status_code=400, detail="Invalid state token")
```

**Why?**
- **CSRF Protection**: Generates and validates state tokens.
- **Stateless**: Enhances scalability.
- **Reusable**: Supports future integrations.

### Step 6: Environment Variables — `.env.example`
Define environment variables for Facebook OAuth.

```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Why?**
- **Credentials**: Authenticate the OAuth flow.
- **Redirect URI**: Matches the callback endpoint.
- **CSRF Secret**: Ensures state token integrity.

### Step 7: Dependencies — `requirements.txt`
List required Python packages.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
```

**Why?**
- **FastAPI & Uvicorn**: Core framework and server.
- **HTTPX**: Handles async HTTP requests.
- **python-dotenv**: Loads `.env` variables.

### Step 8: Git Ignore — `.gitignore`
Prevent sensitive files from being committed.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
```

**Why?**
- Excludes compiled files, `.env`, and macOS-specific files.

### Step 9: Testing Preparation
To verify:
- Create a `.env` file with `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, and `STATE_TOKEN_SECRET` (Subchapter 1.2).
- Install dependencies: `pip install -r requirements.txt`.
- Run the app: `python app.py`.
- Access `http://localhost:5000` to confirm the root response.

Testing is covered in Subchapter 1.3.

### Summary: Why This Subchapter Matters
- **Foundation for Messenger Integration**: Implements secure Facebook OAuth.
- **Modular Design**: Organizes code for reusability.
- **Security**: Uses environment variables and CSRF protection, excluding sensitive tokens.
- **Scalability**: Async programming supports high traffic.

### Next Steps:
- Create a Facebook app (Subchapter 1.2).
- Test the OAuth flow (Subchapter 1.3).