# Chapter 2: Shopify Integration
## Subchapter 2.1: Implementing Shopify OAuth with FastAPI

This subchapter implements the Shopify OAuth flow in our FastAPI application to authenticate with Shopify and fetch raw data for the GPT Messenger sales bot. The flow retrieves shop details, products, discount codes, and collections using a single GraphQL Admin API call (version 2025-04). A UUID is generated to uniquely identify the user’s data, preparing for multi-platform integration in later chapters. The implementation builds on Chapter 1’s modular structure, using async programming, environment variable validation, and stateless CSRF protection. Access tokens and UUIDs are stored in environment variables, with persistent storage introduced in Chapter 3. We assume the Shopify development store and app credentials are set up in Subchapter 2.2, with testing covered in Subchapter 2.3.

### Step 1: Why Shopify OAuth?
The sales bot promotes products, shares discounts, and generates Messenger preview cards, requiring secure access to Shopify data:
- **Shop Details**: Name and primary domain for branding and URLs.
- **Products**: Titles, variants, inventory, and metafields.
- **Discounts**: Codes, titles, values, and validity dates.
- **Collections**: Titles and grouped products for recommendations.
A UUID is generated to prepare for linking data across platforms in Chapter 3.

### Step 2: Project Structure
Building on Chapter 1, we add a `shopify_integration` module:
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
│   └── utils.py
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `shopify_integration/` contains Shopify OAuth routes and utilities.
- `shared/utils.py` reuses CSRF protection from Chapter 1.
- Modular design avoids future features (e.g., session management, webhooks) introduced in Chapters 3–6.

### Step 3: Update `app.py`
Modify `app.py` to include the Shopify OAuth router and validate environment variables.

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
- **Router**: Mounts `shopify_oauth_router` under `/shopify` for endpoints like `/shopify/{shop_name}/login`.
- **Environment Validation**: Ensures Shopify credentials are set, improving reliability.
- **CORS**: Enables frontend interaction for OAuth redirects.
- **Root Endpoint**: Guides users to both OAuth flows.
- **No Future Features**: Excludes webhooks, polling, or session management (introduced in Chapters 3–6).

### Step 4: Create `shopify_integration/routes.py`
This module defines two endpoints: `/shopify/{shop_name}/login` to initiate OAuth and `/shopify/callback` to handle the redirect and fetch data.

```python
import os
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data
from shared.utils import generate_state_token, validate_state_token

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

    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    return JSONResponse(content={
        "user_uuid": user_uuid,
        "token_data": token_data,
        "shopify_data": shopify_data
    })
```

**Why?**
- **Login Endpoint**: Builds the OAuth URL with shop name, `SHOPIFY_API_KEY`, `SHOPIFY_REDIRECT_URI`, and scopes.
- **Callback Endpoint**: Validates the state token, exchanges the code for an access token, generates a UUID, stores tokens and UUID in `os.environ`, and returns raw data with the UUID.
- **UUID**: Prepares for multi-platform linking in Chapter 3.
- **No Sessions or Webhooks**: Session management and webhooks are introduced in Chapters 3–5.
- **Security**: Stores tokens server-side, excludes them from responses (persistent storage in Chapter 3).

### Step 5: Create `shopify_integration/utils.py`
This module handles token exchange and GraphQL data fetching.

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
- **Token Exchange**: Fetches an access token for Shopify API access.
- **GraphQL Query**: Retrieves shop, product, discount, and collection data in a single call.
- **Retry Logic**: Handles rate limits with exponential backoff.
- **Error Handling**: Raises clear HTTP exceptions for debugging.
- **No Webhooks**: Webhook functions are introduced in Chapter 5.

### Step 6: Configure Environment Variables
Add Shopify credentials to `.env.example`.

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
```

**Why?**
- **Credentials**: Authenticate the Shopify OAuth flow.
- **Redirect URI**: Matches the callback endpoint in `routes.py`.
- **CSRF Secret**: Reuses `STATE_TOKEN_SECRET` from Chapter 1 for consistency.
- **No Future Variables**: Excludes webhook or Spaces variables (introduced in Chapters 5–6).

### Step 7: Update `requirements.txt`
Ensure dependencies support both Facebook and Shopify OAuth.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
```

**Why?**
- **No Additional Dependencies**: Reuses Chapter 1’s dependencies (`apscheduler`, `boto3`, `cryptography` introduced in Chapters 3–6).
- **HTTPX**: Handles async HTTP requests for Shopify API.
- **python-dotenv**: Loads `.env` variables.

### Step 8: Git Ignore — `.gitignore`
Use the same `.gitignore` as Chapter 1, as persistent storage is introduced in Chapter 3.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
```

**Why?**
- Excludes compiled files, `.env`, and macOS-specific files.
- SQLite databases (`*.db`) are added in Chapter 3.

### Step 9: Testing Preparation
Testing is covered in Subchapter 2.3:
- Update `.env` with `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI` (Subchapter 2.2).
- Install dependencies: `pip install -r requirements.txt`.
- Run: `python app.py`.
- Navigate to `/shopify/acme-7cu19ngr/login` to initiate OAuth.

**Why?**
- Ensures the setup is complete before testing the OAuth flow.

### Summary: Why This Subchapter Matters
- **Secure Authentication**: Implements Shopify OAuth with CSRF protection and environment validation.
- **Efficient Data Retrieval**: Uses a single GraphQL query for shop and product data.
- **UUID Generation**: Prepares for multi-platform linking in Chapter 3.
- **Modular Design**: Builds on Chapter 1, avoiding future features like sessions or webhooks.
- **Production Note**: Persistent storage for tokens and UUIDs is introduced in Chapter 3.

### Next Steps:
- Create a Shopify development store and app (Subchapter 2.2).
- Test the OAuth flow (Subchapter 2.3).