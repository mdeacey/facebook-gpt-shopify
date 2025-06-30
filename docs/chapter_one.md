# Chapter 1: Facebook OAuth with FastAPI — Secure, Scalable & Modular

This tutorial walks you through building a **secure, modular, and scalable** Facebook OAuth integration with FastAPI. It uses best practices like async programming, environment variables, and **stateless CSRF protection** via signed `state` tokens.

---

## 📁 Step 1: Project Structure

```txt
.
├── app.py
├── facebook_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shared/
│   ├── __init__.py
│   └── utils.py          # <- Stateless CSRF helpers
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why this structure?**

* Separation of concerns: Each service (Facebook, Shopify) is modular.
* Shared logic (like CSRF protection) lives in `shared/`.
* Easy to extend, test, and maintain.

---

## 🚀 Step 2: Create `app.py`

```python
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
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
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

> **Why CORS?** Enables frontend-backend interaction during local or cross-origin dev.

---

## 🌐 Step 3: Define Facebook OAuth Routes — `facebook_oauth/routes.py`

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
```

---

## 🛠 Step 4: Facebook-Specific Helpers — `facebook_oauth/utils.py`

```python
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
```

---

## 🔐 Step 5: Stateless CSRF Protection — `shared/utils.py`

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

---

## ⚙️ Step 6: Environment Variables — `.env.example`

```env
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback

# If you're using GitHub Codespaces, replace with something like:
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback

# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

> 💡 Generate a strong secret using:
>
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

---

## 📦 Step 7: `requirements.txt`

```txt
fastapi
uvicorn
httpx
python-dotenv
```

---

## 🚫 Step 8: `.gitignore`

```txt
__pycache__/
*.pyc
.env
.DS_Store
```
