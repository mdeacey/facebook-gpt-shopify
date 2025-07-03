### Chapter 3: DigitalOcean Integration

#### Subchapter 3.2: Shopify Data Synchronization with DigitalOcean Spaces

This subchapter integrates DigitalOcean Spaces into your FastAPI application to store and keep Shopify data updated for the GPT Messenger sales bot. We’ll configure environment variables, create utilities for checking data changes and uploading to Spaces, update the Shopify callback route to test webhook and polling functionality before uploading initial data post-OAuth (if changed), enhance webhook handling for real-time updates, and leverage daily polling to ensure data consistency. This builds on the Shopify integration from Subchapter 2.1 and assumes a Shopify development store, app credentials, and DigitalOcean Spaces setup (Subchapter 3.1). The focus is on code implementation, ensuring webhooks and polling work reliably before syncing shop details, products, discounts, and collections to Spaces, with uploads optimized to occur only when data differs.

---

##### Step 1: Why Synchronize Shopify Data with DigitalOcean Spaces?

The sales bot requires up-to-date Shopify data to generate accurate recommendations and promotions. Storing and updating this data in DigitalOcean Spaces:

- **Ensures Fresh Data**: Combines initial uploads, real-time webhook updates, and daily polling for consistency.
- **Scales Efficiently**: Uses cloud storage to handle data for multiple shops, offloading the app.
- **Optimizes Resources**: Uploads only when data changes, reducing API calls and costs.

We’ll configure environment variables, create utilities for checking data changes and uploading to Spaces, modify the Shopify callback to test webhooks and polling before uploading initial data, enhance the webhook endpoint for incremental updates, and update daily polling to sync data, ensuring uploads only occur after successful tests and when data differs. The existing `generate_state_token` and `validate_state_token` functions from `shared/utils.py` are used in the OAuth flow to secure the callback, so no additional state token logic is needed for Spaces operations.

---

##### Step 2: Project Structure

The current codebase includes `shopify_integration`, `facebook_oauth`, and `shared` modules. We’ll add a `digitalocean_integration` module for Spaces utilities:

```
.
├── facebook_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shopify_integration/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── digitalocean_integration/
│   ├── __init__.py
│   └── utils.py         # New file for Spaces utilities
├── shared/
│   ├── __init__.py
│   └── utils.py
├── .env
├── app.py
└── requirements.txt
```

- **`digitalocean_integration/utils.py`**: Handles data change checks and uploads to Spaces.
- **`shopify_integration/routes.py`**: Updated to test webhooks/polling before initial upload and enhance webhook processing.
- **`shopify_integration/utils.py`**: Updated for polling with Spaces integration.
- **`.env`**: Extended with Spaces credentials (Step 3).
- **`app.py`**: Already schedules daily polling via APScheduler.

This structure maintains the codebase’s modularity, keeping functionality grouped and reusable.

---

##### Step 3: Configure Environment Variables

**Action**: Add DigitalOcean Spaces credentials to `.env`.

**Why?**  
These variables authenticate Spaces operations, keeping sensitive data secure, as in the codebase’s approach. Configuring them first ensures they’re available for the Spaces utility functions.

**Instructions**:  
Update `.env` with (assuming `.env.example` is part of the codebase):

```plaintext
# Existing credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=http://localhost:5000/shopify/webhook
STATE_TOKEN_SECRET=replace_with_secure_token

# DigitalOcean Spaces credentials
SPACES_ACCESS_KEY=your_access_key
SPACES_SECRET_KEY=your_secret_key
SPACES_BUCKET=your_bucket_name
SPACES_REGION=nyc3
```

**Why?**  
- **New Variables**: Adds Spaces credentials, bucket, and region.
- **Consistency**: Extends the existing `.env` setup, ensuring centralized configuration.

---

##### Step 4: Create digitalocean_integration/utils.py

**Action**: Define functions to compute data hashes, check for data changes, and upload to Spaces.

**Why?**  
Separating change detection (`has_data_changed`) from uploading (`upload_to_spaces`) enhances modularity, making each function reusable and focused on a single responsibility. Keeping `compute_data_hash` in this module ensures encapsulation, as it’s currently only used by `has_data_changed` for Spaces operations. This aligns with the codebase’s modular design.

**Instructions**:  
Create `digitalocean_integration/utils.py` with:

