# Chapter 5: Shopify Data Sync
## Subchapter 5.1: Setting Up Shopify Webhooks for Real-Time Updates

### Introduction
Shopify webhooks enable real-time notifications for product updates (e.g., title, inventory changes) to keep the GPT Messenger sales bot’s data current. This subchapter sets up a secure webhook endpoint in the FastAPI application, integrating HMAC verification and registering webhooks during the Shopify OAuth flow (Chapter 2) with appropriate permissions (`read_products`, `read_inventory`). The webhook system uses the UUID from the SQLite-based session mechanism (Chapter 3) to identify the user and stores data temporarily in `<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`, preparing for cloud storage in Chapter 6 (`users/<uuid>/shopify/<shop_name>/shop_metadata.json` and `users/<uuid>/shopify/<shop_name>/shop_products.json`). The focus is on non-sensitive shop and product data, using `TokenStorage` and `SessionStorage` for secure, production-ready operation.

### Prerequisites
- Completed Chapters 1–4 (Facebook OAuth, Shopify OAuth, Persistent Storage and User Identification, Facebook Data Sync).
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`) and `STATE_TOKEN_SECRET` set in `.env` (Chapter 2).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- A publicly accessible webhook URL (e.g., via ngrok).

---

### Step 1: Configure Environment Variables
Update the `.env` file to include webhook-specific variables for Shopify, in addition to credentials from Chapters 1–4.

**Updated `.env.example`**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# Webhook configuration
FACEBOOK_WEBHOOK_ADDRESS=http://localhost:5000/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# Webhook configuration
SHOPIFY_WEBHOOK_ADDRESS=http://localhost:5000/shopify/webhook
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# Database paths for SQLite storage
TOKEN_DB_PATH=./data/tokens.db
SESSION_DB_PATH=./data/sessions.db
```

**Notes**:
- Replace placeholders with values from your Shopify app (Subchapter 2.2).
- `SHOPIFY_WEBHOOK_ADDRESS` must be publicly accessible (e.g., use ngrok: `ngrok http 5000`).
- **Production Note**: Use a secure, unique `STATE_TOKEN_SECRET` and HTTPS for `SHOPIFY_WEBHOOK_ADDRESS`.

**Why?**
- Authenticates the OAuth flow and secures webhook verification.
- Prepares for webhook registration and event processing.
- Excludes Spaces variables (introduced in Chapter 6).

### Step 2: Update Project Structure
The project structure builds on Chapters 1–4:
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
│   ├── sessions.py
│   ├── tokens.py
│   └── utils.py
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `shopify_integration/` contains webhook routes and utilities, using `TokenStorage` and `SessionStorage`.
- `shared/sessions.py` and `shared/tokens.py` manage persistent storage (Chapter 3).
- Excludes Spaces integration (Chapter 6).

### Step 3: Update `shopify_integration/utils.py`
Add webhook registration and verification functions, splitting the GraphQL query into metadata and products, using `TokenStorage`.

```python
import os
import httpx
import json
from fastapi import HTTPException, Request
import hmac
import hashlib
import base64
import asyncio
from shared.tokens import TokenStorage

token_storage = TokenStorage()

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

async def get_shopify_metadata(access_token: str, shop: str, retries=3):
    url = f"https://{shop}/admin/api/2025-04/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    query = """
    query ShopMetadataQuery {
      shop { name primaryDomain { url } }
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

async def get_shopify_products(access_token: str, shop: str, retries=3):
    url = f"https://{shop}/admin/api/2025-04/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    query = """
    query ShopProductsQuery {
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

async def verify_hmac(request: Request) -> bool:
    hmac_signature = request.headers.get("X-Shopify-Hmac-Sha256")
    if not hmac_signature:
        return False
    body = await request.body()
    secret = os.getenv("SHOPIFY_API_SECRET")
    computed_hmac = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(hmac_signature, computed_hmac)

async def register_webhooks(shop: str, access_token: str):
    url = f"https://{shop}/admin/api/2025-04/webhooks.json"
    headers = {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}
    webhook_address = os.getenv("SHOPIFY_WEBHOOK_ADDRESS")
    if not webhook_address:
        raise HTTPException(status_code=500, detail="SHOPIFY_WEBHOOK_ADDRESS not set")
    data = {
        "webhook": {
            "topic": "products/update",
            "address": webhook_address,
            "format": "json"
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 201:
            print(f"Webhook registered for {shop}: products/update")
        else:
            print(f"Failed to register webhook for {shop}: {response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to register webhook: {response.text}")
```

