# Chapter 6: DigitalOcean Integration
## Subchapter 6.2: Shopify Data Sync with DigitalOcean Spaces

### Introduction
This subchapter transitions the temporary file storage (`<shop_name>/shopify_data.json`) from Chapter 5 to DigitalOcean Spaces for persistent, scalable storage of Shopify shop and product data. We update the webhook and polling mechanisms to upload non-sensitive data to Spaces (`users/<uuid>/shopify/<shop_name>/shopify_data.json`) using the UUID from `TokenStorage` (Chapter 3). The implementation uses `boto3` for S3-compatible storage, ensuring secure, production-ready data management with `TokenStorage` and `SessionStorage`.

### Prerequisites
- Completed Chapters 1–5 and Subchapter 6.1.
- FastAPI application running on a DigitalOcean Droplet or locally.
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- DigitalOcean Spaces bucket and credentials configured (Subchapter 6.3).
- Environment variables for Spaces and OAuth set in `.env`.

---

### Step 1: Why DigitalOcean Spaces for Shopify?
Spaces provides:
- Scalable storage for shop, product, discount, and collection data.
- Persistent storage for multiple users, organized by UUID.
- Integration with webhook and polling systems (Chapter 5).
- Preparation for backups in Chapter 7.

### Step 2: Update Project Structure
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
- `shopify_integration/` updates webhook and polling to use Spaces.
- `shared/tokens.py` and `shared/sessions.py` provide persistent storage.

### Step 3: Update `shopify_integration/utils.py`
Update polling to upload data to Spaces using `TokenStorage`.

```python
import os
import httpx
import json
from fastapi import HTTPException, Request
import hmac
import hashlib
import base64
import asyncio
import boto3
from botocore.exceptions import ClientError
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

def upload_to_spaces(data: dict, object_key: str):
    session = boto3.session.Session()
    client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION"),
        endpoint_url=os.getenv("SPACES_ENDPOINT"),
        aws_access_key_id=os.getenv("SPACES_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET")
    )
    try:
        client.put_object(
            Bucket=os.getenv("SPACES_BUCKET"),
            Key=object_key,
            Body=json.dumps(data),
            ContentType="application/json",
            ACL="private"
        )
        print(f"Uploaded data to Spaces: {object_key}")
    except ClientError as e:
        print(f"Failed to upload to Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")

async def poll_shopify_data(access_token: str, shop: str):
    try:
        shopify_data = await get_shopify_data(access_token, shop)
        shop_key = shop.replace('.', '_')
        user_uuid = token_storage.get_token(f"USER_UUID_{shop_key}")
        if not user_uuid:
            return {"status": "error", "message": f"User UUID not found for shop {shop}"}
        upload_to_spaces(shopify_data, f"users/{user_uuid}/shopify/{shop}/shopify_data.json")
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
- **OAuth Functions**: Reuses token exchange and data fetching from Chapter 5.
- **Webhook Functions**: Reuses verification and registration from Subchapter 5.1.
- **Spaces Upload**: `upload_to_spaces` stores data in `users/<uuid>/shopify/<shop_name>/shopify_data.json`.
- **Polling**: Updates `poll_shopify_data` to use Spaces with `TokenStorage`.

### Step 4: Update `shopify_integration/routes.py`
Update webhook and OAuth callback to use Spaces for storage.

```python
import os
import uuid
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, verify_hmac, register_webhooks, poll_shopify_data, upload_to_spaces
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
    upload_to_spaces(shopify_data, f"users/{user_uuid}/shopify/{shop}/shopify_data.json")

    polling_test_result = await poll_shopify_data(token_data["access_token"], shop)
    print(f"Polling test result for {shop}: {polling_test_result}")

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
        upload_to_spaces(shopify_data, f"users/{user_uuid}/shopify/{shop}/shopify_data.json")
    except Exception as e:
        print(f"Failed to upload data for {shop}: {str(e)}")

    return {"status": "success"}
```

**Why?**
- **Login Endpoint**: Initiates OAuth with scopes for products and inventory.
- **Callback Endpoint**: Uploads data to Spaces, tests webhook and polling, and returns results.
- **Webhook Endpoint**: Processes `products/update` events, uploading to Spaces with `TokenStorage`.
- **Security**: Uses HMAC, excludes tokens, and sets a secure cookie.

### Step 5: Update `requirements.txt`
Ensure `boto3` is included.

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
- `boto3` enables Spaces uploads.
- Other dependencies support OAuth, webhooks, and polling.

### Step 6: Update `.gitignore`
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

### Step 7: Testing Preparation
To verify Spaces integration:
1. Update `.env` with Spaces credentials (Subchapter 6.3).
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Complete Shopify OAuth to set the `session_id` cookie.
5. Run the Shopify OAuth flow to test Spaces uploads.
6. Testing details are in Subchapter 6.4.

### Summary: Why This Subchapter Matters
- **Persistent Storage**: Transitions Shopify data to Spaces for scalability.
- **UUID Integration**: Organizes data by UUID for multi-platform linking.
- **Security**: Uses `TokenStorage` and encrypted storage.
- **Scalability**: Supports production with async processing.

### Next Steps:
- Set up Spaces bucket (Subchapter 6.3).
- Test Spaces integration (Subchapter 6.4).