Step-by-Step Tutorial: Building Facebook OAuth with FastAPI — Explained and Designed Right
This tutorial guides you through building a secure, modular, and scalable Facebook OAuth integration using FastAPI. Each step demonstrates professional Python development practices, including clean code organization, secure configuration, and async programming for scalability.
Step 1: Setup Your Project Structure
Organize your code in a clean, modular way to ensure maintainability and scalability:
.
├── facebook_oauth
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── .env.example
├── .gitignore
├── app.py
├── LICENSE
├── README.md
└── requirements.txt


facebook_oauth/: Contains all OAuth-related logic, keeping concerns separated.
app.py: The FastAPI entry point, setting up the app and routes.
.env.example: Documents environment variables needed for configuration.
requirements.txt: Manages dependencies.

Why this structure?This modular design supports maintainability and scalability, key for professional projects.
Step 2: Prepare app.py — The FastAPI Application Entry
Create the main FastAPI application in app.py:
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Facebook OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Relaxed in dev, lock down in production for security
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


Why load_dotenv()?Loads sensitive data (e.g., Facebook App secrets) from a .env file into environment variables, keeping secrets out of code and version control.
Why CORS middleware?Enables communication between your frontend and API when served from different domains, critical for browser-based apps.
Why router with prefix?Grouping endpoints under /facebook organizes OAuth routes clearly.
Why health-check endpoint?The GET / endpoint verifies the API is running correctly during development.

Step 3: Create facebook_oauth/routes.py — OAuth Routes Explained
Define OAuth-related endpoints in facebook_oauth/routes.py:
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_user_pages
import os

router = APIRouter()

@router.get("/login")
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

    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")

    token_data = await exchange_code_for_token(code)

    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    pages = await get_user_pages(token_data["access_token"])
    return JSONResponse(content={"token_data": token_data, "pages": pages})


Route 1: /loginInitiates the OAuth flow by redirecting the user to Facebook’s login dialog. Uses environment variables for secure configuration and specifies required scopes (pages_messaging, pages_show_list).
Route 2: /callbackHandles the redirect from Facebook, extracts the authorization code, exchanges it for an access token, and fetches the user’s managed pages. Returns a JSON response with token and page data.
Why this design?Defensive programming (e.g., checking for missing config or code) ensures robust error handling. Async utilities keep routes clean and focused.

Step 4: Implement facebook_oauth/utils.py — OAuth Helper Functions
Create helper functions in facebook_oauth/utils.py for reusable logic:
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

async def get_user_pages(access_token: str):
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {"access_token": access_token}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


Why async with httpx?Async HTTP requests improve scalability and responsiveness, especially for API-heavy applications. httpx is a modern, async-compatible alternative to requests.
Why these functions?exchange_code_for_token securely exchanges the OAuth code for an access token. get_user_pages fetches the user’s managed Facebook Pages, demonstrating practical token usage.
Why in utils.py?Keeps routes focused on routing logic, improving modularity and reusability.

Step 5: Environment Variables — .env.example
Document required environment variables in .env.example:
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback


Why environment variables?Keeps secrets out of code and version control. Allows easy configuration switching between dev, staging, and production. .env.example simplifies onboarding by showing required variables.

Step 6: Dependency Management — requirements.txt
List dependencies in requirements.txt:
fastapi
uvicorn
python-dotenv
httpx


Why these dependencies?  
fastapi: Modern, async API framework.
uvicorn: ASGI server with hot reload for development.
python-dotenv: Simplifies environment variable management.
httpx: Async HTTP client for scalable API calls.



Step 7: .gitignore
Exclude sensitive and unnecessary files in .gitignore:
__pycache__/
*.pyc
.env
*.DS_Store


Why?Prevents committing sensitive data (e.g., .env), Python cache files, or IDE/OS-specific files, keeping the repository clean and secure.

Summary: Why This Design Shows Your Python Skills

Modularity: Clean separation of routes, utilities, and configuration.
Security: Environment variables and defensive error handling prevent leaks and misconfigurations.
Scalability: Async programming with httpx ensures non-blocking I/O.
Error Handling: Proper HTTP exceptions provide clear feedback.
Best Practices: CORS, organized routing, and dependency management align with professional standards.

This tutorial provides a production-ready foundation for Facebook OAuth with FastAPI, balancing simplicity with robust design.
