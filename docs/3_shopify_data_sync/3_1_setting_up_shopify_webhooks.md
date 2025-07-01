Subchapter 3.1: Setting Up Shopify Webhooks for Real-Time Updates
Introduction
Shopify webhooks allow your application to receive real-time notifications about key events in your store, such as product updates, inventory changes, or new orders. This keeps your sales bot in sync without constant polling. In this subchapter, we’ll configure a secure webhook endpoint in your FastAPI application, register a comprehensive set of webhooks during the OAuth flow, and make the webhook address configurable via environment variables.

Step 1: Update shopify_oauth/routes.py
This file defines the routes for Shopify OAuth and now includes a webhook endpoint. Below is the complete, updated version.
Updated File: shopify_oauth/routes.py
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, preprocess_shopify_data, verify_hmac, register_webhooks
from shared.utils import generate_state_token, validate_state_token

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    """
    Initiates the Shopify OAuth flow by redirecting the user to Shopify's authorization page.
    """
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_webhooks"

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
    """
    Handles the OAuth callback from Shopify, exchanges the code for an access token,
    registers webhooks, and retrieves initial shop data.
    """
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")
    state = request.query_params.get("state")

    if not code or not shop or not state:
        raise HTTPException(status_code=400, detail="Missing code, shop, or state parameter")

    validate_state_token(state)

    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    # Store access token in environment variables
    os.environ[f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"] = token_data["access_token"]

    # Register webhooks for this shop
    await register_webhooks(shop, token_data["access_token"])

    # Fetch and preprocess initial shop data
    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    preprocessed_data = preprocess_shopify_data(shopify_data)

    return JSONResponse(content={
        "token_data": token_data,
        "preprocessed_data": preprocessed_data,
    })

@router.post("/webhook")
async def shopify_webhook(request: Request):
    """
    Webhook endpoint to receive real-time updates from Shopify.
    Verifies the request's HMAC signature and processes the payload.
    """
    # Verify HMAC signature
    if not await verify_hmac(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    # Extract shop domain from headers
    shop = request.headers.get("X-Shopify-Shop-Domain")
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop domain")

    # Fetch access token dynamically
    access_token_key = f"SHOPIFY_ACCESS_TOKEN_{shop.replace('.', '_')}"
    access_token = os.getenv(access_token_key)
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token not found")

    # Process the payload
    payload = await request.json()
    event_type = request.headers.get("X-Shopify-Topic")
    print(f"Received {event_type} event from {shop}: {payload}")

    return {"status": "success"}

Key Changes:  

Webhook Endpoint: Added @router.post("/webhook") to handle Shopify webhook requests with HMAC verification.  
Dynamic Handling: Shop domain and access token are retrieved dynamically.  
OAuth Callback: Updated to register webhooks after obtaining the access token.


Step 2: Update shopify_oauth/utils.py
This file contains utilities for Shopify OAuth, data fetching, and now includes functions for HMAC verification and webhook registration. Below is the complete, updated version.
Updated File: shopify_oauth/utils.py
import os
import hmac
import hashlib
import base64
import httpx
from fastapi import HTTPException, Request
import asyncio

async def exchange_code_for_token(code: str, shop: str):
    """
    Exchanges the authorization code for an access token from Shopify.
    """
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
    """
    Fetches shop data using Shopify's GraphQL API with retry logic.
    """
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
    """
    Verify the HMAC signature of a Shopify webhook request.
    """
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if not hmac_header:
        return False

    body = await request.body()
    secret = os.getenv("SHOPIFY_API_SECRET")
    expected_hmac = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    expected_hmac_b64 = base64.b64encode(expected_hmac).decode()

    return hmac.compare_digest(hmac_header, expected_hmac_b64)

async def register_webhooks(shop: str, access_token: str):
    """
    Register a comprehensive set of webhooks for real-time updates.
    """
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
    """
    Retrieve the list of existing webhooks for a shop.
    """
    url = f"https://{shop}/admin/api/2025-04/webhooks.json"
    headers = {"X-Shopify-Access-Token": access_token}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json().get("webhooks", [])

async def register_webhook(shop: str, access_token: str, topic: str, address: str):
    """
    Register a single webhook with Shopify.
    """
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

Key Changes:  

HMAC Verification: Added verify_hmac for secure webhook handling.  
Webhook Registration: Added register_webhooks, get_existing_webhooks, and register_webhook to manage webhooks during OAuth.


Step 3: Configure Environment Variables
Add the WEBHOOK_ADDRESS to your .env file to specify the webhook endpoint URL.
Updated .env Example:
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
WEBHOOK_ADDRESS=https://your-app.com/shopify/webhook  # Add this line

# Other credentials...

Why:  

Centralized Configuration: WEBHOOK_ADDRESS is stored in the environment, making it easy to update across deployments.


Step 4: Update OAuth Scope
Ensure your app requests the necessary permissions for webhooks.
In shopify_oauth/routes.py, the scope in start_oauth includes:
scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_webhooks"

Why:  

Permissions: write_webhooks allows your app to register webhooks via the API.


Summary
This subchapter establishes a secure, dynamic webhook system in your FastAPI application, enabling real-time updates from Shopify. The webhook address is configurable via the .env file, and webhooks are registered automatically during OAuth for each shop.