```python
import os
import boto3
import json
import hashlib
from fastapi import HTTPException
from botocore.exceptions import ClientError

def compute_data_hash(data: dict) -> str:
    """Compute SHA256 hash of serialized JSON data."""
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()

def has_data_changed(data: dict, key: str, s3_client: boto3.client) -> bool:
    """Check if data differs from existing object in Spaces. Returns True if changed or new."""
    new_hash = compute_data_hash(data)
    try:
        response = s3_client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=key)
        existing_data = response["Body"].read().decode()
        existing_hash = hashlib.sha256(existing_data.encode()).hexdigest()
        return existing_hash != new_hash
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return True  # Object doesn’t exist, treat as changed
        raise HTTPException(status_code=500, detail=f"Failed to fetch existing data: {str(e)}")

def upload_to_spaces(data: dict, key: str, s3_client: boto3.client):
    """Upload data to DigitalOcean Spaces."""
    try:
        s3_client.put_object(
            Bucket=os.getenv("SPACES_BUCKET"),
            Key=key,
            Body=json.dumps(data, ensure_ascii=False),
            ContentType="application/json",
            ACL="private"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")
```

**Why?**  
- **Hashing**: `compute_data_hash` serializes JSON with sorted keys for consistent hashing, kept here as it’s only used by `has_data_changed`.
- **Change Check**: `has_data_changed` compares hashes, returning `True` if data differs or the object is new.
- **Upload**: `upload_to_spaces` handles the core upload, reusable for unconditional uploads.
- **Error Handling**: Handles “NoSuchKey” for initial uploads and raises exceptions for other failures, aligning with the codebase.
- **S3 Client**: Passed as a parameter to avoid redundant client creation.

---

##### Step 5: Update shopify_integration/routes.py

**Action**: Modify the `/shopify/callback` endpoint to test webhook and polling functionality before uploading initial Shopify data to Spaces (if changed), and enhance the `/shopify/webhook` endpoint for incremental updates.

**Why?**  
The callback, triggered post-OAuth, is ideal for initializing data storage, with `validate_state_token` ensuring security. We’ll verify webhook and polling functionality before uploading, setting `upload_status` to "success" if tests pass and data is either uploaded or unchanged, or "failed" otherwise. The webhook endpoint processes real-time updates, uploading only when data changes. This ensures data integrity and efficiency without additional state token logic for Spaces operations.

**Instructions**:  
Update `shopify_integration/routes.py` as follows:

