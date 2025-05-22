Thank you for confirming that Chapter 3 is complete and aligns with your requirements for the Shopify OAuth flow, fetching raw GraphQL data without preprocessing. Now, I’ll provide the updated **Chapter 5**, focusing on the preprocessing step for the GPT sales bot. This chapter will detail the `preprocess_shopify_data` function, which transforms the raw GraphQL response (from Chapter 3) into a lean, sales-oriented JSON format. The updates will incorporate your specific requirements:
- **Exclude `gid`** (all internal IDs, e.g., `gid://shopify/Product/...`).
- **Omit `handle`**, as it’s redundant with `url`.
- **Inventory handling**:
  - Include `inventory_quantity` only for tracked variants (`inventoryLevels.edges` exists and `quantity > 0`, e.g., snowboards).
  - Omit `inventory_quantity` for untracked variants (no `inventoryLevels.edges` or `quantity: 0` but `availableForSale: true`, e.g., gift cards).
  - Remove `inventory_tracked` entirely.
- Support both percentage and fixed-amount discounts.
- Include collections for grouped recommendations.
- Generate fallback descriptions for empty `description` fields.
- Exclude unavailable variants (`availableForSale: false`) and draft/archived products.
- Omit all empty lists (e.g., `tags: []`) and dictionaries (e.g., `metafields: {}`).

The chapter will mirror the structure of the provided Chapter 5, focusing on preprocessing, and align with your sample JSON data (e.g., products like “Gift Card” and “The Complete Snowboard”, discounts like “CODE_DISCOUNT_BLACKFRIDAY”). The GraphQL query remains in Chapter 3, so Chapter 5 will assume the raw data structure from that query. I’ll ensure the preprocessing meets the sales bot’s needs (e.g., URLs for Messenger preview cards) and is compatible with the scope from Chapter 3 (`read_product_listings,read_inventory,read_discounts,read_locations,read_products`).

---

### Chapter 5: Preprocessing Shopify Data for a Sales Bot

In this chapter, we enhance our FastAPI application to preprocess the raw Shopify GraphQL data (fetched in Chapter 3) into a clean, sales-oriented JSON format tailored for a GPT Messenger sales bot. The bot requires a lean dataset to recommend products, promote discounts, and share product URLs that trigger preview cards in platforms like Facebook Messenger. We transform the verbose, nested GraphQL response by flattening structures, normalizing fields (e.g., prices as floats), adding full product and collection URLs, and excluding all empty lists (e.g., `[]`) and dictionaries (e.g., `{}`) to minimize noise. We filter out unavailable products/variants, exclude internal IDs (e.g., `gid`), and remove redundant fields like `handle` (covered by `url`). For inventory, we include `inventory_quantity` only for variants with tracked stock (positive quantities), omitting it for untracked variants (e.g., gift cards, pre-orders) to keep the output concise and customer-focused. Fallback descriptions are added for empty fields to ensure every product is promotable. The `shopify_oauth` module is updated with an optimized `preprocess_shopify_data` function, and the `/shopify/callback` endpoint (from Chapter 3) is modified to return `token_data` and `preprocessed_data`, discarding the raw GraphQL response for a streamlined output. This design ensures the data is ready for the sales bot to drive customer engagement efficiently.

---

#### Step 1: Understand the Need for Preprocessing

The Shopify GraphQL API (used in Chapter 3) returns a complex, nested JSON structure with `edges.node` patterns, internal IDs (e.g., `gid://shopify/Product/...`), and fields like `variants` and `inventoryLevels`. It includes empty lists (e.g., `tags: []`), empty dictionaries (e.g., `metafields: {}`), and fields like `handle`, which is redundant when full URLs are constructed. Some variants, like gift cards, have no meaningful inventory data (untracked, often with `inventory_quantity: 0` but `availableForSale: true`), while others, like snowboards, have specific stock levels. For a GPT sales bot, we need a streamlined dataset with:
- **Shop info**: Name and URL for branding.
- **Products**: Title, type, vendor, URL, description, tags, metafields (e.g., `snowboard_length`), and variants (title, price, availability, location, and `inventory_quantity` for tracked items only), excluding unavailable items.
- **Discounts**: Code, title, percentage or fixed amount, start/end dates for promotions.
- **Collections**: Title, URL, and product titles for grouped recommendations.
- **No internal IDs**: Exclude `gid` and other identifiers irrelevant to customers.
- **No redundant fields**: Omit `handle`, as it’s covered by `url`.
- **No empty structures**: Omit all empty lists/dictionaries to reduce noise.
- **Inventory handling**: Include `inventory_quantity` only for variants with tracked stock (positive quantities); omit it for untracked variants (no inventory data or zero stock but available).
- **Fallback descriptions**: Generate descriptions for products with empty `description` fields.

**Why preprocess?** Preprocessing flattens the data, adds actionable URLs, excludes irrelevant/redundant fields (e.g., IDs, `handle`, untracked inventory), and ensures every product has a description, making the output compact, bot-friendly, and optimized for sales tasks like product recommendations and discount promotions.

