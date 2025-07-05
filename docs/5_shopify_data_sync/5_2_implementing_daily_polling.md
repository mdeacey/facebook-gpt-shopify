# Chapter 5: Shopify Data Sync
## Subchapter 5.2: Implementing Daily Polling for Redundancy

### Introduction
While Shopify webhooks (Subchapter 5.1) provide real-time product updates, they can miss events due to network issues or downtime. This subchapter implements a daily polling mechanism to fetch shop and product data periodically, ensuring the GPT Messenger sales bot’s data remains current. Polling uses the SQLite-based `TokenStorage` (Chapter 3) for token and UUID retrieval and stores data temporarily in `<shop_name>/shop_metadata.json` for shop details and `<shop_name>/shop_products.json` for products, discounts, and collections, preparing for cloud storage in Chapter 6 (`users/<uuid>/shopify/<shop_name>/shop_metadata.json` and `users/<uuid>/shopify/<shop_name>/shop_products.json`). We integrate polling into the OAuth flow for testing and schedule it daily using APScheduler, maintaining non-sensitive data for secure, production-ready operation.

### Prerequisites
- Completed Chapters 1–4 and Subchapter 5.1.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) and `STATE_TOKEN_SECRET` set in `.env` (Chapter 2, Subchapter 5.1).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Permissions `read_product_listings`, `read_inventory`, `read_discounts`, `read_locations`, `read_products` configured in Shopify Admin (Chapter 2).

---

### Step 1: Why Daily Polling?
Polling complements webhooks by:
- Fetching shop metadata (e.g., `name`, `primaryDomain`) and product data (products, discounts, collections) daily to catch missed events.
- Using `TokenStorage` for consistent token/UUID retrieval (Chapter 3).
- Ensuring data availability for the sales bot (e.g., product titles, inventory levels).
- Supporting multiple users via SQLite-based storage and temporary files, split into `shop_metadata.json` and `shop_products.json` for modularity.

### Step 2: Update Project Structure
The project structure remains as defined in Subchapter 5.1:
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
- `shopify_integration/utils.py` handles polling logic using `TokenStorage`.
- `app.py` integrates APScheduler for scheduling.
- `shared/sessions.py` and `shared/tokens.py` support persistent storage (Chapter 3).
- No dependencies from future chapters (e.g., `digitalocean_integration` or `boto3`) are included.
- Temporary storage uses `<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`, aligning with Chapter 6’s structure.

### Step 3: Update `app.py`
Add APScheduler to schedule daily polling for Shopify shops, alongside Facebook polling (Subchapter 4.3).

```python
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from facebook_integration.utils import daily_poll as facebook_daily_poll
from shopify_integration.utils import daily_poll as shopify_daily_poll
import os
import atexit

load_dotenv()

required_env_vars = [
    "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI",
    "FACEBOOK_WEBHOOK_ADDRESS", "FACEBOOK_VERIFY_TOKEN",
    "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_REDIRECT_URI",
    "SHOPIFY_WEBHOOK_ADDRESS", "STATE_TOKEN_SECRET"
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

scheduler = BackgroundScheduler()
scheduler.add_job(
    facebook_daily_poll,
    trigger=CronTrigger(hour=0, minute=0),  # Run daily at midnight
    id="facebook_daily_poll",
    replace_existing=True
)
scheduler.add_job(
    shopify_daily_poll,
    trigger=CronTrigger(hour=0, minute=30),  # Run 30 minutes after Facebook
    id="shopify_daily_poll",
    replace_existing=True
)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**Why?**
- **Scheduler**: Schedules `shopify_daily_poll` at 00:30 to avoid conflicts with `facebook_daily_poll`.
- **Environment Validation**: Includes Shopify webhook variables from Subchapter 5.1.
- **Shutdown Hook**: Ensures clean scheduler shutdown.
- **Excludes Future Dependencies**: No references to Spaces or `boto3` (Chapter 6).

### Step 4: Update `shopify_integration/utils.py`
Add a `daily_poll` function to fetch shop metadata and product data, storing them in split files.

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
            os.makedirs(shop, exist_ok=True)
            with open(f"{shop}/shop_metadata.json", "w") as f:
                json.dump(shop_metadata, f)
            with open(f"{shop}/shop_products.json", "w") as f:
                json.dump(shop_products, f)
            print(f"Polled and wrote data to {shop}/shop_metadata.json and {shop}/shop_products.json for {shop}")
        except Exception as e:
            print(f"Daily poll failed for shop {shop}: {str(e)}")
```

**Why?**
- **Polling Function**: `daily_poll` fetches metadata and products, storing them in `<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`, using `TokenStorage` for token/UUID retrieval.
- **Split Data**: Separates shop metadata and product data for modularity, aligning with Subchapter 5.1 and Chapter 6’s cloud storage structure.
- **Error Handling**: Logs failures for debugging.
- **Excludes Future Dependencies**: No Spaces or `boto3` references (Chapter 6).

### Step 5: Update `shopify_integration/routes.py`
Integrate polling tests into the OAuth flow, testing both metadata and product polling.

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

    # Test polling
    polling_test_result = {"status": "failed", "message": "Polling test failed"}
    try:
        shop_key = shop.replace('.', '_')
        token_storage.store_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}", token_data["access_token"], type="token")
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
- **Login Endpoint**: Reuses OAuth setup from Chapter 2.
- **Callback Endpoint**: Tests polling alongside webhooks, storing results in `polling_test_result`, and stores data in split files (`<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`).
- **Webhook Endpoint**: Unchanged from Subchapter 5.1, included for completeness.
- **Security**: Uses HMAC verification, excludes tokens, and sets secure cookies.
- **Temporary Storage**: Uses split files, preparing for Spaces in Chapter 6.

### Step 6: Update `requirements.txt`
Ensure dependencies support polling.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
```

**Why?**
- `apscheduler` supports polling (introduced in Subchapter 4.3, reused here).
- `cryptography` supports `TokenStorage` and `SessionStorage`.
- Excludes `boto3` (Chapter 6).

### Step 7: Update `.gitignore`
Ensure temporary Shopify files are excluded.

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
To verify polling:
1. Update `.env` with required variables (Subchapter 5.1).
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth to test polling.
5. Testing details are in Subchapter 5.3.

**Expected Output** (example logs during OAuth):
```
Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
Wrote metadata to acme-7cu19ngr.myshopify.com/shop_metadata.json and products to acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
Polling test result for acme-7cu19ngr.myshopify.com: Success
```

### Summary: Why This Subchapter Matters
- **Data Redundancy**: Polling ensures shop and product data are complete, complementing webhooks.
- **UUID Integration**: Uses `TokenStorage` for multi-platform linking.
- **Scalability**: Async polling and scheduling support production environments.
- **Temporary Storage**: Uses `<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`, preparing for cloud storage in Chapter 6.
- **Modularity**: Split files enhance data organization.

### Next Steps:
- Test webhooks and polling (Subchapter 5.3).
- Proceed to Chapter 6 for cloud storage integration.