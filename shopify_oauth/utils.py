import os
import httpx
import json
from fastapi import HTTPException

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

async def get_shopify_data(access_token: str, shop: str):
    url = f"https://{shop}/admin/api/2025-04/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    query = """
    query SalesBotQuery {
      shop {
        id
        name
        description
        primaryDomain {
          url
        }
      }
      currentAppInstallation {
        id
        accessScopes {
          handle
        }
      }
      publications(first: 1) {
        edges {
          node {
            id
            name
          }
        }
      }
      products(first: 10, sortKey: RELEVANCE) {
        edges {
          node {
            id
            title
            description
            handle
            productType
            vendor
            tags
            variants(first: 5) {
              edges {
                node {
                  id
                  title
                  price
                  availableForSale
                  inventoryItem {
                    id
                    inventoryLevels(first: 5) {
                      edges {
                        node {
                          id
                          quantities(names: ["available"]) {
                            name
                            quantity
                          }
                          location {
                            id
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            metafields(first: 5) {
              edges {
                node {
                  id
                  key
                  namespace
                  value
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      collections(first: 5, sortKey: TITLE) {
        edges {
          node {
            id
            title
            handle
            description
            products(first: 5) {
              edges {
                node {
                  id
                  title
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      codeDiscountNodes(first: 5, sortKey: TITLE) {
        edges {
          node {
            id
            codeDiscount {
              ... on DiscountCodeBasic {
                title
                codes(first: 5) {
                  edges {
                    node {
                      code
                    }
                  }
                }
                customerGets {
                  value {
                    ... on DiscountAmount {
                      amount {
                        amount
                        currencyCode
                      }
                    }
                    ... on DiscountPercentage {
                      percentage
                    }
                  }
                }
                startsAt
                endsAt
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      locations(first: 5) {
        edges {
          node {
            id
            name
            address {
              city
              country
              zip
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      marketingEvents(first: 5) {
        edges {
          node {
            id
            description
            type
            startedAt
            endedAt
          }
        }
      }
      articles(first: 5) {
        edges {
          node {
            id
            title
            handle
            publishedAt
          }
        }
      }
      blogs(first: 5) {
        edges {
          node {
            id
            title
            handle
          }
        }
      }
      pages(first: 5) {
        edges {
          node {
            id
            title
            handle
            createdAt
          }
        }
      }
      inventoryItems(first: 5) {
        edges {
          node {
            id
            sku
            createdAt
            inventoryLevels(first: 5) {
              edges {
                node {
                  id
                  quantities(names: ["available"]) {
                    name
                    quantity
                  }
                }
              }
            }
          }
        }
      }
      productTags(first: 5) {
        edges {
          node
        }
      }
      productTypes(first: 5) {
        edges {
          node
        }
      }
      productVariants(first: 5) {
        edges {
          node {
            id
            title
            price
            product {
              id
              title
            }
          }
        }
      }
    }
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"query": query})
        response.raise_for_status()
        response_data = response.json()

        if "errors" in response_data:
            error_message = "; ".join([error["message"] for error in response_data["errors"]])
            raise HTTPException(status_code=400, detail=f"GraphQL query failed: {error_message}")

        return response_data

def preprocess_shopify_data(raw_data: dict) -> dict:
    """
    Preprocess and normalize Shopify GraphQL response into a clean JSON format,
    adding full product URLs and excluding empty lists and dictionaries.
    """
    # Get the shop's base URL
    shop_url = raw_data["data"]["shop"]["primaryDomain"]["url"]

    preprocessed = {
        "shop": {
            "name": raw_data["data"]["shop"]["name"],
            "url": shop_url
        }
    }

    # Initialize products and discounts lists
    products = []
    discounts = []

    # Process discount codes
    for discount in raw_data["data"].get("codeDiscountNodes", {}).get("edges", []):
        discount = discount["node"]["codeDiscount"]
        if discount.get("title"):
            discount_data = {
                "code": discount["codes"]["edges"][0]["node"]["code"],
                "title": discount["title"],
                "percentage": discount["customerGets"]["value"].get("percentage", 0) * 100,
                "starts_at": discount["startsAt"],
                "ends_at": discount["endsAt"]
            }
            discounts.append(discount_data)

    # Only include discounts if non-empty
    if discounts:
        preprocessed["discounts"] = discounts

    # Process products
    for product in raw_data["data"].get("products", {}).get("edges", []):
        product = product["node"]
        # Construct full product URL
        product_url = f"{shop_url}/products/{product['handle']}"
        
        product_data = {
            "id": product["id"],
            "title": product["title"],
            "type": product["productType"],
            "vendor": product["vendor"],
            "handle": product["handle"],
            "url": product_url,
            "description": product["description"] or ""
        }

        # Only include tags if non-empty
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
                    metafields[key] = {
                        "value": value["value"],
                        "unit": value["unit"]
                    }
                except json.JSONDecodeError:
                    metafields[key] = value
            else:
                metafields[key] = value
        # Only include metafields if non-empty
        if metafields:
            product_data["metafields"] = metafields

        # Process variants
        variants = []
        for var in product.get("variants", {}).get("edges", []):
            var = var["node"]
            inventory = var["inventoryItem"]["inventoryLevels"]["edges"]
            quantity = inventory[0]["node"]["quantities"][0]["quantity"] if inventory else 0
            variant_data = {
                "title": var["title"],
                "price": float(var["price"]),
                "available": var["availableForSale"],
                "inventory_quantity": quantity,
                "location": inventory[0]["node"]["location"]["name"] if inventory else "Unknown"
            }
            variants.append(variant_data)
        # Only include variants if non-empty
        if variants:
            product_data["variants"] = variants

        # Only append product if it has meaningful data (e.g., variants or metafields)
        if variants or metafields:
            products.append(product_data)

    # Only include products if non-empty
    if products:
        preprocessed["products"] = products

    return preprocessed