---

#### Step 2: Update the Preprocessing Logic

We update the `shopify_oauth/utils.py` module with an optimized `preprocess_shopify_data` function that processes the raw GraphQL response from Chapter 3. The function flattens the nested structure, normalizes fields, adds URLs, and applies the specified inventory logic.

**Code in `shopify_oauth/utils.py` (Updated for Preprocessing)**:
```python
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
```

**Why this function?**
- **Flattening**: Removes `edges.node` structures, making fields like `title`, `price`, and `inventory_quantity` directly accessible.
- **Normalization**: Converts prices to floats and parses metafield JSON (e.g., `snowboard_length` into value/unit pairs).
- **URL Addition**: Adds `url` for products (`/products/{handle}`) and collections (`/collections/{handle}`) for Messenger preview cards.
- **Exclusions**:
  - Omits `gid` (all internal IDs, e.g., `id` fields).
  - Excludes `handle`, as it’s redundant with `url`.
  - Filters unavailable variants (`availableForSale: false`) and draft/archived products (`status: DRAFT`, `ARCHIVED`, or `Archived` tag).
  - Omits empty lists (e.g., `tags: []`) and dictionaries (e.g., `metafields: {}`), skipping `products`, `discounts`, and `collections` keys if empty.
- **Inventory Handling**:
  - Includes `inventory_quantity` only for tracked variants (`inventoryLevels.edges` exists and `quantity > 0`, e.g., snowboards with `quantity: 10`).
  - Omits `inventory_quantity` for untracked variants (no `inventoryLevels.edges` or `quantity: 0` but `availableForSale: true`, e.g., gift cards).
  - Removes `inventory_tracked`, as the presence/absence of `inventory_quantity` indicates tracking status.
- **Fallback Descriptions**: Generates descriptions using `type`, `vendor`, and `tags` if `description` is empty (e.g., “A snowboard from Hydrogen Vendor with features like Accessory, Sport, Winter”).
- **Discounts**: Supports percentage (e.g., 80% off) and fixed-amount discounts, with `ends_at: "N/A"` for open-ended discounts.
- **Error Handling**: Handles edge cases (e.g., missing inventory, invalid metafield JSON) gracefully.

**Why in `utils.py`?** Placing preprocessing alongside OAuth utilities (e.g., token exchange, data fetching) maintains modularity and reusability within the `shopify_oauth` module.

---

#### Step 3: Update shopify_oauth/routes.py to Use Preprocessed Data

We modify the `/shopify/callback` endpoint in `shopify_oauth/routes.py` (from Chapter 3) to call `preprocess_shopify_data` and return `token_data` and `preprocessed_data`, discarding the raw GraphQL response.

**Code in `shopify_oauth/routes.py` (Updated)**:
```python
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, preprocess_shopify_data

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify app config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&response_type=code"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")

    if not code or not shop:
        raise HTTPException(status_code=400, detail="Missing code or shop parameter")

    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    # Fetch and preprocess Shopify data
    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    preprocessed_data = preprocess_shopify_data(shopify_data)

    return JSONResponse(content={
        "token_data": token_data,
        "preprocessed_data": preprocessed_data
    })
```

**Why this change?**
- **Streamlined Response**: Returns `token_data` (for authentication) and `preprocessed_data` (sales-ready data), discarding the verbose raw GraphQL response.
- **Sales Focus**: The `preprocessed_data` is optimized for the bot, with URLs, no IDs or `handle`, and tailored inventory.
- **Modularity**: Leverages `preprocess_shopify_data` from `utils.py`, keeping routing logic separate.

---

#### Step 4: Verify Existing Dependencies

The preprocessing logic uses the standard `json` library for metafield parsing and relies on existing project dependencies (`httpx`, `fastapi`, `python-dotenv`, `uvicorn`). No changes are needed to `requirements.txt`.

**Code in `requirements.txt` (Unchanged)**:
```
fastapi
uvicorn
python-dotenv
httpx
```

**Why no new dependencies?** Using built-in Python libraries and existing dependencies keeps the project lightweight, avoiding unnecessary bloat while meeting all functional requirements.

---

#### Step 5: Test the Implementation

To test the preprocessing:

1. **Run the App**: Start the FastAPI server with `uvicorn app:app --host 0.0.0.0 --port 5000 --reload`.
2. **Authenticate**: Navigate to `/shopify/acme-7cu19ngr/login` to initiate the Shopify OAuth flow (from Chapter 3).
3. **Check Callback**: Verify the `/shopify/callback` response contains `token_data` and `preprocessed_data`.
4. **Inspect Output**:
   - Confirm `preprocessed_data` includes shop info, products, discounts, and collections, with no empty lists (e.g., `tags: []`) or dictionaries (e.g., `metafields: {}`).
   - Ensure each product and collection has a `url` field (e.g., `https://acme-7cu19ngr.myshopify.com/products/the-complete-snowboard`).
   - Verify no `gid` (IDs) or `handle` fields.
   - Check inventory: `inventory_quantity` present only for tracked variants (e.g., `10` for snowboards), omitted for untracked variants (e.g., gift cards), and no `inventory_tracked`.
   - Confirm unavailable variants (e.g., `available: false`) and draft/archived products are excluded.
   - Validate fallback descriptions (e.g., for “The Collection Snowboard: Hydrogen”).
   - Ensure discounts match your sample (e.g., 80% off for “CODE_DISCOUNT_BLACKFRIDAY”).

