Chapter 1: Facebook Integration
Subchapter 1.1: Facebook OAuth with FastAPI — Secure, Scalable & Modular
This subchapter introduces the FastAPI implementation of Facebook OAuth for a GPT Messenger sales bot, enabling secure authentication to access Facebook Pages and Messenger APIs. We build a modular backend that supports sending product recommendations and promotions via Messenger. The code is designed for scalability, using async programming, environment variables, and stateless CSRF protection via signed state tokens. This forms the first part of Chapter 1, followed by creating a Facebook app (Subchapter 1.2) and testing the OAuth flow (Subchapter 1.3).

Step 1: Project Structure
To keep the project modular and extensible, we organize it as follows:
.
├── app.py
├── facebook_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shared/
│   ├── __init__.py
│   └── utils.py          # Stateless CSRF helpers
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt

Why this structure?

Separation of Concerns: The facebook_oauth/ module isolates Facebook-specific logic, making it easy to add Shopify integration (Chapter 2).
Shared Logic: shared/utils.py contains reusable CSRF protection code, reducing duplication.
Scalability: Modular design supports testing, maintenance, and future extensions (e.g., additional APIs).


Step 2: Create app.py
The main application file initializes FastAPI, sets up CORS, and includes the Facebook OAuth router.
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

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

Why?

FastAPI Setup: Initializes the app with a descriptive title and loads environment variables via python-dotenv.
CORS: Allows frontend-backend interaction during development, critical for OAuth redirects.
Router: Mounts the Facebook OAuth routes under /facebook, leaving room for Shopify routes (Subchapter 2.2).
Root Endpoint: Provides a simple health check and usage hint, testable in Subchapter 1.3.


Step 3: Define Facebook OAuth Routes — facebook_oauth/routes.py
This module defines two endpoints: /facebook/login to start the OAuth flow and /facebook/callback to handle the redirect and fetch page data.
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
    scope = "pages_messaging,pages_show_list"

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

    pages = await get_facebook_data(token_data["access_token"])
    return JSONResponse(content={"token_data": token_data, "pages": pages})

Why?

Login Endpoint: Constructs the OAuth URL with client_id, redirect_uri, and scopes (pages_messaging, pages_show_list) needed for Messenger integration. The state token prevents CSRF attacks.
Callback Endpoint: Validates the state token, exchanges the code for an access token, and fetches page data (e.g., page IDs, access tokens). Returns a JSON response for testing in Subchapter 1.3.
Validation: Checks client_id format and required parameters, ensuring robustness.


Step 4: Facebook-Specific Helpers — facebook_oauth/utils.py
This module contains helper functions for token exchange and data retrieval.
import os
import httpx

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
    params = {"access_token": access_token}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

Why?

Token Exchange: exchange_code_for_token securely fetches an access token using the authorization code and app credentials.
Data Fetching: get_facebook_data retrieves page data (e.g., page IDs, access tokens) needed for Messenger interactions.
Async HTTP: Uses httpx for non-blocking requests, aligning with FastAPI’s async nature.


Step 5: Stateless CSRF Protection — shared/utils.py
This module provides reusable CSRF protection, used by both Facebook and Shopify OAuth flows.
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

Why?

CSRF Protection: Generates and validates signed state tokens to prevent cross-site request forgery during OAuth redirects.
Stateless: Stores no session data, improving scalability.
Reusable: Shared across Facebook (this subchapter) and Shopify (Subchapter 2.2) OAuth flows.


Step 6: Environment Variables — .env.example
Define environment variables for Facebook OAuth, with placeholders for Shopify variables (added in Chapter 2).
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback

# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback

# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token

Why?

Credentials: FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are obtained in Subchapter 1.2, authenticating the OAuth flow.
Redirect URI: Matches the callback endpoint, configurable for local or Codespaces environments.
CSRF Secret: A secure token (generate via python -c "import secrets; print(secrets.token_urlsafe(32))") ensures state token integrity.
Security: Storing variables in .env (not committed, per .gitignore) prevents credential exposure.


Step 7: Dependencies — requirements.txt
List the required Python packages.
fastapi
uvicorn
httpx
python-dotenv

Why?

FastAPI & Uvicorn: Core framework and server for running the app.
HTTPX: Handles async HTTP requests for OAuth and API calls.
python-dotenv: Loads .env variables, simplifying configuration.


Step 8: Git Ignore — .gitignore
Prevent sensitive files from being committed.
__pycache__/
*.pyc
.env
.DS_Store

Why?

Excludes compiled Python files, the .env file (containing secrets), and macOS-specific files, ensuring a clean repository.


Step 9: Testing Preparation
To verify this implementation:

Create a .env file based on .env.example, filling in FACEBOOK_APP_ID and FACEBOOK_APP_SECRET (obtained in Subchapter 1.2).
Install dependencies: pip install -r requirements.txt.
Run the app: python app.py.
Access http://localhost:5000 to see the root response: {"status": "ok", "message": "Use /facebook/login for OAuth"}.

Detailed testing, including the OAuth flow, is covered in Subchapter 1.3.

Summary: Why This Subchapter Matters

Foundation for Messenger Integration: Implements secure Facebook OAuth, enabling access to Pages and Messenger APIs for the sales bot.
Modular Design: Organizes code into reusable modules (facebook_oauth, shared), preparing for Shopify integration (Chapter 2).
Security: Uses environment variables, CSRF protection, and input validation to ensure a robust implementation.
Scalability: Async programming and stateless design support high traffic and future extensions.

Next Steps:

Create a Facebook app to obtain credentials (Subchapter 1.2).
Test the OAuth flow to verify authentication and page data retrieval (Subchapter 1.3).
Proceed to Shopify integration (Chapter 2) for product data.
