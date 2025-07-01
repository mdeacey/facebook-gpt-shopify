Chapter 2: Shopify Integration
Subchapter 2.4: Preprocessing Shopify Data
This subchapter enhances the FastAPI application by preprocessing the raw Shopify GraphQL data fetched in Subchapter 2.1 into a lean, sales-oriented JSON format for the GPT Messenger sales bot. The bot requires compact data to recommend products, promote discounts, and generate Messenger preview cards. The preprocess_shopify_data function flattens the nested GraphQL response, normalizes fields (e.g., prices as floats), adds full URLs, and applies specific rules: excludes internal IDs (e.g., gid), omits handle (redundant with url), includes inventory_quantity only for tracked variants (positive quantities, e.g., snowboards), omits it for untracked variants (e.g., gift cards), removes inventory_tracked, excludes unavailable variants and draft/archived products, omits empty lists/dictionaries, and adds fallback descriptions for empty fields. We update the shopify_oauth/utils.py module from Subchapter 2.1 and ensure the /shopify/callback endpoint (tested in Subchapter 2.3) returns token_data and preprocessed_data. This subchapter completes the Shopify integration, building on Subchapters 2.1–2.3 and Chapter 1’s Facebook integration.

Step 1: Understand the Need for Preprocessing
The Shopify GraphQL API (Subchapter 2.1) returns a verbose, nested JSON structure with edges.node patterns, internal IDs (e.g., gid://shopify/Product/...), and redundant fields like handle. Inventory data varies: tracked variants (e.g., snowboards) have positive quantities, while untracked variants (e.g., gift cards) lack meaningful stock or have zero quantity but are availableForSale. The sales bot needs a streamlined dataset with:

Shop info: Name and URL for branding.
Products: Title, type, vendor, URL, description, tags, metafields (e.g., snowboard_length), and variants (title, price, availability, location, and inventory_quantity for tracked items only).
Discounts: Code, title, percentage or fixed amount, start/end dates.
Collections: Title, URL, and product titles for recommendations.
Exclusions: No gid, handle, unavailable variants (availableForSale: false), draft/archived products, or empty lists/dictionaries (e.g., tags: [], metafields: {}).
Inventory: Include inventory_quantity only for tracked variants (quantity > 0); omit for untracked variants (no inventory or quantity = 0 but availableForSale: true); exclude inventory_tracked.
Fallbacks: Generate descriptions for empty description fields.

Why preprocess?

Flattens nested structures for easier bot consumption.
Adds URLs for Messenger preview cards.
Excludes irrelevant/redundant data and empty fields to reduce noise.
Handles inventory logically for tracked (e.g., snowboards) and untracked (e.g., gift cards) variants.
Ensures all products have promotable descriptions.


Step 2: Update shopify_oauth/utils.py with Preprocessing Logic
Replace the placeholder preprocess_shopify_data function in shopify_oauth/utils.py (from Subchapter 2.1) with the full implementation to process the raw GraphQL response.
Code in shopify_oauth/utils.py:
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
            products(first: 5) {
              edges { node { title } }
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

Why this function?

Flattening: Removes edges.node nesting, making fields like title, price, and inventory_quantity directly accessible.
Normalization: Converts prices to floats and parses metafield JSON (e.g., snowboard_length into value/unit pairs).
URLs: Adds product (/products/{handle}) and collection (/collections/{handle}) URLs for Messenger preview cards.
Exclusions:
Omits gid and other internal IDs.
Excludes handle, as url suffices.
Filters unavailable variants (availableForSale: false) and draft/archived products (status: DRAFT, ARCHIVED, or Archived tag).
Omits empty lists (e.g., tags: []) and dictionaries (e.g., metafields: {}), skipping products, discounts, collections if empty.


Inventory Handling:
Includes inventory_quantity only for tracked variants (quantity > 0, e.g., snowboards with 10 units).
Omits inventory_quantity for untracked variants (no inventory or quantity = 0 but availableForSale: true, e.g., gift cards).
Excludes inventory_tracked, as the presence/absence of inventory_quantity indicates tracking status.


Fallback Descriptions: Generates descriptions using type, vendor, and tags if description is empty (e.g., “A snowboard from Hydrogen Vendor with features like Accessory, Sport, Winter”).
Discounts: Supports percentage (e.g., 80% off) and fixed-amount discounts, with ends_at: "N/A" for open-ended discounts.
Error Handling: Gracefully handles edge cases (e.g., missing inventory, invalid metafield JSON).

Why in utils.py?

Keeps preprocessing logic alongside OAuth and data-fetching utilities (Subchapter 2.1), maintaining modularity and reusability.
Aligns with the sales bot’s need for processed data, as tested in Subchapter 2.3.


Step 3: Verify shopify_oauth/routes.py
The /shopify/callback endpoint in shopify_oauth/routes.py (Subchapter 2.1) already includes preprocess_shopify_data, returning token_data and preprocessed_data. For reference, the relevant code is:
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

    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    preprocessed_data = preprocess_shopify_data(shopify_data)
    return JSONResponse(content={
        "token_data": token_data,
        "preprocessed_data": preprocessed_data
    })

Why?

Ensures the callback endpoint (tested in Subchapter 2.3) returns sales-ready data, discarding verbose raw GraphQL data.
Maintains modularity by leveraging preprocess_shopify_data from utils.py.
Aligns with the example response in Subchapter 2.3, providing token_data and preprocessed_data.


Step 4: Verify Dependencies
The preprocessing logic uses the standard json library and existing dependencies from Subchapter 2.1. No changes are needed to requirements.txt.
requirements.txt (unchanged):
fastapi
uvicorn
python-dotenv
httpx

Why?

The json library handles metafield parsing, and existing dependencies (httpx, fastapi, etc.) suffice, keeping the project lightweight.


Step 5: Test the Preprocessing
To verify preprocessing, follow the testing steps in Subchapter 2.3:

Run the app: python app.py.
Authenticate via /shopify/acme-7cu19ngr/login.
Check the /shopify/callback response (example below) to ensure:
preprocessed_data includes shop, products, discounts, and collections.
No gid, handle, or empty lists/dictionaries.
inventory_quantity present only for tracked variants (e.g., snowboards), omitted for untracked (e.g., gift cards), with no inventory_tracked.
Unavailable variants and draft/archived products excluded.
Fallback descriptions for empty fields (e.g., “The Collection Snowboard: Hydrogen”).
Discounts match expected format (e.g., 80% off for “CODE_DISCOUNT_BLACKFRIDAY”).



Example Response from /shopify/callback (from Subchapter 2.3):
{
  "token_data": {
    "access_token": "shpua_9a72896d590dbff5d3cf818f49710f67",
    "scope": "read_product_listings,read_inventory,read_discounts,read_locations,read_products"
  },
  "preprocessed_data": {
    "shop": {
      "name": "acme-7cu19ngr",
      "url": "https://acme-7cu19ngr.myshopify.com"
    },
    "discounts": [
      {
        "code": "CODE_DISCOUNT_BLACKFRIDAY",
        "title": "CODE_DISCOUNT_BLACKFRIDAY",
        "percentage": 80.0,
        "starts_at": "2025-11-28T00:00:00Z",
        "ends_at": "2025-11-29T00:00:00Z"
      }
    ],
    "collections": [
      {
        "title": "Automated Collection",
        "url": "https://acme-7cu19ngr.myshopify.com/collections/automated-collection",
        "products": [
          "The Collection Snowboard: Liquid",
          "The Multi-managed Snowboard",
          "The Multi-location Snowboard",
          "The Compare at Price Snowboard",
          "The Collection Snowboard: Hydrogen"
        ]
      },
      {
        "title": "Home page",
        "url": "https://acme-7cu19ngr.myshopify.com/collections/frontpage",
        "products": [
          "The Inventory Not Tracked Snowboard"
        ]
      },
      {
        "title": "Hydrogen",
        "url": "https://acme-7cu19ngr.myshopify.com/collections/hydrogen",
        "products": [
          "The Collection Snowboard: Liquid",
          "The Collection Snowboard: Oxygen",
          "The Collection Snowboard: Hydrogen"
        ]
      }
    ],
    "products": [
      {
        "title": "The Inventory Not Tracked Snowboard",
        "type": "snowboard",
        "vendor": "acme-7cu19ngr",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-inventory-not-tracked-snowboard",
        "description": "A snowboard from acme-7cu19ngr with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 949.95,
            "available": true,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "Gift Card",
        "type": "giftcard",
        "vendor": "Snowboard Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/gift-card",
        "description": "This is a gift card for the store",
        "variants": [
          {
            "title": "$10",
            "price": 10.0,
            "available": true,
            "location": "Shop location"
          },
          {
            "title": "$25",
            "price": 25.0,
            "available": true,
            "location": "Shop location"
          },
          {
            "title": "$50",
            "price": 50.0,
            "available": true,
            "location": "Shop location"
          },
          {
            "title": "$100",
            "price": 100.0,
            "available": true,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Complete Snowboard",
        "type": "snowboard",
        "vendor": "Snowboard Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-complete-snowboard",
        "description": "This PREMIUM snowboard is so SUPERDUPER awesome!",
        "tags": ["Premium", "Snow", "Snowboard", "Sport", "Winter"],
        "variants": [
          {
            "title": "Ice",
            "price": 699.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          },
          {
            "title": "Dawn",
            "price": 699.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          },
          {
            "title": "Powder",
            "price": 699.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          },
          {
            "title": "Electric",
            "price": 699.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          },
          {
            "title": "Sunset",
            "price": 699.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Videographer Snowboard",
        "type": "snowboard",
        "vendor": "acme-7cu19ngr",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-videographer-snowboard",
        "description": "A snowboard from acme-7cu19ngr with features like high-quality.",
        "variants": [
          {
            "title": "Default Title",
            "price": 885.95,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "Selling Plans Ski Wax",
        "type": "accessories",
        "vendor": "acme-7cu19ngr",
        "url": "https://acme-7cu19ngr.myshopify.com/products/selling-plans-ski-wax",
        "description": "A accessories from acme-7cu19ngr with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "variants": [
          {
            "title": "Selling Plans Ski Wax",
            "price": 24.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          },
          {
            "title": "Special Selling Plans Ski Wax",
            "price": 49.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          },
          {
            "title": "Sample Selling Plans Ski Wax",
            "price": 9.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Hidden Snowboard",
        "type": "snowboard",
        "vendor": "Snowboard Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-hidden-snowboard",
        "description": "A snowboard from Snowboard Vendor with features like Premium, Snow, Snowboard, Sport, Winter.",
        "tags": ["Premium", "Snow", "Snowboard", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 749.95,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Collection Snowboard: Hydrogen",
        "type": "snowboard",
        "vendor": "Hydrogen Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-collection-snowboard-hydrogen",
        "description": "A snowboard from Hydrogen Vendor with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 600.0,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Minimal Snowboard",
        "type": "",
        "vendor": "acme-7cu19ngr",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-minimal-snowboard",
        "description": "A  from acme-7cu19ngr with features like high-quality.",
        "variants": [
          {
            "title": "Default Title",
            "price": 885.95,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Compare at Price Snowboard",
        "type": "snowboard",
        "vendor": "acme-7cu19ngr",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-compare-at-price-snowboard",
        "description": "A snowboard from acme-7cu19ngr with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 785.95,
            "available": true,
            "inventory_quantity": 10,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Collection Snowboard: Oxygen",
        "type": "snowboard",
        "vendor": "Hydrogen Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-collection-snowboard-oxygen",
        "description": "A snowboard from Hydrogen Vendor with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 1025.0,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Multi-location Snowboard",
        "type": "snowboard",
        "vendor": "acme-7cu19ngr",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-multi-location-snowboard",
        "description": "A snowboard from acme-7cu19ngr with features like Premium, Snow, Snowboard, Sport, Winter.",
        "tags": ["Premium", "Snow", "Snowboard", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 729.95,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The Multi-managed Snowboard",
        "type": "snowboard",
        "vendor": "Multi-managed Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-multi-managed-snowboard",
        "description": "A snowboard from Multi-managed Vendor with features like Premium, Snow, Snowboard, Sport, Winter.",
        "tags": ["Premium", "Snow", "Snowboard", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 629.95,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      },
      {
        "title": "The 3p Fulfilled Snowboard",
        "type": "snowboard",
        "vendor": "acme-7cu19ngr",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-3p-fulfilled-snowboard",
        "description": "A snowboard from acme-7cu19ngr with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 2629.95,
            "available": true,
            "inventory_quantity": 20,
            "location": "Snow City Warehouse"
          }
        ]
      },
      {
        "title": "The Collection Snowboard: Liquid",
        "type": "snowboard",
        "vendor": "Hydrogen Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-collection-snowboard-liquid",
        "description": "A snowboard from Hydrogen Vendor with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "variants": [
          {
            "title": "Default Title",
            "price": 749.95,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      }
    ]
  }
}

Why this output?

Sales-Ready: Includes shop, products, discounts, and collections with URLs for Messenger preview cards.
Filtered Data: Excludes gid, handle, unavailable variants, draft/archived products, and empty structures (e.g., tags: []).
Inventory: inventory_quantity included for tracked variants (e.g., snowboards with 10 or 50 units), omitted for untracked (e.g., gift cards), with no inventory_tracked.
Fallbacks: Generated descriptions for products like “The Collection Snowboard: Hydrogen”.
Discounts: Matches the expected format (e.g., 80% off for “CODE_DISCOUNT_BLACKFRIDAY”).
Consistency: Aligns with Subchapter 2.3’s testing output, confirming the preprocessing works as expected.


Step 6: Example Sales Bot Interaction
Using the preprocessed data (integrated with Chapter 1’s Messenger API):
Customer: I’m looking for a premium snowboard.Bot: Try The Complete Snowboard! It’s a premium snowboard for $699.95, with only 10 units left in Ice or Dawn variants. Use CODE_DISCOUNT_BLACKFRIDAY for 80% off (Nov 28–29, 2025), just $139.99. Check it out: [https://acme-7cu19ngr.myshopify.com/products/the-complete-snowboard]. Explore our Premium Snowboards collection: [https://acme-7cu19ngr.myshopify.com/collections/automated-collection].  
Customer: Any gift cards?Bot: Our Gift Card comes in $10–$100 options, perfect for gifting! Available now: [https://acme-7cu19ngr.myshopify.com/products/gift-card].  
Why?

The preprocessed data provides concise, actionable information (URLs, prices, inventory, discounts) for the bot to generate engaging responses.
URLs enable Messenger preview cards, enhancing customer interaction.
Combines with Chapter 1’s Facebook integration for seamless messaging.


Step 7: Troubleshooting Common Issues
If the preprocessed data is incorrect:

Missing products/discounts/collections: Verify the GraphQL query in Subchapter 2.1 fetches all required fields and the acme-7cu19ngr store (Subchapter 2.2) has test data.
Incorrect inventory: Ensure inventory_quantity logic checks for quantity > 0 and inventoryLevels.edges existence, omitting for untracked variants.
Empty fields not excluded: Confirm the preprocessing logic skips empty lists/dictionaries.
Invalid URLs: Check that shop_url is correctly extracted from primaryDomain.url and appended with /products/{handle} or /collections/{handle}.
Metafield parsing errors: Ensure JSON parsing for snowboard_length/snowboard_weight handles invalid cases gracefully.

Why?

These checks ensure the preprocessing logic is robust and produces bot-ready data, aligning with Subchapter 2.3’s testing.


Summary: Why This Subchapter Matters

Lean Output: Produces a compact dataset by excluding gid, handle, untracked inventory, and empty structures.
Sales-Optimized: Adds URLs, filters unavailable items, and includes fallback descriptions for bot-friendly data.
Inventory Handling: Correctly manages tracked (e.g., snowboards) and untracked (e.g., gift cards) variants, omitting inventory_tracked.
Bot Readiness: Enables the sales bot to recommend products, promote discounts, and generate Messenger preview cards, integrating with Chapter 1’s Facebook functionality.
Robustness: Handles edge cases (e.g., missing data, invalid JSON) for reliable operation.

Next Steps:

Review Subchapters 2.1–2.3 if issues arise with OAuth, store setup, or testing.
Use the preprocessed data with Chapter 1’s Messenger integration to deploy the sales bot.
Extend the app with additional features (e.g., webhook handling, bot logic) as needed.
