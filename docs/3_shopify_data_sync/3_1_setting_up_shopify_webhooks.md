# Subchapter 1.1: Setting Up Shopify Webhooks for Real-Time Updates

## Introduction
Shopify webhooks enable your application to receive real-time notifications about store events, keeping your sales bot up-to-date. This subchapter guides you through setting up a secure webhook endpoint in your FastAPI application, integrating HMAC verification, registering webhooks during the OAuth flow with appropriate scopes, and including an automatic test to verify functionality post-authentication.

## Prerequisites
- Completed Shopify OAuth setup from Chapter 2.
- Your FastAPI application is running locally or in a production-like environment.
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) are set.

---

## Step 1: Update `shopify_integration/routes.py`
Configure the webhook endpoint and enhance the OAuth callback to register webhooks and test them automatically with corrected scopes.

**Updated File: `shopify_integration/routes.py`**
```python
import os
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, preprocess_shopify_data, verify_hmac, register_webhooks
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
    # Updated scope to include relevant write permissions for webhook registration
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

    # Register webhooks for this shop
    await register_webhooks(shop, token_data["access_token"])

    # Fetch and preprocess initial shop data
    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    preprocessed_data = preprocess_shopify_data(shopify_data)

    # Automatically test the webhook
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
        test_result = response.json() if response.status_code == 200 else {"error": response.text}
        print(f"Webhook test result for {shop}: {test_result}")

    return JSONResponse(content={
        "token_data": token_data,
        "preprocessed_data": preprocessed_data,
        "webhook_test": test_result
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
- **Environment Variable**: Updated `WEBHOOK_ADDRESS` to `SHOPIFY_WEBHOOK_ADDRESS` in the prerequisites and comments for consistency.

---

## Step 2: Update `shopify_integration/utils.py`
Ensure the utility functions support the webhook setup with the new environment variable.

**Updated File: `shopify_integration/utils.py`**
```python
import os
import hmac
import hashlib
import base64
import httpx
from fastapi import HTTPException, Request
import asyncio
import json

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
```

**Key Changes**:
- **Environment Variable**: Updated `WEBHOOK_ADDRESS` to `SHOPIFY_WEBHOOK_ADDRESS` in `register_webhooks`.

---

## Step 3: Configure Environment Variables
Update your `.env` file to use the new variable name.

**Updated `.env` Example**:
```plaintext
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=https://your-app.com/shopify/webhook  # Updated variable name
```

---

## Summary
This subchapter sets up a secure webhook system with an automatic test during OAuth, using the corrected scope (`write_products`, `write_orders`, `write_inventory`) and renaming `WEBHOOK_ADDRESS` to `SHOPIFY_WEBHOOK_ADDRESS` for clarity.

## Next Steps
- Proceed to Subchapter 1.2 for testing instructions.
- Remove the test logic from the callback after initial testing (optional).