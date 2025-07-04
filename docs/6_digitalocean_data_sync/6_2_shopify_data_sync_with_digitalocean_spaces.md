# Chapter 6: DigitalOcean Integration
## Subchapter 6.2: Shopify Data Sync with DigitalOcean Spaces

### Introduction
This subchapter integrates DigitalOcean Spaces to store Shopify shop and product data for the GPT Messenger sales bot, replacing the temporary file storage (`<shop_name>/shopify_data.json`) from Chapter 5 with a UUID-based bucket structure (`users/<uuid>/shopify/shopify_data.json`). The webhook and polling systems (Subchapters 5.1 and 5.2) are updated to use Spaces, leveraging the UUID from the session-based mechanism (Chapter 3). This ensures secure, scalable storage for multiple users, maintaining non-sensitive data for the sales bot’s recommendations.

### Prerequisites
- Completed Chapters 1–5 and Subchapter 6.1.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- Shop access tokens (`SHOPIFY_ACCESS_TOKEN_<shop_key>`) and UUID mappings (`USER_UUID_<shop_key>`) stored in the environment.
- DigitalOcean Spaces credentials and bucket set up (Subchapter 6.3).
- `boto3` installed (`pip install boto3`).

---

### Step 1: Configure Environment Variables
Use the `.env` from Subchapter 6.1, which includes Spaces credentials.

**`.env.example`**:
```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=https://your-app.com/shopify/webhook
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# DigitalOcean Spaces credentials
SPACES_ACCESS_KEY=your_access_key
SPACES_SECRET_KEY=your_secret_key
SPACES_BUCKET=your_bucket_name
SPACES_REGION=nyc3
```

**Notes**:
- No additional variables needed beyond Subchapter 6.1.
- **Production Note**: Ensure secure credentials and HTTPS for webhook addresses.

**Why?**
- Enables storage of Shopify data in Spaces using the UUID-based structure.

### Step 2: Project Structure
The project structure remains as defined in Subchapter 6.1:
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
│   ├── session.py
│   └── utils.py
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `digitalocean_integration/utils.py` provides Spaces functions (Subchapter 6.1).
- `shopify_integration/` handles Shopify data sync.
- `shared/session.py` supports session-based UUID retrieval.

### Step 3: Update `shopify_integration/utils.py`
Update polling to use Spaces with the `users/` prefix instead of temporary file storage.

```python
import os
import httpx
import asyncio
import hashlib
import base64
import hmac
from fastapi import HTTPException, Request
import boto3
from digitalocean_integration.utils import has_data_changed, upload_to_spaces

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

async def poll_shopify_data(access_token: str, shop: str) -> dict:
    try:
        await get_shopify_data(access_token, shop)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def daily_poll():
    shops = [
        key.replace("SHOPIFY_ACCESS_TOKEN_", "").replace("_", ".")
        for key in os.environ
        if key.startswith("SHOPIFY_ACCESS_TOKEN_")
    ]
    
    for shop in shops:
        try:
            shop_key = shop.replace('.', '_')
            access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop_key}"
            access_token = os.getenv(access_token_key)
            user_uuid = os.getenv(f"USER_UUID_{shop_key}")
            if not user_uuid:
                print(f"User UUID not found for shop {shop}")
                continue
            if access_token:
                poll_result = await poll_shopify_data(access_token, shop)
                if poll_result["status"] == "success":
                    shopify_data = await get_shopify_data(access_token, shop)
                    session = boto3.session.Session()
                    s3_client = session.client(
                        "s3",
                        region_name=os.getenv("SPACES_REGION", "nyc3"),
                        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
                        aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
                        aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
                    )
                    spaces_key = f"users/{user_uuid}/shopify/shopify_data.json"
                    if has_data_changed(shopify_data, spaces_key, s3_client):
                        upload_to_spaces(shopify_data, spaces_key, s3_client)
                        print(f"Polled and uploaded data for {shop}: Success")
                    else:
                        print(f"Polled data for {shop}: No upload needed, data unchanged")
                else:
                    print(f"Polling failed for {shop}: {poll_result['message']}")
        except Exception as e:
            print(f"Daily poll failed for {shop}: {str(e)}")
```

**Why?**
- **OAuth and Webhook Functions**: Reuses functions from Chapter 5.
- **Polling Function**: Updates `poll_shopify_data` to use Spaces with `users/<uuid>/shopify/shopify_data.json`.
- **Daily Poll**: Iterates over shop access tokens, storing data in Spaces.
- **Error Handling**: Returns status and messages.

### Step 4: Update `shopify_integration/routes.py`
Update the OAuth flow, webhook, and polling to use Spaces with the `users/` prefix.

