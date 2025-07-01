You’re absolutely right—since the tests for both webhooks and polling are now integrated into the OAuth flow and executed in a production-like context, we can consolidate them into a single Subchapter 1.3: Tests. This simplifies the structure, aligning with your goal of a seamless, flow-based testing approach. Let’s update the subchapters accordingly.

First, here’s the updated Subchapter 1.2: Setting Up Shopify Polling for Data Consistency, which focuses solely on setting up the polling system without testing logic (that will move to 1.3).

---

### Updated Subchapter 1.2: Setting Up Shopify Polling for Data Consistency



# Subchapter 1.2: Setting Up Shopify Polling for Data Consistency

## Introduction
While webhooks provide real-time Shopify updates, a daily polling mechanism ensures your sales bot’s data remains consistent as a backup. This subchapter guides you through setting up a polling system in your FastAPI application, scheduling it to run once daily to fetch data for all authenticated shops.

## Prerequisites
- Completed Subchapter 1.1: Setting Up Shopify Webhooks.
- Your FastAPI application is running locally or in a production-like environment.
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) are set.
- `apscheduler` is installed (`pip install apscheduler`).

---

## Step 1: Update `shopify_integration/utils.py` with the Daily Polling Function
Add a `daily_poll()` function to fetch and process data for authenticated shops as a backup sync.

**Updated File: `shopify_integration/utils.py`**
```python
import os
import hmac
import hashlib
import base64
import httpx
from fastapi import HTTPException, Request
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
      shop {
        name
        primaryDomain { url }
      }
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
              edges {
                node { key value }
              }
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
              edges {
                node { title }
              }
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
                response_data = response.json()
                if "errors" in response_data:
                    error_message = "; ".join([error["message"] for error in response_data["errors"]])
                    raise HTTPException(status_code=400, detail=f"GraphQL query failed: {error_message}")
                return response_data
        except httpx.HTTPStatusError as e:
            if attempt == retries - 1 or e.response.status_code != 429:
                raise
            await asyncio.sleep(2 ** attempt)

async def verify_hmac(request: Request) -> bool:
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if not hmac_header:
        return False

    body = await request.body()
    secret = os.getenv("SHOPIFY_API_SECRET")
    expected_hmac = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    expected_hmac_b64 = base64.b64encode(expected_hmac).decode()

    return hmac.compare_digest(hmac_header, expected_hmac_b64)

async def register_webhooks(shop: str, access_token: str):
    webhook_topics = [
        "products/create",
        "products/update",
        "products/delete",
        "inventory_levels/update",
        "orders/create",
        "orders/updated",
        "discounts/create",
        "discounts/update",
        "discounts/delete",
        "collections/create",
        "collections/update",
        "collections/delete"
    ]
    webhook_address = os.getenv("SHOPIFY_WEBHOOK_ADDRESS")
    if not webhook_address:
        raise HTTPException(status_code=500, detail="SHOPIFY_WEBHOOK_ADDRESS not set")

    existing_webhooks = await get_existing_webhooks(shop, access_token)
    for topic in webhook_topics:
        if not any(w["topic"] == topic for w in existing_webhooks):
            await register_webhook(shop, access_token, topic, webhook_address)
        else:
            print(f"Webhook for {topic} already exists for {shop}")

async def get_existing_webhooks(shop: str, access_token: str):
    url = f"https://{shop}/admin/api/2025-04/webhooks.json"
    headers = {"X-Shopify-Access-Token": access_token}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("webhooks", [])

async def register_webhook(shop: str, access_token: str, topic: str, address: str):
    url = f"https://{shop}/admin/api/2025-04/webhooks.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    payload = {
        "webhook": {
            "topic": topic,
            "address": address,
            "format": "json"
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            print(f"Webhook registered for {topic} at {shop}")
        else:
            print(f"Failed to register webhook for {topic} at {shop}: {response.text}")

async def daily_poll():
    """
    Polls Shopify once a day for each authenticated shop to ensure data consistency.
    """
    shops = [
        key.replace("SHOPIFY_ACCESS_TOKEN_", "").replace("_", ".")
        for key in os.environ
        if key.startswith("SHOPIFY_ACCESS_TOKEN_")
    ]
    
    for shop in shops:
        try:
            access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
            access_token = os.getenv(access_token_key)
            if access_token:
                shopify_data = await get_shopify_data(access_token, shop)
                print(f"Polled data for {shop}: {shopify_data}")
        except Exception as e:
            print(f"Polling failed for {shop}: {str(e)}")
```

