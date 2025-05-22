import os
import httpx
import json
from fastapi import HTTPException
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

def preprocess_shopify_data(raw_data: dict) -> dict:
    """
    Preprocess Shopify GraphQL response into a sales-bot-friendly JSON format.
    Excludes unavailable products/variants, internal IDs, handle, and empty fields.
    Includes inventory_quantity only for tracked variants; omits it for untracked ones.
    Adds full URLs and fallback descriptions.
    """
    shop_url = raw_data["data"]["shop"]["primaryDomain"]["url"]
    preprocessed = {
        "shop": {
            "name": raw_data["data"]["shop"]["name"],
            "url": shop_url
        }
    }

    # Process discounts
    discounts = []
    for discount in raw_data["data"].get("codeDiscountNodes", {}).get("edges", []):
        discount = discount["node"]["codeDiscount"]
        if discount.get("title"):
            value = discount["customerGets"]["value"]
            discount_data = {
                "code": discount["codes"]["edges"][0]["node"]["code"],
                "title": discount["title"],
                "starts_at": discount["startsAt"],
                "ends_at": "N/A" if not discount["endsAt"] else discount["endsAt"]
            }
            if "percentage" in value:
                discount_data["percentage"] = value["percentage"] * 100
            elif "amount" in value:
                discount_data["amount"] = {
                    "value": float(value["amount"]["amount"]),
                    "currency": value["amount"]["currencyCode"]
                }
            discounts.append(discount_data)
    if discounts:
        preprocessed["discounts"] = discounts

    # Process collections
    collections = []
    for collection in raw_data["data"].get("collections", {}).get("edges", []):
        collection = collection["node"]
        collection_data = {
            "title": collection["title"],
            "url": f"{shop_url}/collections/{collection['handle']}",
            "products": [p["node"]["title"] for p in collection["products"]["edges"]]
        }
        if collection_data["products"]:  # Only include non-empty collections
            collections.append(collection_data)
    if collections:
        preprocessed["collections"] = collections

    # Process products
    products = []
    for product in raw_data["data"].get("products", {}).get("edges", []):
        product = product["node"]
        # Skip draft or archived products
        if product["status"] in ["DRAFT", "ARCHIVED"] or "Archived" in product["tags"]:
            continue
        product_url = f"{shop_url}/products/{product['handle']}"
        product_data = {
            "title": product["title"],
            "type": product["productType"],
            "vendor": product["vendor"],
            "url": product_url,
            "description": product["description"] or f"A {product['productType'].lower()} from {product['vendor']} with features like {', '.join(product['tags'] or ['high-quality'])}."
        }
        if product["tags"]:
            product_data["tags"] = product["tags"]

        # Process metafields
        metafields = {}
        for mf in product.get("metafields", {}).get("edges", []):
            mf = mf["node"]
            key = mf["key"]
            value = mf["value"]
            if key in ["snowboard_length", "snowboard_weight"]:
                try:
                    value = json.loads(value)
                    metafields[key] = {"value": value["value"], "unit": value["unit"]}
                except json.JSONDecodeError:
                    metafields[key] = value
            else:
                metafields[key] = value
        if metafields:
            product_data["metafields"] = metafields

        # Process variants
        variants = []
        for var in product.get("variants", {}).get("edges", []):
            var = var["node"]
            if not var["availableForSale"]:
                continue  # Skip unavailable variants
            inventory = var["inventoryItem"]["inventoryLevels"]["edges"]
            quantity = inventory[0]["node"]["quantities"][0]["quantity"] if inventory else 0
            variant_data = {
                "title": var["title"],
                "price": float(var["price"]),
                "available": var["availableForSale"],
                "location": inventory[0]["node"]["location"]["name"] if inventory else "Online"
            }
            # Include inventory_quantity only for tracked variants (quantity > 0)
            if inventory and quantity > 0:
                variant_data["inventory_quantity"] = quantity
            variants.append(variant_data)
        if not variants:
            continue  # Skip products with no available variants
        product_data["variants"] = variants
        products.append(product_data)

    if products:
        preprocessed["products"] = products

    return preprocessed