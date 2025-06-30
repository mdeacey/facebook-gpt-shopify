Absolutely — here is the **fully updated Chapter 3**, matching your structure, keeping code and implementation focused, and correcting the `.env` keys for consistency with your actual OAuth variables (`SHOPIFY_API_KEY`, not `CLIENT_ID`, etc.).

---

# Chapter 3: Implementing Shopify OAuth with FastAPI for a Sales Bot

In this chapter, we implement a Shopify OAuth flow in your FastAPI application to authenticate with Shopify and fetch raw data for a GPT Messenger sales bot. The flow retrieves shop details, products, discount codes, and collections in a single, optimized GraphQL Admin API call. Preprocessing is deferred to Chapter 5. This chapter mirrors the structure from Chapter 2 (Facebook OAuth), explaining each step, its purpose, and alignment with professional Python development practices.

---

## Step 1: Why Shopify OAuth?

The sales bot promotes products, shares discounts, and links Messenger preview cards. OAuth securely authenticates access to Shopify data:

* **Shop Details**: Name and primary domain (for URL generation).
* **Products**: Variants, inventory, metafields.
* **Discounts**: Title, codes, values, start/end dates.
* **Collections**: Titles and grouped products.

Raw GraphQL data preserves flexibility for tailored preprocessing in Chapter 5.

---

## Step 2: Project Structure

```txt
.
├── facebook_oauth/
├── shopify_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shared/
│   └── utils.py          # <- Stateless CSRF helpers
├── .env.example
├── app.py
├── requirements.txt
```

* `shopify_oauth/`: Contains Shopify OAuth routes and GraphQL utilities.
* `shared/utils.py`: Reused CSRF-safe `state` token helpers.
* `app.py`: Registers both Facebook and Shopify OAuth routes.

---

## Step 3: Update `app.py`

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
```

---

## Step 4: `shopify_oauth/routes.py`

```python
import os
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

    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    return JSONResponse(content={
        "token_data": token_data,
        "shopify_data": shopify_data.get("data", {})
    })
```

---

## Step 5: `shopify_oauth/utils.py`

```python
import os
import httpx
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
            products(first: 5) {
              edges { node { title } }
            }
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

---

## Step 6: `.env.example`

```env
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret

# Shopify redirect URI for local dev
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback

# Or for GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
```

---

## Step 7: `requirements.txt`

```txt
fastapi
uvicorn
httpx
python-dotenv
```

---

✅ Let me know when you're ready and I’ll send the **corrected Chapter 4** next, with this implementation in mind.
