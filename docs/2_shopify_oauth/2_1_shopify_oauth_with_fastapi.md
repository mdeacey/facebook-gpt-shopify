Chapter 2: Shopify Integration
Subchapter 2.1: Implementing Shopify OAuth with FastAPI
This subchapter implements the Shopify OAuth flow in our FastAPI application to authenticate with Shopify and fetch raw data for the GPT Messenger sales bot. The flow retrieves shop details, products, discount codes, and collections using a single GraphQL Admin API call (version 2025-04). Data preprocessing is deferred to Subchapter 2.4, keeping this subchapter focused on authentication and raw data retrieval. The implementation mirrors Subchapter 1.1 (Facebook OAuth), using a modular structure, async programming, and stateless CSRF protection. We assume the Shopify development store and app credentials are set up in Subchapter 2.2, with testing covered in Subchapter 2.3.

Step 1: Why Shopify OAuth?
The sales bot promotes products, shares discounts, and generates Messenger preview cards, requiring secure access to Shopify data:

Shop Details: Name and primary domain for branding and URL generation.
Products: Titles, variants, inventory, and metafields (e.g., snowboard length).
Discounts: Codes, titles, values, and validity dates for promotions.
Collections: Titles and grouped products for recommendations.

A single GraphQL query fetches this data efficiently, with preprocessing in Subchapter 2.4 tailoring it for the sales bot.

Step 2: Project Structure
Building on Chapter 1, we add a shopify_oauth module alongside facebook_oauth:
.
├── facebook_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shopify_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shared/
│   └── utils.py          # Stateless CSRF helpers
├── .env
├── .env.example
├── app.py
└── requirements.txt


shopify_oauth/: Contains Shopify OAuth routes and GraphQL utilities.
shared/utils.py: Reuses CSRF state token helpers from Subchapter 1.1.
app.py: Registers both Facebook and Shopify OAuth routes.
.env.example: Includes Shopify credentials (added in Subchapter 2.2).


Step 3: Update app.py
Modify app.py to include the Shopify OAuth router, supporting both Facebook and Shopify endpoints.
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

Why?

The shopify_oauth_router is mounted under /shopify, enabling endpoints like /shopify/{shop_name}/login.
CORS middleware supports frontend integration, consistent with Subchapter 1.1.
The root endpoint guides users to available OAuth flows, testable in Subchapter 2.3.


Step 4: Create shopify_oauth/routes.py
This module defines two endpoints: /shopify/{shop_name}/login to initiate OAuth and /shopify/callback to handle the redirect and fetch preprocessed data.
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, preprocess_shopify_data
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
    preprocessed_data = preprocess_shopify_data(shopify_data)
    return JSONResponse(content={
        "token_data": token_data,
        "preprocessed_data": preprocessed_data
    })

Why?

Login Endpoint: Builds the OAuth URL with the shop name (e.g., acme-7cu19ngr.myshopify.com), SHOPIFY_API_KEY, SHOPIFY_REDIRECT_URI, and scopes. The state token reuses Subchapter 1.1’s CSRF protection.
Callback Endpoint: Validates the state token, exchanges the code for an access token, fetches raw GraphQL data, and preprocesses it using preprocess_shopify_data (from Subchapter 2.4). Returns token_data and preprocessed_data for testing in Subchapter 2.3.
Preprocessing Integration: Including preprocess_shopify_data ensures the response is sales-bot-ready, consistent with Subchapter 2.3’s output.


Step 5: Create shopify_oauth/utils.py
This module handles token exchange, GraphQL data fetching, and preprocessing (implemented in Subchapter 2.4).
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

def preprocess_shopify_data(raw_data: dict) -> dict:
    """
    Placeholder for preprocessing function (implemented in Subchapter 2.4).
    Transforms raw GraphQL data into sales-bot-friendly JSON.
    """
    # Actual implementation in Subchapter 2.4
    return raw_data.get("data", {})

Why?

Token Exchange: exchange_code_for_token securely fetches an access token using credentials from Subchapter 2.2.
GraphQL Query: get_shopify_data retrieves shop, product, discount, and collection data in one optimized query, supporting the sales bot’s needs.
Retry Logic: Handles rate limits (HTTP 429) with exponential backoff for reliability.
Preprocessing Placeholder: Includes a stub for preprocess_shopify_data, fully implemented in Subchapter 2.4, to ensure the module is complete.
Error Handling: Raises clear HTTP exceptions for robust error reporting.


Step 6: Configure Environment Variables
Add Shopify credentials to your .env file, obtained from the Shopify app in Subchapter 2.2. The .env.example guides configuration.
.env.example:
# Facebook OAuth credentials (from Subchapter 1.2)
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback

# Shopify OAuth credentials (from Subchapter 2.2)
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback

# Shared secret for state token CSRF protection (from Subchapter 1.1)
STATE_TOKEN_SECRET=replace_with_secure_token

Why?

Credentials: SHOPIFY_API_KEY and SHOPIFY_API_SECRET (from Subchapter 2.2) authenticate the OAuth flow.
Redirect URI: Matches the callback endpoint, configurable for local or Codespaces environments.
CSRF Secret: Reuses STATE_TOKEN_SECRET from Subchapter 1.1 for consistent security.
Comprehensive Example: Includes both Facebook and Shopify variables, ensuring all dependencies are clear.


Step 7: Update requirements.txt
Ensure dependencies support both integrations, consistent with Chapter 1.
requirements.txt:
fastapi
uvicorn
httpx
python-dotenv

Why?

No additional dependencies are needed beyond Subchapter 1.1, as Shopify OAuth uses the same libraries (httpx for HTTP, python-dotenv for variables).


Step 8: Testing Preparation
Testing is covered in Subchapter 2.3, where you’ll:

Run the app (python app.py).
Navigate to /shopify/acme-7cu19ngr/login to initiate OAuth.
Verify the /shopify/callback response contains token_data and preprocessed_data.

For now, you can:

Install dependencies: pip install -r requirements.txt.
Start the server: python app.py.
Access http://localhost:5000 to confirm the root response: {"status": "ok", "message": "Use /facebook/login or /shopify/{shop_name}/login"}.

Note: You’ll need the Shopify store and app credentials from Subchapter 2.2 to proceed with OAuth.

Summary: Why This Subchapter Matters

Secure Authentication: Implements Shopify OAuth with CSRF protection, enabling access to shop data.
Efficient Data Retrieval: Uses a single GraphQL query to fetch all necessary data, optimized for the sales bot.
Modular Design: Mirrors Subchapter 1.1’s structure, ensuring consistency and reusability.
Bot Preparation: Fetches raw data, ready for preprocessing in Subchapter 2.4 to support product recommendations and promotions.

Next Steps:

Create a Shopify development store and app to obtain credentials (Subchapter 2.2).
Test the OAuth flow and data retrieval (Subchapter 2.3).
Preprocess the raw data for the sales bot (Subchapter 2.4).