**Example Response from `/shopify/callback`**:
```json
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
        "title": "Premium Snowboards",
        "url": "https://acme-7cu19ngr.myshopify.com/collections/premium-snowboards",
        "products": ["The Complete Snowboard", "The Hidden Snowboard"]
      }
    ],
    "products": [
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
            "location": "Online"
          },
          {
            "title": "$25",
            "price": 25.0,
            "available": true,
            "location": "Online"
          },
          {
            "title": "$50",
            "price": 50.0,
            "available": true,
            "location": "Online"
          },
          {
            "title": "$100",
            "price": 100.0,
            "available": true,
            "location": "Online"
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
        "metafields": {
          "snowboard_length": {
            "value": 159.0,
            "unit": "CENTIMETERS"
          },
          "snowboard_weight": {
            "value": 7.0,
            "unit": "POUNDS"
          }
        },
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
        "title": "The Collection Snowboard: Hydrogen",
        "type": "snowboard",
        "vendor": "Hydrogen Vendor",
        "url": "https://acme-7cu19ngr.myshopify.com/products/the-collection-snowboard-hydrogen",
        "description": "A snowboard from Hydrogen Vendor with features like Accessory, Sport, Winter.",
        "tags": ["Accessory", "Sport", "Winter"],
        "metafields": {
          "binding_mount": "Optimistic"
        },
        "variants": [
          {
            "title": "Default Title",
            "price": 600.0,
            "available": true,
            "inventory_quantity": 50,
            "location": "Shop location"
          }
        ]
      }
    ]
  }
}
```

**Why this output?**
- **Sales-Ready**: Includes shop, products, discounts, and collections with URLs for Messenger preview cards.
- **No IDs or `handle`**: Excludes `gid` and `handle`, as `url` suffices.
- **Inventory Handling**: `inventory_quantity` included for tracked variants (e.g., snowboards with `10` or `50` units), omitted for untracked variants (e.g., gift cards), no `inventory_tracked`.
- **Filtered Data**: Excludes unavailable variants (e.g., “The Out of Stock Snowboard” with `available: false`), archived products, and products with no variants.
- **No Empty Structures**: Omits `tags: []` (e.g., for “Gift Card”), `metafields: {}`, etc.
- **Fallback Descriptions**: Generated for “The Collection Snowboard: Hydrogen” (empty `description`).
- **Discounts**: Matches your sample (80% off for “CODE_DISCOUNT_BLACKFRIDAY”).

---

#### Step 6: Example Sales Bot Interaction

Using the preprocessed data:

**Customer**: I’m looking for a premium snowboard.  
**Bot**: Try *The Complete Snowboard*! It’s a premium snowboard, 159 cm long, 7 pounds, available in Ice or Dawn for $699.95. Only 10 units left! Use *CODE_DISCOUNT_BLACKFRIDAY* for 80% off (Nov 28–29, 2025), just $139.99. Check it out: [https://acme-7cu19ngr.myshopify.com/products/the-complete-snowboard]. Explore our Premium Snowboards collection: [https://acme-7cu19ngr.myshopify.com/collections/premium-snowboards].  

**Customer**: Any gift cards?  
**Bot**: Our *Gift Card* comes in $10–$100 options, perfect for gifting! Available now: [https://acme-7cu19ngr.myshopify.com/products/gift-card].  

---

#### Summary: Why This Design Excels for a Sales Bot

- **Lean Output**: Excludes `gid`, `handle`, untracked inventory, and empty structures for a compact dataset.
- **Sales-Optimized**: Includes URLs for products and collections, enabling Messenger preview cards.
- **Customer-Focused**: Filters unavailable items, adds fallback descriptions, omits irrelevant inventory details for untracked items.
- **Flexible**: Supports percentage and fixed-amount discounts, includes collections for recommendations.
- **Robust**: Handles edge cases (e.g., missing inventory, invalid metafield JSON).
- **Bot-Ready**: Structured for seamless integration with a GPT sales bot, aligned with the raw data from Chapter 3.

**Key Features**:
- **Preprocessing**: Flattens GraphQL structure, normalizes fields, adds URLs.
- **Exclusions**: Removes `gid`, `handle`, unavailable variants, draft/archived products.
- **Inventory**: Includes `inventory_quantity` only for tracked variants (e.g., snowboards), omits for untracked (e.g., gift cards), no `inventory_tracked`.
- **Fallbacks**: Generates descriptions for empty fields.
- **Output**: Matches your sample JSON, with products, discounts, and collections tailored for sales.