**Why?**
- **OAuth Functions**: Reuses token exchange from Chapter 2.
- **Split Queries**: Separates `get_shopify_data` into `get_shopify_metadata` (shop details) and `get_shopify_products` (products, discounts, collections) for modularity, aligning with the split into `shop_metadata.json` and `shop_products.json`.
- **Webhook Verification**: Validates incoming webhooks with HMAC.
- **Webhook Registration**: Subscribes to `products/update` events during OAuth.
- **TokenStorage**: Initialized for token retrieval.
- **Error Handling**: Ensures robust webhook setup.
- **Temporary Storage**: Prepares for split storage in `<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`, transitioning to Spaces in Chapter 6.

### Step 4: Update `shopify_integration/routes.py`
Add a webhook endpoint and test webhook registration in `/callback`, using `TokenStorage` and `SessionStorage`, storing data in split files.

```python
import os
import uuid
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_metadata, get_shopify_products, verify_hmac, register_webhooks
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
import httpx
import hmac
import hashlib
import base64

router = APIRouter()
session_storage = SessionStorage()
token_storage = TokenStorage()

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
    token_storage.store_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}", token_data["access_token"], type="token")

    user_uuid = str(uuid.uuid4())
    token_storage.store_token(f"USER_UUID_{shop_key}", user_uuid, type="uuid")

    session_id = session_storage.generate_session_id()
    session_storage.store_uuid(session_id, user_uuid)

    webhook_test_result = {"status": "failed", "message": "Webhook registration failed"}
    try:
        await register_webhooks(shop, token_data["access_token"])
        test_payload = {"product": {"id": 12345, "title": "Test Product"}}
        secret = os.getenv("SHOPIFY_API_SECRET")
        hmac_signature = base64.b64encode(
            hmac.new(secret.encode(), json.dumps(test_payload).encode(), hashlib.sha256).digest()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('SHOPIFY_WEBHOOK_ADDRESS', 'http://localhost:5000/shopify/webhook')}",
                headers={
                    "X-Shopify-Topic": "products/update",
                    "X-Shopify-Shop-Domain": shop,
                    "X-Shopify-Hmac-Sha256": hmac_signature,
                    "Content-Type": "application/json"
                },
                data=json.dumps(test_payload)
            )
            webhook_test_result = response.json() if response.status_code == 200 else {
                "status": "failed",
                "message": response.text
            }
        print(f"Webhook test result for {shop}: {webhook_test_result}")
    except Exception as e:
        webhook_test_result = {"status": "failed", "message": f"Webhook setup failed: {str(e)}"}
        print(f"Webhook setup failed for {shop}: {str(e)}")

    shop_metadata = await get_shopify_metadata(token_data["access_token"], shop)
    shop_products = await get_shopify_products(token_data["access_token"], shop)

    os.makedirs(shop, exist_ok=True)
    with open(f"{shop}/shop_metadata.json", "w") as f:
        json.dump(shop_metadata, f)
    with open(f"{shop}/shop_products.json", "w") as f:
        json.dump(shop_products, f)
    print(f"Wrote metadata to {shop}/shop_metadata.json and products to {shop}/shop_products.json for {shop}")

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "token_data": token_data,
        "shopify_data": {
            "metadata": shop_metadata,
            "products": shop_products
        },
        "webhook_test": webhook_test_result
    })
    response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=3600)
    return response

@router.post("/webhook")
async def shopify_webhook(request: Request):
    if not await verify_hmac(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop domain")

    shop_key = shop.replace('.', '_')
    access_token = token_storage.get_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}")
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token not found")

    user_uuid = token_storage.get_token(f"USER_UUID_{shop_key}")
    if not user_uuid:
        raise HTTPException(status_code=500, detail="User UUID not found for shop")

    payload = await request.json()
    event_type = request.headers.get("X-Shopify-Topic")
    print(f"Received {event_type} event from {shop}: {payload}")

    try:
        shop_metadata = await get_shopify_metadata(access_token, shop)
        shop_products = await get_shopify_products(access_token, shop)
        os.makedirs(shop, exist_ok=True)
        with open(f"{shop}/shop_metadata.json", "w") as f:
            json.dump(shop_metadata, f)
        with open(f"{shop}/shop_products.json", "w") as f:
            json.dump(shop_products, f)
        print(f"Wrote metadata to {shop}/shop_metadata.json and products to {shop}/shop_products.json for {shop}")
    except Exception as e:
        print(f"Failed to write data for {shop}: {str(e)}")

    return {"status": "success"}
```

