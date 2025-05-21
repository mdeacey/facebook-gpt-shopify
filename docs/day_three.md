### Documentation: /docs/DAY-THREE.md

```markdown
# Chapter 3: Building Chained Facebook and Shopify OAuth with FastAPI — Separated Concerns

This chapter guides you through implementing a chained OAuth flow in your FastAPI application, where users provide a Shopify shop name at `/{shop_name}/login` to authenticate with Facebook first, then Shopify. Each OAuth flow handles only its own tasks: Facebook OAuth manages Facebook authentication and data, while Shopify OAuth manages Shopify authentication and data. The `shop_name` is passed through the flow using the OAuth `state` parameter, ensuring a stateless design. We’ll explain each component, its purpose, and why this approach aligns with professional Python development practices.

---

## Step 1: Update the Project Structure for Shopify

To support the chained OAuth flow, we extend the project structure with a `shopify_oauth` package, maintaining modularity alongside the `facebook_oauth` package. The updated structure is:

```
└── ./
    ├── docs
    │   ├── DAY-ONE.md
    │   ├── DAY-TWO.md
    │   └── DAY-THREE.md
    ├── facebook_oauth
    │   ├── __init__.py
    │   ├── routes.py
    │   └── utils.py
    ├── shopify_oauth
    │   ├── __init__.py
    │   ├── routes.py
    │   └── utils.py
    ├── .env.example
    ├── .gitignore
    ├── app.py
    ├── LICENSE
    └── requirements.txt
```

- **shopify_oauth/**: Contains Shopify OAuth logic, mirroring `facebook_oauth` for consistency.
- **app.py**: Includes a new `/{shop_name}/login` endpoint to start the chained flow and Shopify routes.
- **.env.example**: Documents Shopify-specific environment variables.
- **requirements.txt**: Unchanged, as existing dependencies support both OAuth flows.

**Why this structure?**  
The modular design separates Facebook and Shopify logic, ensuring maintainability and scalability. The top-level `/{shop_name}/login` endpoint provides a clear entry point for the chained flow.

---

## Step 2: Update app.py — Add Chained OAuth Entry Point

The main FastAPI application in `app.py` is updated to include Shopify routes and a `/{shop_name}/login` endpoint to initiate the chained flow:

```python
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from shopify_oauth.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")
app.include_router(shopify_oauth_router, prefix="/shopify")

@app.get("/{shop_name}/login")
async def start_chained_oauth(shop_name: str):
    # Redirect to Facebook OAuth login, passing shop_name in state parameter
    return {"redirect": f"/facebook/login?state={shop_name}"}