```python
import os
import json
import boto3
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, verify_hmac, register_webhooks, poll_shopify_data
from shared.utils import generate_state_token, validate_state_token
from shared.session import generate_session_id, store_uuid
from digitalocean_integration.utils import has_data_changed, upload_to_spaces
import hmac
import hashlib
import base64
import httpx

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_products,write_inventory"

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

    shop_key = shop.replace('.', '_')
    os.environ[f"SHOPIFY_ACCESS_TOKEN_{shop_key}"] = token_data["access_token"]

    user_uuid = str(uuid.uuid4())
    os.environ[f"USER_UUID_{shop_key}"] = user_uuid

    session_id = generate_session_id()
    store_uuid(session_id, user_uuid)

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
                f"http://localhost:5000/shopify/webhook",
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

    access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop_key}"
    access_token = os.getenv(access_token_key)
    polling_test_result = await poll_shopify_data(access_token, shop)
    print(f"Polling test result for {shop}: {polling_test_result}")

    upload_status_result = {"status": "failed", "message": "Tests failed"}
    if (
        webhook_test_result.get("status") == "success"
        and polling_test_result.get("status") == "success"
    ):
        try:
            session = boto3.session.Session()
            s3_client = session.client(
                "s3",
                region_name=os.getenv("SPACES_REGION", "nyc3"),
                endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
                aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
            )
            spaces_key = f"users/{user_uuid}/shopify/shopify_data.json"
            if has_data_changed(shopify_data, spaces_key, s3_client):
                upload_to_spaces(shopify_data, spaces_key, s3_client)
                print(f"Uploaded data to Spaces for {shop}")
            else:
                print(f"No upload needed for {shop}: Data unchanged")
            upload_status_result = {"status": "success"}
        except Exception as e:
            upload_status_result = {"status": "failed", "message": f"Spaces upload failed: {str(e)}"}
            print(f"Failed to upload to Spaces for {shop}: {str(e)}")

    response = JSONResponse(content={
        "user_uuid": user_uuid,
        "token_data": token_data,
        "shopify_data": shopify_data,
        "webhook_test": webhook_test_result,
        "polling_test": polling_test_result,
        "upload_status": upload_status_result
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
    access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop_key}"
    access_token = os.getenv(access_token_key)
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token not found")

    user_uuid = os.getenv(f"USER_UUID_{shop_key}")
    if not user_uuid:
        raise HTTPException(status_code=500, detail="User UUID not found for shop")

    payload = await request.json()
    event_type = request.headers.get("X-Shopify-Topic")
    print(f"Received {event_type} event from {shop}: {payload}")

    try:
        shopify_data = await get_shopify_data(access_token, shop)
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=os.getenv("SPACES_REGION", "nyc3"),
            endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
        )
        spaces_key = f"users/{user_uuid}/shopify/shopify_data.json"
        if has_data_changed(shopify_data, spaces_key, s3_client):
            upload_to_spaces(shopify_data, spaces_key, s3_client)
            print(f"Updated data in Spaces for {shop} via {event_type}")
        else:
            print(f"No update needed in Spaces for {shop} via {event_type}: Data unchanged")
    except Exception as e:
        print(f"Failed to update Spaces for {shop} via {event_type}: {str(e)}")

    return {"status": "success"}
```

**Why?**
- **Login Endpoint**: Uses the `session_id` cookie to retrieve the UUID (Chapter 3).
- **Callback Endpoint**: Tests polling and webhooks, uploads to Spaces with `users/` prefix, and returns results with `user_uuid`.
- **Webhook Endpoint**: Processes `products/update` events, storing updates in `users/<uuid>/shopify/shopify_data.json`.
- **Security**: Excludes tokens, uses HMAC, and sets a secure cookie.

### Step 5: Update `requirements.txt`
Use the same `requirements.txt` from Subchapter 6.1.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
apscheduler
boto3
```

**Why?**
- No additional dependencies needed.

### Step 6: Testing Preparation
To verify Spaces integration:
1. Use `.env` from Subchapter 6.1.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth to set the `session_id` cookie.
5. Run the Shopify OAuth flow to test Spaces uploads.
6. Testing details are in Subchapter 6.4.

### Summary: Why This Subchapter Matters
- **Cloud Storage**: Replaces temporary file storage with Spaces.
- **UUID Integration**: Organizes data in `users/<uuid>/shopify/shopify_data.json`.
- **Security**: Ensures non-sensitive data storage and session-based UUID retrieval.
- **Scalability**: Supports multiple users in production.

### Next Steps:
- Set up a Spaces bucket (Subchapter 6.3).
- Test Spaces integration (Subchapter 6.4).