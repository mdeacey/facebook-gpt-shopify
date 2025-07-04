# Chapter 5: Shopify Data Sync
## Subchapter 5.2: Implementing Daily Polling for Redundancy

### Introduction
While Shopify webhooks (Subchapter 5.1) provide real-time product updates, they can miss events due to network issues or downtime. This subchapter implements a daily polling mechanism to fetch shop and product data periodically, ensuring the GPT Messenger sales bot’s data remains current. Polling uses the SQLite-based `TokenStorage` (Chapter 3) for token and UUID retrieval and stores data temporarily in `<shop_name>/shopify_data.json`, preparing for cloud storage in Chapter 6. We integrate polling into the OAuth flow for testing and schedule it daily using APScheduler, maintaining non-sensitive data for secure, production-ready operation.

### Prerequisites
- Completed Chapters 1–4 and Subchapter 5.1.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) and `STATE_TOKEN_SECRET` set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).

---

### Step 1: Why Daily Polling?
Polling complements webhooks by:
- Fetching shop, product, discount, and collection data daily to catch missed events.
- Using `TokenStorage` for consistent token/UUID retrieval.
- Ensuring data availability for the sales bot (e.g., product titles, inventory).
- Supporting multiple users via SQLite-based storage.

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
- `shared/sessions.py` and `shared/tokens.py` support persistent storage.
- Excludes Spaces integration (Chapter 6).

### Step 3: Update `app.py`
Add APScheduler to schedule daily polling for Shopify shops.

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
    trigger=CronTrigger(hour=0, minute=0),
    id="facebook_daily_poll",
    replace_existing=True
)
scheduler.add_job(
    shopify_daily_poll,
    trigger=CronTrigger(hour=0, minute=0),
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
- **Scheduler**: Runs `shopify_daily_poll` daily at midnight, alongside `facebook_daily_poll`.
- **Shutdown Hook**: Ensures clean scheduler shutdown.
- **Environment Validation**: Includes webhook variables.
- **Modular Routers**: Supports both OAuth flows.

### Step 4: Update `shopify_integration/utils.py`
Add a polling function using `TokenStorage`, storing data temporarily.

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

async def poll_shopify_data(access_token: str, shop: str):
    try:
        shopify_data = await get_shopify_data(access_token, shop)
        shop_key = shop.replace('.', '_')
        user_uuid = token_storage.get_token(f"USER_UUID_{shop_key}")
        if not user_uuid:
            return {"status": "error", "message": f"User UUID not found for shop {shop}"}

        os.makedirs(shop, exist_ok=True)
        with open(f"{shop}/shopify_data.json", "w") as f:
            json.dump(shopify_data, f)
        print(f"Wrote data to {shop}/shopify_data.json for {shop}")
        return {"status": "success"}
    except Exception as e:
        print(f"Failed to poll data for {shop}: {str(e)}")
        return {"status": "error", "message": str(e)}

async def daily_poll():
    shops = [
        key.replace("SHOPIFY_ACCESS_TOKEN_", "").replace("_", ".")
        for key in token_storage.get_all_tokens_by_type("token")
        if key.startswith("SHOPIFY_ACCESS_TOKEN_")
    ]

    for shop in shops:
        try:
            shop_key = shop.replace('.', '_')
            access_token = token_storage.get_token(f"SHOPIFY_ACCESS_TOKEN_{shop_key}")
            if access_token:
                result = await poll_shopify_data(access_token, shop)
                if result["status"] == "success":
                    print(f"Polled data for shop {shop}: Success")
                else:
                    print(f"Polling failed for shop {shop}: {result['message']}")
        except Exception as e:
            print(f"Daily poll failed for shop {shop}: {str(e)}")
```

**Why?**
- **Polling Function**: `poll_shopify_data` fetches shop data using `TokenStorage`, storing in temporary files.
- **Daily Poll**: `daily_poll` iterates over shop tokens in `tokens.db`, calling `poll_shopify_data`.
- **Error Handling**: Returns status and error messages.
- **Temporary Storage**: Prepares for cloud storage in Chapter 6.

### Step 5: Update `shopify_integration/routes.py`
Integrate polling into the OAuth flow for immediate testing.

```python
import os
import uuid
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, verify_hmac, register_webhooks, poll_shopify_data
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

    shopify_data = await get_shopify_data(token_data["access_token"], shop)

    polling_test_result = await poll_shopify_data(token_data["access_token"], shop)
    print(f"Polling test result for {shop}: {polling_test_result}")

    os.makedirs(shop, exist_ok=True)
    with open(f"{shop}/shopify_data.json", "w") as f:
        json.dump(shopify_data, f)
    print(f"Wrote data to {shop}/shopify_data.json for {shop}")

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "token_data": token_data,
        "shopify_data": shopify_data,
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
        shopify_data = await get_shopify_data(access_token, shop)
        os.makedirs(shop, exist_ok=True)
        with open(f"{shop}/shopify_data.json", "w") as f:
            json.dump(shopify_data, f)
        print(f"Wrote data to {shop}/shopify_data.json for {shop}")
    except Exception as e:
        print(f"Failed to write data for {shop}: {str(e)}")

    return {"status": "success"}
```

**Why?**
- **Login Endpoint**: Initiates OAuth with scopes for products and inventory.
- **Callback Endpoint**: Tests polling and webhooks, stores data in `<shop_name>/shopify_data.json`, sets the `session_id` cookie, and returns results with `user_uuid`.
- **Webhook Endpoint**: Processes `products/update` events, storing updates with `TokenStorage`.
- **Security**: Uses HMAC, excludes tokens, and sets a secure cookie.

### Step 6: Update `requirements.txt`
Ensure APScheduler is included.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
```

**Why?**
- `apscheduler` enables daily polling.
- `cryptography` supports `TokenStorage` and `SessionStorage`.

### Step 7: Update `.gitignore`
Ensure SQLite databases are excluded.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
```

**Why?**
- Excludes `tokens.db` and `sessions.db`.

### Step 8: Testing Preparation
To verify polling:
1. Update `.env` with `SHOPIFY_WEBHOOK_ADDRESS`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth to set the `session_id` cookie and test polling.
5. Testing details are in Subchapter 5.3.

### Summary: Why This Subchapter Matters
- **Data Redundancy**: Polling ensures data consistency alongside webhooks.
- **UUID Integration**: Uses `TokenStorage` for multi-platform linking.
- **Scalability**: Async polling and scheduling support production environments.
- **Temporary Storage**: Prepares for cloud storage in Chapter 6.

### Next Steps:
- Test webhooks and polling (Subchapter 5.3).
- Proceed to Chapter 6 for cloud storage integration.