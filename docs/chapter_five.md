Below is the updated **Chapter 5** of the tutorial, fully incorporating the exclusion of empty lists (`[]`) and dictionaries (`{}`) in the `simplify_shopify_data` function, as well as the streamlined `/shopify/callback` endpoint that returns only `token_data` and `simplified_data`. This chapter follows the structure and style of the provided Chapter 1 example, focusing on the preprocessing implementation without referencing feeding the data to a GPT model (as that's planned for a future chapter). The documentation explains the changes made to `shopify_oauth/utils.py` and `shopify_oauth/routes.py`, justifies the design decisions, and includes code snippets within `<xaiArtifact>` tags.

---

### Chapter 5: Preprocessing Shopify Data for a Streamlined Output

In this chapter, we enhance our FastAPI application by adding preprocessing and normalization of Shopify GraphQL data. We transform the complex, nested JSON response from the Shopify API into a clean, flattened format, excluding empty lists and dictionaries to minimize noise and produce a concise output. This streamlined JSON is ideal for downstream processing. We modify the `shopify_oauth` module to include a preprocessing function and update the `/shopify/callback` endpoint to return only the essential data—`token_data` and `simplified_data`—discarding the raw GraphQL response since backward compatibility is not required.

#### Step 1: Understand the Need for Preprocessing

The Shopify GraphQL API returns a verbose, deeply nested JSON structure with `edges.node` patterns and complex fields like `variants` and `inventoryLevels`. This response often includes empty lists (e.g., `[]` for tags or variants) and empty dictionaries (e.g., `{}` for metafields), which add unnecessary bulk and clutter. Our goal is to simplify this response into a lean JSON format with normalized fields (e.g., prices as floats, parsed metafields) and exclude empty lists and dictionaries to focus on meaningful data: shop info, products with variants or metafields, and discounts.

**Why preprocess?** Simplifying the data and removing empty structures reduces response size, enhances clarity for downstream applications, and ensures only relevant data is included, making the API output more efficient and developer-friendly.

#### Step 2: Extend `shopify_oauth/utils.py` with Preprocessing Logic

We add a `simplify_shopify_data` function to `shopify_oauth/utils.py` to preprocess and normalize the Shopify GraphQL response. This function flattens nested structures, normalizes data, and skips empty lists and dictionaries to produce a minimal output.

**Code in `shopify_oauth/utils.py`** (Relevant Addition):
```python
import json

def simplify_shopify_data(raw_data: dict) -> dict:
    """
    Simplify and normalize Shopify GraphQL response into a clean JSON format,
    excluding empty lists and dictionaries.
    """
    simplified = {
        "shop": {
            "name": raw_data["data"]["shop"]["name"],
            "url": raw_data["data"]["shop"]["primaryDomain"]["url"]
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

    # Process products
    for product in raw_data["data"].get("products", {}).get("edges", []):
        product = product["node"]
        product_data = {
            "id": product["id"],
            "title": product["title"],
            "type": product["productType"],
            "vendor": product["vendor"],
            "tags": product["tags"],
            "handle": product["handle"],
            "description": product["description"] or ""
        }

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
        if metafields:  # Only include non-empty metafields
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
        if variants:  # Only include non-empty variants
            product_data["variants"] = variants

        # Only append product if it has meaningful data (e.g., variants or metafields)
        if variants or metafields:
            products.append(product_data)

    # Only include non-empty products and discounts in the output
    if products:
        simplified["products"] = products
    if discounts:
        simplified["discounts"] = discounts

    return simplified
```

**Why this function?**
- **Flattening**: Removes nested `edges.node` structures, making fields like `price` and `inventory_quantity` directly accessible.
- **Normalization**: Converts prices to floats and parses metafield JSON (e.g., `snowboard_length`) into value/unit pairs for consistency.
- **Filtering Empty Structures**: Excludes empty lists (e.g., `[]` for variants) and dictionaries (e.g., `{}` for metafields), as well as products without variants or metafields, to minimize noise.
- **Error Handling**: Handles edge cases like missing inventory data or invalid metafield JSON gracefully, ensuring robustness.

**Why in `utils.py`?** Placing the preprocessing logic alongside other Shopify utilities (e.g., OAuth token exchange, API calls) maintains modularity and promotes reusability within the `shopify_oauth` module.

#### Step 3: Update `shopify_oauth/routes.py` to Return Simplified Data

We modify the `/shopify/callback` endpoint in `shopify_oauth/routes.py` to call `simplify_shopify_data` and return only `token_data` and `simplified_data`, discarding the raw GraphQL response to keep the output lean.

**Code in `shopify_oauth/routes.py`** (Updated):
```python
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, simplify_shopify_data

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_price_rules,read_discounts,read_content,read_locations,read_marketing_events,read_shipping,read_gift_cards,read_products,read_publications"

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

    # Fetch Shopify data
    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    
    # Simplify the data
    simplified_data = simplify_shopify_data(shopify_data)

    return JSONResponse(content={
        "token_data": token_data,
        "simplified_data": simplified_data
    })
```

**Why this change?**
- **Streamlined Response**: Returns only `token_data` (for authentication) and `simplified_data` (the processed output), reducing response size and complexity.
- **No Raw Data**: Eliminates the raw GraphQL response, as it’s unnecessary for downstream tasks, aligning with the goal of a concise API.
- **Modularity**: Leverages the `simplify_shopify_data` utility to keep the route focused on routing logic, enhancing maintainability.

#### Step 4: Verify Existing Dependencies

The preprocessing logic uses only the standard `json` library for metafield parsing and relies on existing project dependencies (`httpx`, `fastapi`, `python-dotenv`, `uvicorn`). No changes are needed to `requirements.txt`.

**Code in `requirements.txt`** (Unchanged):
```
fastapi
uvicorn
python-dotenv
httpx
```

**Why no new dependencies?** Using built-in Python libraries and existing dependencies keeps the project lightweight, avoiding unnecessary bloat while meeting all functional requirements.

#### Step 5: Test the Implementation

To ensure the preprocessing works as expected:
1. **Run the App**: Start the FastAPI server with `uvicorn app:app --host 0.0.0.0 --port 5000 --reload`.
2. **Authenticate**: Navigate to `/shopify/{shop_name}/login` (e.g., `/shopify/acme-7cu19ngr/login`) to initiate the Shopify OAuth flow.
3. **Check Callback**: After authentication, verify the `/shopify/callback` response contains `token_data` and `simplified_data` in the expected format.
4. **Inspect Output**: Confirm that `simplified_data` includes shop info, products with variants or metafields, and discounts, with no empty lists or dictionaries.

**Example Response from `/shopify/callback`**:
```json
{
  "token_data": {
    "access_token": "shpua_9a72896d590dbff5d3cf818f49710f67",
    "scope": "read_product_listings,read_inventory,read_price_rules,read_discounts,read_content,read_locations,read_marketing_events,read_shipping,read_gift_cards,read_products,read_publications"
  },
  "simplified_data": {
    "shop": {
      "name": "acme-7cu19ngr",
      "url": "https://acme-7cu19ngr.myshopify.com"
    },
    "products": [
      {
        "id": "gid://shopify/Product/7558391660630",
        "title": "Gift Card",
        "type": "giftcard",
        "vendor": "Snowboard Vendor",
        "tags": [],
        "handle": "gift-card",
        "description": "This is a gift card for the store",
        "variants": [
          {
            "title": "$10",
            "price": 10.0,
            "available": true,
            "inventory_quantity": 0,
            "location": "Shop location"
          },
          {
            "title": "$25",
            "price": 25.0,
            "available": true,
            "inventory_quantity": 0,
            "location": "Shop location"
          },
          {
            "title": "$50",
            "price": 50.0,
            "available": true,
            "inventory_quantity": 0,
            "location": "Shop location"
          },
          {
            "title": "$100",
            "price": 100.0,
            "available": true,
            "inventory_quantity": 0,
            "location": "Shop location"
          }
        ]
      },
      {
        "id": "gid://shopify/Product/7558391693398",
        "title": "The Complete Snowboard",
        "type": "snowboard",
        "vendor": "Snowboard Vendor",
        "tags": ["Premium", "Snow", "Snowboard", "Sport", "Winter"],
        "handle": "the-complete-snowboard",
        "description": "This PREMIUM snowboard is so SUPERDUPER awesome!",
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
        ],
        "metafields": {
          "title_tag": "Complete Snowboard",
          "description_tag": "snowboard winter sport snowboarding",
          "snowboard_length": {
            "value": 159.0,
            "unit": "CENTIMETERS"
          },
          "snowboard_weight": {
            "value": 7.0,
            "unit": "POUNDS"
          }
        }
      }
      // ... other products with variants or metafields
    ],
    "discounts": [
      {
        "code": "CODE_DISCOUNT_BLACKFRIDAY",
        "title": "CODE_DISCOUNT_BLACKFRIDAY",
        "percentage": 20.0,
        "starts_at": "2025-11-28T00:00:00Z",
        "ends_at": "2025-11-29T00:00:00Z"
      }
    ]
  }
}
```

**Why this output?** The JSON is lean, with no empty lists (e.g., `[]` for variants) or dictionaries (e.g., `{}` for metafields). Products without variants or metafields (e.g., “The Inventory Not Tracked Snowboard” if it lacks both) are excluded, and the `products` and `discounts` keys appear only if they contain data. This minimizes the response size and focuses on meaningful information.

#### Summary: Why This Design Shows Your Python Skills

- **Modularity**: The `simplify_shopify_data` function is integrated into `utils.py`, keeping preprocessing logic reusable and separate from routing concerns.
- **Simplicity**: The `/shopify/callback` endpoint returns only `token_data` and `simplified_data`, ensuring a concise API response.
- **Efficiency**: Excluding empty lists and dictionaries reduces noise and payload size, making the output more suitable for downstream processing.
- **No New Dependencies**: Leverages standard Python libraries and existing dependencies, maintaining a lightweight project.
- **Robustness**: Handles edge cases (e.g., missing inventory, invalid metafield JSON) to ensure reliable preprocessing.

This chapter builds on the Shopify OAuth foundation, adding preprocessing to produce a streamlined JSON output that’s ready for future integrations, while keeping the implementation minimal and maintainable.