@app.get("/")
async def root():
    return {"status": "ok", "message": "Provide shop name at /{shop_name}/login to start chained OAuth"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**What’s changed?**
- Added `/{shop_name}/login` to start the Facebook OAuth flow, passing `shop_name` in the `state` parameter.
- Updated the root endpoint to guide users to use `/{shop_name}/login`.

**Why these changes?**  
- **Chained Entry Point**: The `/{shop_name}/login` endpoint initiates the flow with Facebook OAuth, using `state` to carry `shop_name` without server-side storage.
- **User Guidance**: The root message clarifies the entry point for the chained flow.
- **CORS and Environment**: Reuses CORS middleware and `load_dotenv()` for secure configuration and frontend compatibility.

---

## Step 3: Update facebook_oauth/routes.py — Handle Facebook OAuth

The Facebook OAuth routes in `facebook_oauth/routes.py` handle authentication and redirect to Shopify OAuth:

```python
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_user_pages

router = APIRouter()

@router.get("/login")
async def start_oauth(state: str | None = None):
    client_id = os.getenv("FACEBOOK_APP_ID")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
    scope = "pages_messaging,pages_show_list"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Facebook app config missing")

    auth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"
    )
    if state:
        auth_url += f"&state={state}"

    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state parameter")

    token_data = await exchange_code_for_token(code)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    pages = await get_user_pages(token_data["access_token"])
    
    # Return Facebook data and suggest Shopify redirect
    response = JSONResponse(content={"token_data": token_data, "pages": pages})
    response.headers["X-Shopify-Redirect"] = f"/shopify/{state}/login"
    return response
```

**Route Details**:
- **/login**: Initiates Facebook OAuth, appending the `state` parameter (containing `shop_name`) to the authorization URL.
- **/callback**: Exchanges the authorization code for a token, fetches user pages, and returns the Facebook data. A custom header (`X-Shopify-Redirect`) suggests the next step (`/shopify/{state}/login`) for the client to follow.

**Why this design?**  
- **Separation of Concerns**: The endpoint handles only Facebook OAuth tasks, returning Facebook data without touching Shopify logic.
- **Stateless**: The `state` parameter carries `shop_name` to the next step.
- **Client-Driven Chaining**: The custom header allows the client to initiate Shopify OAuth, keeping the server stateless.

---

## Step 4: Create shopify_oauth/routes.py — Handle Shopify OAuth

The Shopify OAuth routes in `shopify_oauth/routes.py` handle only Shopify authentication and data:

```python
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shop_info

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_products,write_products,read_orders"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify app config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&response_type=code"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")

    if not code or not shop:
        raise HTTPException(status_code=400, detail="Missing code or shop parameter")

    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    shop_info = await get_shop_info(token_data["access_token"], shop)
    return JSONResponse(content={"token_data": token_data, "shop_info": shop_info})
```

**Route Details**:
- **/{shop_name}/login**: Initiates Shopify OAuth by redirecting to the shop’s authorization URL, ensuring `shop_name` includes `.myshopify.com`.
- **/callback**: Exchanges the code for an access token, fetches shop info, and returns only Shopify data.

**Why this design?**  
- **Separation of Concerns**: Handles only Shopify OAuth tasks, returning Shopify-specific data.
- **Stateless**: Uses the `shop_name` from the URL and query parameters, requiring no server-side storage.
- **RESTful**: The `/{shop_name}/login` path aligns with RESTful conventions.

---

## Step 5: Implement shopify_oauth/utils.py — Shopify Helper Functions

The helper functions in `shopify_oauth/utils.py` remain unchanged:

```python
import os
import httpx

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

async def get_shop_info(access_token: str, shop: str):
    url = f"https://{shop}/admin/api/2023-04/shop.json"
    headers = {"X-Shopify-Access-Token": access_token}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
```

**Why these functions?**  
- **Async**: `httpx.AsyncClient` ensures non-blocking I/O.
- **Modularity**: Separates logic from routes, improving reusability.
- **Security**: Uses environment variables for sensitive credentials.

---

## Step 6: Update Environment Variables — .env.example

The `.env.example` file includes variables for both OAuth flows:

```
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback

# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
```

**Why these variables?**  
- Authenticate with Facebook and Shopify OAuth systems.
- `SHOPIFY_REDIRECT_URI` specifies the callback URL (`/shopify/callback`).
- Stored in `.env` for security.

---

## Step 7: Reuse Existing Dependencies — requirements.txt

The `requirements.txt` file remains unchanged:

```
fastapi
uvicorn
python-dotenv
httpx
```

**Why no changes?**  
- **fastapi**: Powers endpoints and routing.
- **uvicorn**: Runs the ASGI server.
- **python-dotenv**: Manages environment variables.
- **httpx**: Handles async HTTP requests.

---

## Step 8: .gitignore and LICENSE

No changes needed for `.gitignore` or `LICENSE`, as they already cover sensitive files and the MIT License.

**Why no changes?**  
- **.gitignore**: Excludes `.env` and other artifacts.
- **LICENSE**: MIT License remains applicable.

---

## Step 9: Testing the Chained OAuth Flow

To test the chained flow:
1. Create a Facebook app (per Chapter 2) and add `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, and `FACEBOOK_REDIRECT_URI` to `.env`.
 CREATE A SHOPIFY APP IN THE SHOPIFY PARTNER DASHBOARD AND ADD `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, AND `SHOPIFY_REDIRECT_URI` TO `.ENV`.
3. Run the FastAPI app (`python app.py`).
4. Visit `http://localhost:5000/yourshopname/login` (replace `yourshopname` with your Shopify store name, e.g., `mystorename` or `mystorename.myshopify.com`).
5. Complete Facebook OAuth, which returns a JSON response with Facebook data (`token_data` and `pages`) and an `X-Shopify-Redirect` header pointing to `/shopify/yourshopname/login`.
6. Follow the redirect (manually or programmatically) to complete Shopify OAuth, which redirects to `/shopify/callback`.
7. Verify the Shopify callback returns only Shopify data (`token_data` and `shop_info`).

**Why test this way?**  
- Ensures the chained flow works: from `/{shop_name}/login` to Facebook OAuth, then Shopify OAuth.
- Confirms each endpoint handles only its own data.
- Validates the `state` parameter passes `shop_name` correctly.

**Note**: The client must handle the Facebook data from `/facebook/callback` and follow the `X-Shopify-Redirect` header to initiate Shopify OAuth. In a frontend, this can be automated using JavaScript.

---

## Summary: Why This Design Shows Your Python Skills

- **Separation of Concerns**: Facebook and Shopify OAuth flows are independent, each handling only its own data and tasks.
- **Statelessness**: The `state` parameter carries `shop_name` through redirects, eliminating server-side storage.
- **Security**: Environment variables and error handling prevent leaks and misconfigurations.
- **Scalability**: Async `httpx` requests ensure non-blocking I/O.
- **Flexibility**: The `/{shop_name}/login` endpoint supports any Shopify store.
- **RESTful Design**: Hierarchical URLs (`/shopify/{shop_name}/login`) align with conventions.
- **Best Practices**: Modular routing, CORS, and dependency reuse reflect professional standards.

This implementation delivers a production-ready, stateless chained OAuth flow, keeping Facebook and Shopify tasks separate while maintaining a seamless user experience.
```

---

### Notes
- **Why This Approach?** 
  - **Separation of Concerns**: The Facebook OAuth callback returns only Facebook data (`token_data` and `pages`), and the Shopify callback returns only Shopify data (`token_data` and `shop_info`). This ensures each module handles its own responsibilities.
  - **Stateless**: Using the `state` parameter to pass `shop_name` avoids server-side storage, making the API robust and scalable.
  - **Client Responsibility**: The client (e.g., a frontend) must handle the Facebook data from `/facebook/callback` and follow the `X-Shopify-Redirect` header to start Shopify OAuth. This keeps the server stateless and aligns with OAuth best practices.
- **Why `X-Shopify-Redirect` Header?** Instead of an automatic redirect, the header allows the client to decide how to proceed, providing flexibility (e.g., storing Facebook data before continuing). In a frontend, JavaScript can read the header and navigate to the Shopify login URL.
- **Production Considerations**: In a real application, you might use a frontend to orchestrate the flow or add a session middleware (e.g., `fastapi_sessions`) to temporarily store Facebook data if needed, but the current design avoids this for simplicity and statelessness.
- **No Placeholders**: The code is complete, with each endpoint returning its full, relevant data.

This `DAY-THREE.md` is ready to be saved in your project. Let me know if you need further refinements, such as adding client-side code examples to handle the redirects or integrating a session system for production!