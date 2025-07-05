# Chapter 6: DigitalOcean Integration
## Subchapter 6.2: Shopify Data Sync with DigitalOcean Spaces

### Introduction
This subchapter transitions the temporary file storage for Shopify data (`<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json` from Chapter 5) to DigitalOcean Spaces, using the UUID from Chapter 3 to organize data in `users/<uuid>/shopify/<shop_name>/shop_metadata.json` and `users/<uuid>/shopify/<shop_name>/shop_products.json`. The webhook and polling mechanisms (Subchapters 5.1–5.2) are updated to upload non-sensitive shop metadata (e.g., `name`, `primaryDomain`) and product data (products, discounts, collections) to Spaces using `boto3`, ensuring scalable, production-ready storage for the GPT Messenger sales bot.

### Prerequisites
- Completed Chapters 1–5 and Subchapter 6.1.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- DigitalOcean Spaces credentials (`SPACES_KEY`, `SPACES_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`) set in `.env` (Subchapter 6.1).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) and `STATE_TOKEN_SECRET` set in `.env` (Chapter 2, Subchapter 5.1).
- Permissions `read_product_listings`, `read_inventory`, `read_discounts`, `read_locations`, `read_products` configured in Shopify Admin (Chapter 2).

---

### Step 1: Verify Environment Variables
The `.env` file from Subchapter 6.1 includes Spaces credentials, along with Shopify credentials from Chapter 2 and Subchapter 5.1. Confirm they are set correctly:

**`.env.example`**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=http://localhost:5000/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=http://localhost:5000/shopify/webhook
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# Database paths for SQLite storage
TOKEN_DB_PATH=./data/tokens.db
SESSION_DB_PATH=./data/sessions.db
# DigitalOcean Spaces credentials
SPACES_KEY=your_spaces_key
SPACES_SECRET=your_spaces_secret
SPACES_REGION=nyc3
SPACES_BUCKET=your-bucket-name
```

**Notes**:
- Obtain `SPACES_KEY` and `SPACES_SECRET` from your DigitalOcean account (Spaces > API).
- Set `SPACES_REGION` (e.g., `nyc3`) and `SPACES_BUCKET` to your bucket name.
- **Production Note**: Use secure credentials and HTTPS for webhook addresses (`SHOPIFY_WEBHOOK_ADDRESS`).

**Why?**
- Ensures `boto3` can authenticate with Spaces for data uploads.
- Reuses existing Shopify and session-related environment variables for consistency.

### Step 2: Verify Project Structure
The project structure includes the `digitalocean_integration` directory from Subchapter 6.1:
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
├── digitalocean_integration/
│   ├── __init__.py
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
- `digitalocean_integration/utils.py` provides the `upload_to_spaces` function for Spaces uploads, reused from Subchapter 6.1.
- `shopify_integration/` contains webhook and polling logic, updated to use Spaces.
- `shared/sessions.py` and `shared/tokens.py` manage persistent storage (Chapter 3).

### Step 3: Update `shopify_integration/utils.py`
Update the polling and webhook functions to upload shop metadata and product data to Spaces instead of local files, using the new path structure.

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
from digitalocean_integration.utils import upload_to_spaces

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

async def daily_poll():
    shop_keys = [
        key.replace("SHOPIFY_ACCESS_TOKEN_", "")
        for key in token_storage.get_all_tokens_by_type("token")
        if key.startswith("SHOPIFY_ACCESS_TOKEN_")
    ]
    for shop_key in shop_keys:
        try:
            access_token = token_storage.get_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}")
            shop = shop_key.replace('_', '.')
            if not access_token:
                print(f"Access token not found for shop {shop}")
                continue
            user_uuid = token_storage.get_token(f"USER_UUID_{shop_key}")
            if not user_uuid:
                print(f"User UUID not found for shop {shop}")
                continue
            shop_metadata = await get_shopify_metadata(access_token, shop)
            shop_products = await get_shopify_products(access_token, shop)
            upload_to_spaces(shop_metadata, f"users/{user_uuid}/shopify/{shop}/shop_metadata.json")
            upload_to_spaces(shop_products, f"users/{user_uuid}/shopify/{shop}/shop_products.json")
            print(f"Uploaded data to users/{user_uuid}/shopify/{shop}/shop_metadata.json and users/{user_uuid}/shopify/{shop}/shop_products.json for {shop}")
        except Exception as e:
            print(f"Daily poll failed for shop {shop}: {str(e)}")
```