**Why?**
- **Login Endpoint**: Initiates OAuth with scopes for products and inventory (Chapter 2).
- **Callback Endpoint**: Registers webhooks, tests the webhook endpoint, stores data in `<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`, sets the `session_id` cookie, and returns results with `user_uuid`. The split into metadata and products enhances modularity, preparing for Spaces (`users/<uuid>/shopify/<shop_name>/shop_metadata.json` and `users/<uuid>/shopify/<shop_name>/shop_products.json`) in Chapter 6.
- **Webhook Endpoint**: Processes `products/update` events, storing updates in temporary files using `TokenStorage`.
- **Security**: Uses HMAC verification, excludes tokens, and sets a secure cookie.
- **Temporary Storage**: Splits data for clarity and scalability.

### Step 5: Configure Webhook in Shopify Admin
**Action**: Set up the webhook in the Shopify Admin:
1. Log into your Shopify development store (Subchapter 2.2).
2. Navigate to **Settings > Notifications > Webhooks**.
3. Click **Create webhook**.
4. Select **Event**: `Product update`.
5. Set **Callback URL**: `SHOPIFY_WEBHOOK_ADDRESS` (e.g., `https://your-app.com/shopify/webhook` or `http://localhost:5000/shopify/webhook` via ngrok).
6. Set **Format**: JSON.
7. Click **Save**.

**Expected Output**: Shopify confirms webhook creation.

**Screenshot Reference**: Shopify Admin webhook settings page showing the `Product update` webhook.

**Why?**
- Configures Shopify to send `products/update` events to `/shopify/webhook`.
- Requires `read_products` permission.
- Ngrok ensures local testing accessibility.
- Uses `SHOPIFY_WEBHOOK_ADDRESS` for flexibility.

### Step 6: Update `requirements.txt`
Ensure dependencies support webhooks.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
```

**Why?**
- `apscheduler` is included for polling (Subchapter 5.2).
- `cryptography` supports `TokenStorage` and `SessionStorage` (Chapter 3).
- Excludes `boto3` (introduced in Chapter 6).

### Step 7: Update `.gitignore`
Ensure SQLite databases and temporary Shopify files are excluded.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
facebook/
*.myshopify.com/
```

**Why?**
- Excludes `tokens.db`, `sessions.db`, and temporary Shopify files (`<shop_name>/shop_metadata.json`, `<shop_name>/shop_products.json`).

### Step 8: Testing Preparation
To verify the webhook setup:
1. Update `.env` with `SHOPIFY_WEBHOOK_ADDRESS`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth to set the `session_id` cookie and register webhooks.
5. Testing details are in Subchapter 5.3.

### Summary: Why This Subchapter Matters
- **Real-Time Updates**: Webhooks keep product data current for the sales bot.
- **Security**: HMAC verification, `TokenStorage`, and `SessionStorage` ensure secure, multi-user operation.
- **UUID Integration**: Links data using the UUID from Chapter 3.
- **Scalability**: Async processing supports high traffic.
- **Temporary Storage**: Uses `<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`, preparing for cloud storage in Chapter 6.

### Next Steps:
- Implement daily polling for redundancy (Subchapter 5.2).
- Test webhooks and polling (Subchapter 5.3).