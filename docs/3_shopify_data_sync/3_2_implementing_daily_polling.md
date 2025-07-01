Below is the complete Subchapter 3.2, which focuses on implementing daily polling as a backup to the primary webhook system in your FastAPI application. This subchapter ensures your sales bot’s data stays synchronized with Shopify even if webhooks fail, without including any DigitalOcean-specific code (as requested). Since we’re updating `app.py` and `shopify_integration/utils.py`, I’ve included the full updated files to avoid confusion, based on the provided starting directory structure and files.

---

### Subchapter 3.2: Implementing Daily Polling for Data Consistency

#### Introduction
While webhooks provide real-time updates from Shopify, it’s prudent to have a backup mechanism to ensure your sales bot’s data remains consistent, even if webhooks fail (e.g., due to network issues or missed events). In this subchapter, we’ll implement a daily polling system that runs once a day to fetch and sync data for all authenticated Shopify shops. This polling acts as a secondary check to guarantee data accuracy, complementing the webhook system set up in Subchapter 3.1.

#### Prerequisites
- Completed Subchapter 3.1: Setting Up Shopify Webhooks.
- APScheduler installed (`pip install apscheduler`).
- Shopify access tokens stored in environment variables (e.g., `SHOPIFY_ACCESS_TOKEN_yourshop_myshopify_com`).

---

#### Step 1: Update `shopify_integration/utils.py` with the Daily Polling Function
We’ll add an asynchronous `daily_poll()` function to `shopify_integration/utils.py` that:
1. Retrieves all authenticated Shopify shops from environment variables.
2. Fetches the latest data for each shop using the Shopify API.
3. Preprocesses the data (if needed).
4. Logs the action (for now, as a placeholder).

Here’s the updated `shopify_integration/utils.py`:

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
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

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
    webhook_address = os.getenv("WEBHOOK_ADDRESS")
    if not webhook_address:
        raise HTTPException(status_code=500, detail="WEBHOOK_ADDRESS not set")

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
    Runs as a backup to the primary webhook system.
    """
    # Dynamically get all shops from environment variables
    shops = [
        key.replace("SHOPIFY_ACCESS_TOKEN_", "").replace("_", ".")
        for key in os.environ
        if key.startswith("SHOPIFY_ACCESS_TOKEN_")
    ]
    
    for shop in shops:
        try:
            # Get the access token for the shop
            access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
            access_token = os.getenv(access_token_key)
            if access_token:
                # Fetch data from Shopify API
                shopify_data = await get_shopify_data(access_token, shop)
                # Preprocess the data (if needed)
                preprocessed_data = preprocess_shopify_data(shopify_data)
                # For now, just log the data; later, this can be replaced with storage logic
                print(f"Polled and processed data for {shop}: {preprocessed_data}")
        except Exception as e:
            print(f"Polling failed for {shop}: {str(e)}")

def preprocess_shopify_data(shopify_data):
    # Placeholder preprocessing function; enhance as needed
    return shopify_data
```

**Explanation**:  
- Added `daily_poll()` to fetch data for all shops dynamically.  
- Uses existing `get_shopify_data()` and `preprocess_shopify_data()` functions.  
- Errors are caught per shop to ensure polling continues for others.

---

#### Step 2: Schedule the Polling in `app.py`
We’ll use `apscheduler` to schedule `daily_poll()` to run daily at midnight. Here’s the updated `app.py`:

```python
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
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

**Explanation**:  
- Added `BackgroundScheduler` to run `daily_poll()` at midnight.  
- Used `atexit` to ensure clean shutdown.  
- No changes to existing routes or middleware.

---

#### Step 3: Configure Environment Variables
Ensure your `.env` file includes Shopify access tokens, stored during the OAuth flow.

**Example `.env`**:
```plaintext
# Shopify credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=https://your-app.com/shopify/webhook
SHOPIFY_ACCESS_TOKEN_yourshop_myshopify_com=your_access_token
```

#### Summary
You’ve added a daily polling mechanism to your FastAPI app, ensuring data consistency as a backup to webhooks. The system fetches and logs data for all authenticated shops once a day, with room to extend functionality later.

#### Next Steps
- Configure webhooks via Shopify admin UI (Subchapter 3.3).  
- Test webhook and polling integration (Subchapter 3.4).

---