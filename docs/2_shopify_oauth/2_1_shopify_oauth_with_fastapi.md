# Chapter 2: Shopify Integration
## Subchapter 2.1: Implementing Shopify OAuth with FastAPI

This subchapter implements the Shopify OAuth flow in our FastAPI application to authenticate with Shopify and fetch raw data for the GPT Messenger sales bot. The flow retrieves shop details, products, discount codes, and collections using a single GraphQL Admin API call (version 2025-04). A UUID is generated to uniquely identify the user’s data, preparing for multi-platform integration in later chapters. Data preprocessing is deferred to a later chapter, focusing here on authentication and raw data retrieval. The implementation builds on Chapter 1’s modular structure, using async programming and stateless CSRF protection. We assume the Shopify development store and app credentials are set up in Subchapter 2.2, with testing covered in Subchapter 2.3.

### Step 1: Why Shopify OAuth?
The sales bot promotes products, shares discounts, and generates Messenger preview cards, requiring secure access to Shopify data:
- **Shop Details**: Name and primary domain for branding and URLs.
- **Products**: Titles, variants, inventory, and metafields.
- **Discounts**: Codes, titles, values, and validity dates.
- **Collections**: Titles and grouped products for recommendations.
A UUID is generated to group data across platforms in later integrations.

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
- Modular design supports future integrations.

### Step 3: Update `app.py`
Modify `app.py` to include the Shopify OAuth router.

```python
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
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
- Mounts `shopify_oauth_router` under `/shopify` for endpoints like `/shopify/{shop_name}/login`.
- Updates root endpoint to guide users to both OAuth flows.

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
- **Callback Endpoint**: Validates the state token, exchanges the code for an access token, generates a UUID, stores it server-side, and returns raw data with the UUID.
- **UUID**: Prepares for multi-platform linking in later chapters.

### Step 5: Create `shopify_integration/utils.py`
This module handles token exchange and GraphQL data fetching.

```python
import os
import httpx
import json
from fastapi import HTTPException
import asyncio

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
- **Token Exchange**: Fetches an access token.
- **GraphQL Query**: Retrieves shop, product, discount, and collection data.
- **Retry Logic**: Handles rate limits.
- **Error Handling**: Raises clear HTTP exceptions.

### Step 6: Configure Environment Variables
Add Shopify credentials to `.env`.

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
- Combines credentials for both integrations.
- Provides local and Codespaces options.

### Step 7: Update `requirements.txt`
Ensure dependencies support both integrations.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
```

**Why?**
- No additional dependencies needed beyond Chapter 1.

### Step 8: Testing Preparation
Testing is covered in Subchapter 2.3:
- Run: `python app.py`.
- Navigate to `/shopify/acme-7cu19ngr/login`.
- Verify `/shopify/callback` response contains `user_uuid` and `shopify_data`.

### Summary: Why This Subchapter Matters
- **Secure Authentication**: Implements Shopify OAuth with CSRF protection.
- **Efficient Data Retrieval**: Uses a single GraphQL query.
- **UUID Generation**: Prepares for multi-platform linking.
- **Modular Design**: Ensures consistency with Chapter 1.

### Next Steps:
- Create a Shopify development store and app (Subchapter 2.2).
- Test the OAuth flow (Subchapter 2.3).