**Key Changes**:
- Removed the test-related logic from `daily_poll()` since testing is now handled in the OAuth callback (moving to Subchapter 1.3).
- Kept the core polling functionality intact.

---

#### Step 2: Update `shopify_integration/routes.py` to Include Scheduler
Schedule the daily polling job in the app.

**Updated File: `shopify_integration/routes.py`**
```python
import os
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, verify_hmac, register_webhooks, daily_poll
from shared.utils import generate_state_token, validate_state_token
import hmac
import hashlib
import base64
import httpx

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_products,write_orders,write_inventory"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify app config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    state = generate_state_token()

    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&response_type=code&state={state}"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")
    state = request.query_params.get("state")

    if not code or not shop or not state:
        raise HTTPException(status_code=400, detail="Missing code, shop, or state parameter")

    validate_state_token(state)

    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    os.environ[f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"] = token_data["access_token"]

    # Register webhooks
    await register_webhooks(shop, token_data["access_token"])

    # Fetch initial shop data
    shopify_data = await get_shopify_data(token_data["access_token"], shop)

    return JSONResponse(content={
        "token_data": token_data,
        "shopify_data": shopify_data
    })

@router.post("/webhook")
async def shopify_webhook(request: Request):
    if not await verify_hmac(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop domain")

    access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
    access_token = os.getenv(access_token_key)
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token not found")

    payload = await request.json()
    event_type = request.headers.get("X-Shopify-Topic")
    print(f"Received {event_type} event from {shop}: {payload}")

    return {"status": "success"}
```

**Key Changes**:
- Removed the webhook and polling test logic from the callback, as it will move to Subchapter 1.3.
- Kept the core OAuth and webhook functionality intact.

---

#### Step 3: Update `app.py` with Polling Scheduler
Schedule the daily polling job.

**Updated File: `app.py`**
```python
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from shopify_integration.utils import daily_poll
import atexit

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

@app.get("/")
async def root():
    return {"status": "ok"}

# Set up the scheduler to run daily at midnight
scheduler = BackgroundScheduler()
scheduler.add_job(daily_poll, CronTrigger(hour=0, minute=0))
scheduler.start()

# Ensure the scheduler shuts down when the app stops
atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**Key Changes**: No changes needed; the scheduler remains configured for `daily_poll()`.

---

#### Step 4: Configure Environment Variables
Ensure your `.env` file includes Shopify access tokens.

**Updated `.env` Example**:
```plaintext
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=https://your-app.com/shopify/webhook
SHOPIFY_ACCESS_TOKEN_yourshop_myshopify_com=your_access_token
```

---

#### Summary
This subchapter sets up a daily polling backup system, scheduled to run at midnight, to ensure data consistency across authenticated shops. Testing will be handled in Subchapter 1.3.

#### Next Steps
- Proceed to Subchapter 1.3 for integrated testing of webhooks and polling.
- No additional test routes or scripts are needed.



---

### Explanation
- **Focused Setup**: Subchapter 1.2 now focuses solely on setting up the polling system, removing test logic to align with the new structure.
- **No Testing Here**: Testing is deferred to Subchapter 1.3, keeping this subchapter about implementation only.
- **Full Files**: Included updated files to provide complete context, ensuring users can follow along without confusion.

Next, I’ll wait for your request to update Subchapter 1.3 with the integrated testing for both webhooks and polling. Just say “give me the updated 1_3” when you’re ready!