**Why?**
- **Polling Function**: `daily_poll` uploads shop metadata and product data to Spaces (`users/<uuid>/shopify/<shop_name>/shop_metadata.json` and `users/<uuid>/shopify/<shop_name>/shop_products.json`) instead of local files.
- **Split Data**: Maintains the split between metadata and products for modularity, consistent with Subchapter 5.1.
- **Error Handling**: Logs failures for debugging.
- **Spaces Integration**: Uses `upload_to_spaces` from Subchapter 6.1 for consistency.

### Step 4: Update `shopify_integration/routes.py`
Update the webhook and OAuth callback to use Spaces for storage, maintaining the split file structure.

```python
import os
import uuid
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_metadata, get_shopify_products, verify_hmac, register_webhooks, daily_poll
from shared.utils import generate_state_token, validate_state_token
from shared.sessions import SessionStorage
from shared.tokens import TokenStorage
from digitalocean_integration.utils import upload_to_spaces
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
    upload_to_spaces(shop_metadata, f"users/{user_uuid}/shopify/{shop}/shop_metadata.json")
    upload_to_spaces(shop_products, f"users/{user_uuid}/shopify/{shop}/shop_products.json")
    print(f"Uploaded data to users/{user_uuid}/shopify/{shop}/shop_metadata.json and users/{user_uuid}/shopify/{shop}/shop_products.json for {shop}")

    polling_test_result = {"status": "failed", "message": "Polling test failed"}
    try:
        await daily_poll()
        polling_test_result = {"status": "success"}
        print(f"Polling test result for {shop}: Success")
    except Exception as e:
        polling_test_result = {"status": "failed", "message": f"Polling test failed: {str(e)}"}
        print(f"Polling test failed for {shop}: {str(e)}")

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "token_data": token_data,
        "shopify_data": {
            "metadata": shop_metadata,
            "products": shop_products
        },
        "webhook_test": webhook_test_result,
        "polling_test": polling_test_result
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
        upload_to_spaces(shop_metadata, f"users/{user_uuid}/shopify/{shop}/shop_metadata.json")
        upload_to_spaces(shop_products, f"users/{user_uuid}/shopify/{shop}/shop_products.json")
        print(f"Uploaded data to users/{user_uuid}/shopify/{shop}/shop_metadata.json and users/{user_uuid}/shopify/{shop}/shop_products.json for {shop}")
    except Exception as e:
        print(f"Failed to upload data for {shop}: {str(e)}")

    return {"status": "success"}
```

**Why?**
- **Callback Endpoint**: Uploads shop metadata and product data to Spaces during OAuth, using the new path structure (`users/<uuid>/shopify/<shop_name>/...`).
- **Webhook Endpoint**: Uploads updated data to Spaces on `products/update` events, maintaining the split between `shop_metadata.json` and `shop_products.json`.
- **Security**: Uses `TokenStorage` for UUID and token retrieval, excludes sensitive data.
- **Split Data**: Preserves modularity of metadata and product data, consistent with Chapter 5.

### Step 5: Update `requirements.txt`
The `requirements.txt` from Subchapter 6.1 includes `boto3`:
```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
boto3
```

**Why?**
- `boto3` enables Spaces integration, reused from Subchapter 6.1.
- Retains dependencies from previous chapters.

### Step 6: Verify Spaces Configuration
**Action**: Ensure the DigitalOcean Spaces bucket is set up:
1. Log into your DigitalOcean account.
2. Navigate to **Spaces** and verify the bucket exists (name matches `SPACES_BUCKET`).
3. Ensure `SPACES_KEY` and `SPACES_SECRET` have read/write access to the bucket.

**Why?**
- Confirms Spaces is ready for uploads.
- Ensures secure access with correct credentials.

### Step 7: Testing Preparation
To verify Spaces integration for Shopify data:
1. Update `.env` with Spaces and Shopify credentials.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth to test webhook and polling uploads:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
5. Testing details are in Subchapter 6.4.

**Expected Output** (example logs):
```
Webhook registered for acme-7cu19ngr.myshopify.com: products/update
Uploaded data to users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json and users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
Polling test result for acme-7cu19ngr.myshopify.com: Success
```

### Summary: Why This Subchapter Matters
- **Scalable Storage**: Moves Shopify data to Spaces for production-ready storage.
- **UUID Organization**: Uses `users/<uuid>/shopify/<shop_name>/...` for multi-user support.
- **Modularity**: Maintains split between `shop_metadata.json` and `shop_products.json` for clarity and scalability.
- **Security**: Uses private ACL and secure token storage.
- **Consistency**: Aligns with webhook and polling mechanisms from Chapter 5.

### Next Steps:
- Test Spaces integration for both Facebook and Shopify data (Subchapter 6.4).
- Implement data backup and recovery (Chapter 7).