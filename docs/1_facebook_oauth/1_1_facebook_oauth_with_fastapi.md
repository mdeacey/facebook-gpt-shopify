# Chapter 1: Facebook Integration
## Subchapter 1.1: Facebook OAuth with FastAPI — Secure, Scalable & Modular

This subchapter introduces the FastAPI implementation of Facebook OAuth for a GPT Messenger sales bot, enabling secure authentication to access Facebook Pages and Messenger APIs. We build a modular backend that supports sending product recommendations and promotions via Messenger. The code uses async programming, environment variable validation for reliability, and stateless CSRF protection via signed state tokens. Access tokens are stored server-side using environment variables, with persistent storage introduced in Chapter 3. The OAuth flow retrieves comprehensive, non-sensitive page data. This forms the first part of Chapter 1, followed by creating a Facebook app (Subchapter 1.2) and testing the OAuth flow (Subchapter 1.3).

### Step 1: Project Structure
To keep the project modular, we organize it as follows:
```
.
├── app.py
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
- **No Premature Features**: Excludes Shopify or session management, which are introduced in Chapters 2 and 3.

### Step 2: Create `app.py`
The main application file initializes FastAPI, validates required environment variables, sets up CORS, and includes the Facebook OAuth router.

```python
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

# Validate required environment variables
required_env_vars = [
    "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI",
    "STATE_TOKEN_SECRET"
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

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
    return {"status": "ok", "message": "Use /facebook/login for OAuth"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**Why?**
- **FastAPI Setup**: Initializes the app and loads environment variables using `python-dotenv`.
- **Environment Validation**: Ensures required variables are set, improving reliability.
- **CORS**: Enables frontend-backend interaction for OAuth redirects.
- **Router**: Mounts Facebook OAuth routes under `/facebook`.
- **Root Endpoint**: Guides users to the OAuth endpoint.
- **No Shopify**: Excludes Shopify router, as it’s introduced in Chapter 2.

### Step 3: Define Facebook OAuth Routes — `facebook_integration/routes.py`
This module defines two endpoints: `/facebook/login` to start the OAuth flow and `/facebook/callback` to handle the redirect and fetch page data. Tokens are stored in environment variables, with persistent storage introduced in Chapter 3.

```python
import os
import re
from fastapi import APIRouter, HTTPException
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
async def oauth_callback(code: str, state: str):
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
- **Callback Endpoint**: Validates the state token, exchanges the code for a user access token, stores tokens in `os.environ`, and returns non-sensitive page data.
- **Security**: Excludes tokens from the response, using environment variables for temporary storage (persistent storage in Chapter 3).
- **No Session Management**: Session-based UUID linking is introduced in Chapter 3, so `/login` doesn’t use cookies yet.

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
- **Error Handling**: Logs API errors for debugging.
- **Async HTTP**: Uses `httpx` for non-blocking requests.
- **No Webhooks**: Webhook functions are introduced in Chapter 4.

### Step 5: Stateless CSRF Protection — `shared/utils.py`
This module provides reusable CSRF protection for OAuth flows.

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
- **CSRF Protection**: Generates and validates state tokens to secure OAuth flows.
- **Stateless**: Enhances scalability without server-side storage.
- **No Extra Data**: UUID support is added in Chapter 3, keeping this simple for now.
- **Production Note**: The default `STATE_TOKEN_SECRET` should be replaced with a secure value in `.env`.

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
- **Redirect URI**: Matches the callback endpoint in `routes.py`.
- **CSRF Secret**: Ensures state token integrity, validated in `app.py`.
- **No Shopify**: Shopify variables are introduced in Chapter 2.

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
- **HTTPX**: Handles async HTTP requests for OAuth.
- **python-dotenv**: Loads `.env` variables.
- **No Additional Dependencies**: `apscheduler`, `boto3`, and `cryptography` are introduced in later chapters.

### Step 8: Git Ignore — `.gitignore`
Prevent sensitive and temporary files from being committed.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
```

**Why?**
- Excludes compiled Python files, `.env`, and macOS-specific files.
- SQLite databases (`*.db`) are added in Chapter 3, when persistent storage is introduced.

### Step 9: Testing Preparation
To verify the setup:
- Create a `.env` file with `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, and `STATE_TOKEN_SECRET` (Subchapter 1.2).
- Install dependencies: `pip install -r requirements.txt`.
- Run the app: `python app.py`.
- Access `http://localhost:5000` to confirm the root response.
- Detailed testing is covered in Subchapter 1.3.

**Why?**
- Ensures the FastAPI server and OAuth endpoints are functional before testing the full flow.

### Summary: Why This Subchapter Matters
- **Foundation for Messenger Integration**: Implements secure Facebook OAuth for accessing page data.
- **Modular Design**: Organizes code for reusability and maintenance.
- **Security**: Uses environment variables, validates them, and excludes sensitive tokens from responses.
- **Scalability**: Async programming supports high traffic.
- **Gradual Progression**: Focuses on Facebook OAuth, with persistent storage and additional integrations introduced later.

### Next Steps:
- Create a Facebook app to obtain credentials (Subchapter 1.2).
- Test the OAuth flow to verify authentication (Subchapter 1.3).
- Proceed to Chapter 2 for Shopify integration.