```python
import os
import json
import boto3
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, verify_hmac, register_webhooks, poll_shopify_data
from shared.utils import generate_state_token, validate_state_token
from digitalocean_integration.utils import has_data_changed, upload_to_spaces  # Add these imports
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

    os.environ[f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"] = token_data["access_token"]

    # Register webhooks
    webhook_status = "success"
    try:
        await register_webhooks(shop, token_data["access_token"])
    except Exception as e:
        webhook_status = "failed"
        print(f"Webhook registration failed for {shop}: {str(e)}")

    shopify_data = await get_shopify_data(token_data["access_token"], shop)

    # Test webhook
    webhook_test_result = {"status": "failed", "message": "Webhook test not run"}
    if webhook_status == "success":
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

    # Test polling
    access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
    access_token = os.getenv(access_token_key)
    polling_test_result = await poll_shopify_data(access_token, shop)
    print(f"Polling test result for {shop}: {polling_test_result}")

    # Upload to Spaces if webhook and polling tests succeed
    upload_status = "failed"
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
            spaces_key = f"{shop}/shopify_data.json"
            if has_data_changed(shopify_data, spaces_key, s3_client):
                upload_to_spaces(shopify_data, spaces_key, s3_client)
                print(f"Uploaded data to Spaces for {shop}")
            else:
                print(f"No upload needed for {shop}: Data unchanged")
            upload_status = "success"
        except Exception as e:
            print(f"Failed to upload to Spaces for {shop}: {str(e)}")
            upload_status = "failed"

    return JSONResponse(content={
        "token_data": token_data,
        "shopify_data": shopify_data,
        "webhook_status": webhook_status,
        "webhook_test": webhook_test_result,
        "polling_test": polling_test_result,
        "upload_status": upload_status
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

    # Update data in Spaces if changed
    try:
        shopify_data = await get_shopify_data(access_token, shop)
        spaces_key = f"{shop}/shopify_data.json"
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            region_name=os.getenv("SPACES_REGION", "nyc3"),
            endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
        )
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
- **Imports**: Includes `has_data_changed` and `upload_to_spaces` from `digitalocean_integration.utils`.
- **Callback Logic**: Tests webhook and polling functionality, then checks for data changes before uploading, setting `upload_status` to "success" if tests pass and data is either uploaded or unchanged, or "failed" otherwise.
- **Webhook Condition**: Uses only `webhook_test_result.get("status") == "success"`, ensuring no redundant checks.
- **Status Consistency**: `upload_status` is "success" when tests pass and data handling completes, aligning with other statuses.
- **Webhook Update**: Checks for changes before uploading, logging when updates are skipped.
- **Error Handling**: Logs failures without interrupting the flow, consistent with the codebase.
- **S3 Client**: Creates a single client per operation for efficiency.
- **No State Tokens**: Relies on existing `validate_state_token` for OAuth security.

---

##### Step 6: Update shopify_integration/utils.py

**Action**: Update the `poll_shopify_data` function to return the fetched Shopify data alongside the status, and update the `daily_poll` function to use this data for Spaces uploads (if changed).

**Why?**  
Returning the Shopify data from `poll_shopify_data` ensures it’s accessible for change checks and uploads in `daily_poll`, avoiding redundant API calls to `get_shopify_data`. Checking for changes before uploading aligns with the callback’s test-first and efficiency-focused approach.

**Instructions**:  
Update `shopify_integration/utils.py`, preserving existing functions and updating `poll_shopify_data` and `daily_poll`, with all necessary imports:

```python
import os
import httpx
import asyncio
import hashlib  # Add this import
import base64  # Add this import
import hmac    # Add this import
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
        shopify_data = await get_shopify_data(access_token, shop)
        return {"status": "success", "data": shopify_data}
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
            access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
            access_token = os.getenv(access_token_key)
            if access_token:
                poll_result = await poll_shopify_data(access_token, shop)
                if poll_result["status"] == "success":
                    shopify_data = poll_result["data"]
                    spaces_key = f"{shop}/shopify_data.json"
                    session = boto3.session.Session()
                    s3_client = session.client(
                        "s3",
                        region_name=os.getenv("SPACES_REGION", "nyc3"),
                        endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
                        aws_access_key_id=os.getenv("SPACES_ACCESS_KEY"),
                        aws_secret_access_key=os.getenv("SPACES_SECRET_KEY")
                    )
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
- **Imports**: Adds `hashlib`, `base64`, `hmac` for `verify_hmac`, plus `boto3`, `has_data_changed`, and `upload_to_spaces` for Spaces operations.
- **Updated `poll_shopify_data`**: Returns `{"status": "success", "data": shopify_data}` on success, ensuring data access.
- **Updated `daily_poll`**: Uses `poll_result["data"]`, avoiding redundant `get_shopify_data` calls.
- **Error Handling**: Checks `poll_result["status"]` and logs failures, allowing the loop to continue.
- **Logging**: Distinguishes between successful uploads and skipped updates.
- **Scheduler**: Uses the existing `app.py` scheduler (runs at 00:00 daily).
- **Preservation**: Retains existing functions unchanged, adding necessary imports.

---

##### Step 7: Update requirements.txt

**Action**: Add `boto3` to support Spaces integration.

**Instructions**:  
Update `requirements.txt`:

```plaintext
fastapi
uvicorn
httpx
python-dotenv
apscheduler
boto3
```

**Why?**  
- **Boto3**: Required for Spaces API interactions, building on existing dependencies.

---

##### Summary: Why This Subchapter Matters

- **Data Synchronization**: Integrates Spaces for initial data storage, real-time webhook updates, and daily polling, with uploads contingent on successful tests and data changes.
- **Efficient Design**: Avoids redundant uploads and API calls by checking for changes and reusing fetched data.
- **Modular Design**: Adds `digitalocean_integration/utils.py` with Spaces-specific functions (`compute_data_hash`, `has_data_changed`, `upload_to_spaces`) and extends existing modules.
- **Bot Readiness**: Ensures the sales bot has up-to-date Shopify data for accurate recommendations.

**Next Steps**:  
- Set up DigitalOcean Spaces and obtain credentials (Subchapter 3.1).  
- Test the full synchronization flow, including edge cases (Subchapter 3.3).  
- Optimize webhook handling for specific event types (Subchapter 3.3).

---