Step-by-Step Tutorial: Building Facebook OAuth with FastAPI --- Explained and Designed Right
==========================================================================================

* * * * *

Step 1: Setup Your Project Structure
------------------------------------

We start by organizing our code in a clean, modular way:

markdown

CopyEdit

`.
├── facebook_oauth
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── .env.example
├── .gitignore
├── app.py
├── LICENSE
├── README.md
└── requirements.txt`

-   `facebook_oauth/` contains all OAuth-related logic, keeping concerns separated.

-   `app.py` is the FastAPI entry point --- it sets up the app and routes.

-   `.env.example` documents environment variables needed for config.

-   `requirements.txt` manages dependencies.

This modular structure supports maintainability and scalability --- key for professional projects.

* * * * *

Step 2: Prepare `app.py` --- The FastAPI Application Entry
--------------------------------------------------------

python

CopyEdit

`from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()`

### Why `load_dotenv()`?

We want to keep sensitive data like Facebook App secrets out of code and version control. `load_dotenv()` loads these from a `.env` file into environment variables, which our code can securely access using `os.getenv()`.

python

CopyEdit

`app = FastAPI(title="Facebook OAuth with FastAPI")`

We create the main FastAPI app with a clear title --- useful for auto-generated docs and clarity.

python

CopyEdit

`app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Relaxed in dev, lock down in production for security
    allow_methods=["*"],
    allow_headers=["*"],
)`

### Why add CORS middleware?

If your frontend is served from a different domain than your API, browsers block cross-origin requests by default. Adding CORS middleware enables your frontend to communicate with your API during development and production.

python

CopyEdit

`app.include_router(facebook_oauth_router, prefix="/facebook")`

### Why use a router with a prefix?

Routers let us group related endpoints. Prefixing with `/facebook` keeps all Facebook OAuth routes organized and namespaced.

python

CopyEdit

`@app.get("/")
async def root():
    return {"status": "ok"}`

A simple health-check endpoint helps verify your API is running correctly.

python

CopyEdit

`if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)`

For development, we run the app with hot reload enabled --- speeding up testing and iteration.

* * * * *

Step 3: Create `facebook_oauth/routes.py` --- OAuth Routes Explained
------------------------------------------------------------------

python

CopyEdit

`from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_user_pages
import os

router = APIRouter()`

We start by importing FastAPI routing tools and our utility functions, grouping all Facebook OAuth endpoints under one router.

* * * * *

### Route 1: `/login` --- Initiate Facebook OAuth Flow

python

CopyEdit

`@router.get("/login")
async def start_oauth():
    client_id = os.getenv("FACEBOOK_APP_ID")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
    scope = "pages_messaging,pages_show_list"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Facebook app config missing")

    auth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"
    )

    return RedirectResponse(auth_url)`

### Why this design?

-   We **retrieve config from environment variables** securely --- no hardcoded secrets.

-   We define the **Facebook OAuth scope** we need (`pages_messaging` and `pages_show_list`) for the permissions our app requires.

-   If critical config is missing, we return a **clear 500 error** --- this is defensive programming to catch misconfigurations early.

-   We **build the OAuth URL manually** --- so we fully control parameters and understand the flow.

-   Returning a **redirect response** sends the user's browser to Facebook's login dialog --- initiating the OAuth flow cleanly.

* * * * *

### Route 2: `/callback` --- Handle OAuth Redirect & Exchange Code for Token

python

CopyEdit

`@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")

    token_data = await exchange_code_for_token(code)

    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    pages = await get_user_pages(token_data["access_token"])
    return JSONResponse(content={"token_data": token_data, "pages": pages})`

### Why these steps?

-   We **extract the OAuth `code` from the query params** that Facebook sends after user authorization.

-   If the code is missing, it means something went wrong (user denied permissions or error), so we return a **400 client error**.

-   We **call an async utility function** to exchange the code for a Facebook access token.

-   If token exchange fails (e.g., invalid code, expired), we return a detailed error to aid debugging.

-   With the access token, we fetch the user's Facebook Pages --- demonstrating practical use of the token.

-   Finally, we return a JSON response containing the token and the pages, which can be used by frontend or backend logic.

* * * * *

Step 4: Implement `facebook_oauth/utils.py` --- OAuth Helper Functions
--------------------------------------------------------------------

python

CopyEdit

`import os
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
        return response.json()`

### Why use `httpx.AsyncClient()` and async?

-   Using async HTTP requests **improves scalability** and responsiveness --- especially if this service grows or integrates with more APIs.

-   `httpx` is a modern alternative to `requests` that supports async out of the box.

-   `raise_for_status()` ensures we catch HTTP errors early and fail loudly rather than silently returning bad data.

* * * * *

python

CopyEdit

`async def get_user_pages(access_token: str):
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {"access_token": access_token}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()`

### Why fetch `/me/accounts`?

-   This endpoint returns a list of Facebook Pages the user manages.

-   This shows practical use of the OAuth token to fetch relevant data, which is critical for apps that interact with Facebook Pages.

-   Keeping this logic in utils keeps routes clean and focused on routing.

* * * * *

Step 5: Environment Variables --- `.env.example`
----------------------------------------------

env

CopyEdit

`FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback`

### Why environment variables?

-   Keep secrets and config out of code and version control.

-   Make it easy to switch between dev, staging, and production without code changes.

-   `.env.example` documents exactly which variables are needed for easy onboarding.

* * * * *

Step 6: Dependency Management --- `requirements.txt`
--------------------------------------------------

nginx

CopyEdit

`fastapi
uvicorn
python-dotenv
httpx`

### Why these dependencies?

-   **FastAPI** for modern, fast async API framework.

-   **Uvicorn** for ASGI server with hot reload during development.

-   **python-dotenv** to manage environment variables easily.

-   **httpx** for async HTTP client, better than synchronous `requests` in an async app.

* * * * *

Bonus: `.gitignore`
-------------------

Your `.gitignore` excludes:

-   Python cache files (`__pycache__`, `.pyc`)

-   Environment files (`.env`) to avoid leaking secrets

-   IDE files and OS system files like `.DS_Store`

### Why?

-   Keeps your repo clean.

-   Protects sensitive data.

-   Ensures only relevant source code is committed.

* * * * *

Summary: Why This Design Shows Your Python Skills
=================================================

-   **Modularity**: Separating routes and utils, clean file structure.

-   **Security**: Using env vars, careful config checks, not exposing secrets.

-   **Scalability**: Async HTTP requests for non-blocking IO.

-   **Error handling**: Defensive programming with proper HTTP exceptions.

-   **Clear comments & doc**: Explaining intent and flow --- essential for maintainability.

-   **Professional best practices**: CORS, clean API routing, dependency management.