import logging
import os
import httpx
import asyncio
import hmac
import hashlib
import base64
import boto3
from fastapi import HTTPException, Request
from shared.tokens import TokenStorage
from shared.utils import retry_async
from digitalocean_integration.spaces import has_data_changed, upload_to_spaces

logger = logging.getLogger(__name__)

token_storage = TokenStorage()

@retry_async
async def exchange_code_for_token(code: str, shop: str):
    url = f"https://{shop}/admin/oauth/access_token"
    data = {
        "client_id": os.getenv("SHOPIFY_API_KEY"),
        "client_secret": os.getenv("SHOPIFY_API_SECRET"),
        "code": code
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        logger.info(f"Shopify token exchange response for {shop}: {response.status_code}, {response.text}")
        response.raise_for_status()
        return response.json()

async def get_shopify_data(access_token: str, shop: str, retries=3):
    url = f"https://{shop}/admin/api/2025-04/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    metadata_query = """
    query ShopMetadataQuery {
      shop {
        name
        primaryDomain { url }
      }
    }
    """

    products_query = """
    query ProductsQuery {
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

    @retry_async
    async def make_graphql_request(client, url, headers, query):
        return await client.post(url, headers=headers, json={"query": query})

    metadata_result = {}
    products_result = {}
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await make_graphql_request(client, url, headers, metadata_query)
                metadata_data = response.json()
                if "errors" in metadata_data:
                    error_message = "; ".join([error["message"] for error in metadata_data["errors"]])
                    raise HTTPException(status_code=400, detail=f"GraphQL metadata query failed: {error_message}")
                metadata_result = metadata_data["data"]

                response = await make_graphql_request(client, url, headers, products_query)
                products_data = response.json()
                if "errors" in products_data:
                    error_message = "; ".join([error["message"] for error in products_data["errors"]])
                    raise HTTPException(status_code=400, detail=f"GraphQL products query failed: {error_message}")
                products_result = products_data["data"]

                logger.info(f"Shopify data fetched for {shop}")
                return {"metadata": metadata_result, "products": products_result}
            except httpx.HTTPStatusError as e:
                if attempt == retries - 1 or e.response.status_code != 429:
                    logger.error(f"Shopify GraphQL query failed for {shop}: {str(e)}")
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

@retry_async
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
            logger.info(f"Webhook for {topic} already exists for {shop}")

@retry_async
async def get_existing_webhooks(shop: str, access_token: str):
    url = f"https://{shop}/admin/api/2025-04/webhooks.json"
    headers = {"X-Shopify-Access-Token": access_token}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        logger.info(f"Shopify webhooks response for {shop}: {response.status_code}, {response.text}")
        return response.json().get("webhooks", [])

@retry_async
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
        logger.info(f"Shopify webhook registration response for {topic} at {shop}: {response.status_code}, {response.text}")
        if response.status_code != 201:
            raise HTTPException(status_code=500, detail=f"Failed to register webhook: {response.text}")
        logger.info(f"Webhook registered for {topic} at {shop}")

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
            user_uuid = token_storage.get_token(f"USER_UUID_{shop_key}")
            if not access_token or not user_uuid:
                logger.error(f"Missing access token or user UUID for shop {shop}")
                continue
            shopify_data = await get_shopify_data(access_token, shop)
            session = boto3.session.Session()
            s3_client = session.client(
                "s3",
                region_name=os.getenv("SPACES_REGION", "nyc3"),
                endpoint_url=f"https://{os.getenv('SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
                aws_access_key_id=os.getenv("SPACES_API_KEY"),
                aws_secret_access_key=os.getenv("SPACES_API_SECRET")
            )
            spaces_key = f"users/{user_uuid}/shopify/data.json"
            if has_data_changed(shopify_data, spaces_key, s3_client):
                upload_to_spaces(shopify_data, spaces_key, s3_client)
                logger.info(f"Polled and uploaded data for {shop}: Success")
            else:
                logger.info(f"Polled data for {shop}: No upload needed, data unchanged")
        except Exception as e:
            logger.error(f"Daily poll failed for {shop}: {str(e)}")