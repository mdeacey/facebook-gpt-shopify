You’re suggesting a simplified scope for the Shopify OAuth flow in Chapter 3:

```
read_product_listings,read_inventory,read_discounts,read_locations,read_products
```

This scope is a subset of the previously provided one, removing `read_price_rules`, `read_content`, `read_marketing_events`, `read_shipping`, `read_gift_cards`, and `read_publications`. Your question implies you want to confirm if this reduced scope, combined with the current Chapter 3 implementation (focused on OAuth and raw GraphQL data fetching without preprocessing), is sufficient for the GPT sales bot’s needs. You’ve also emphasized that Chapter 3 should not include preprocessing (handled in Chapter 5), and preprocessing requirements include:
- Excluding `gid` (internal IDs).
- Omitting `handle` (redundant with `url`).
- Including `inventory_quantity` only for tracked variants (`inventoryLevels.edges` exists and `quantity > 0`), omitting it for untracked variants (no `inventoryLevels.edges` or `quantity: 0` but `availableForSale: true`), and removing `inventory_tracked`.

I’ll evaluate whether the proposed scope is sufficient for the sales bot, update **Chapter 3** to use this scope while maintaining the structure and intent of the previous Chapter 3 (mirroring Chapter 5’s structure but without preprocessing), and confirm if this setup meets all requirements. Since Chapter 5 handles preprocessing, I’ll briefly outline its necessary updates to ensure alignment but focus on Chapter 3 here.

---

### Evaluating the Proposed Scope

The proposed scope (`read_product_listings,read_inventory,read_discounts,read_locations,read_products`) covers:
- **read_product_listings**: Access to published product listings, excluding drafts.
- **read_inventory**: Stock availability for tracked products (e.g., `inventory_quantity` for snowboards).
- **read_discounts**: Discount codes (e.g., “CODE_DISCOUNT_BLACKFRIDAY”).
- **read_locations**: Location-specific inventory details (e.g., “Shop location”).
- **read_products**: Detailed product data, including variants, metafields, and collections.

**Sufficiency for the Sales Bot**:
- **Core Needs**: The bot promotes products, shares discounts, and provides URLs for Messenger preview cards. The scope supports:
  - Fetching product details (`title`, `description`, `productType`, `vendor`, `tags`, `variants`, `metafields`) via `read_products` and `read_product_listings`.
  - Accessing inventory (`inventory_quantity`, `location`) via `read_inventory` and `read_locations`.
  - Sharing discounts (`code`, `percentage`, `starts_at`, `ends_at`) via `read_discounts`.
  - Constructing URLs using `handle` and shop URL (handled in Chapter 5 preprocessing).
- **Collections**: Supported by `read_products`, as collections are tied to product data.
- **Inventory Handling**: Chapter 5 preprocessing will include `inventory_quantity` only for tracked variants and omit it for untracked ones (e.g., gift cards), aligning with your sample JSON (e.g., gift cards with `inventory_quantity: 0` but `available: true`).
- **Removed Scopes**:
  - `read_price_rules`: Not used in the GraphQL query (which uses `codeDiscountNodes`), so its removal has no impact.
  - `read_content`, `read_marketing_events`, `read_shipping`, `read_gift_cards`, `read_publications`: Not queried, so their removal streamlines authorization without affecting the bot’s core functionality (product promotion, discounts).
- **Gaps**: The scope excludes data like marketing events, shipping rates, or gift card details, which could enhance the bot (e.g., promoting campaigns or gift cards). However, your sample JSON focuses on products and discounts, and the bot’s primary role (per interactions) is product/discount promotion, so the reduced scope is likely sufficient.

**Conclusion**: The proposed scope is sufficient for the sales bot’s core needs (promoting products, sharing discounts, providing URLs), especially since Chapter 5 preprocessing tailors the output (e.g., removing `gid`, `handle`, optimizing inventory). If future features require marketing events, shipping, or gift cards, the scope can be expanded.

---

### Updated Chapter 3: Implementing Shopify OAuth with FastAPI for a Sales Bot

In this chapter, we implement a Shopify OAuth flow in your FastAPI application to authenticate with Shopify and fetch raw data for a GPT Messenger sales bot. Using Shopify’s GraphQL Admin API, the flow retrieves shop details, products, discount codes, and collections in a single, optimized API call, supporting the bot in promoting products, sharing promotions, and answering customer inquiries. The raw GraphQL data is later preprocessed (in Chapter 5) to produce a lean, sales-oriented JSON format with product URLs for Messenger preview cards, excluding internal IDs (e.g., `gid`) and redundant fields like `handle`. The project includes a Facebook OAuth setup (from Chapter 2), which remains unchanged. We focus solely on the Shopify OAuth implementation, explaining each component, its purpose, and why this approach aligns with professional Python development practices for a sales bot.

---

#### Step 1: Understand the Need for Shopify OAuth

The sales bot requires Shopify data to promote products, share discounts, and provide URLs for Messenger preview cards. Shopify’s OAuth flow authenticates the application, granting access to the GraphQL Admin API. The raw data fetched includes shop details, products (with variants, inventory, and metafields), discount codes, and collections, which are preprocessed in Chapter 5 to exclude unnecessary fields (e.g., IDs, `handle`), optimize inventory (e.g., omitting untracked stock), and ensure a customer-friendly format. A single GraphQL call minimizes API usage, and the scope is tailored to the bot’s needs, ensuring efficiency and security.

**Why OAuth?** OAuth securely authenticates the app, providing an access token to fetch data without exposing sensitive credentials. The raw GraphQL response provides a flexible foundation for preprocessing, enabling the bot to deliver tailored responses.

---

#### Step 2: Review the Project Structure

The project structure includes a `facebook_oauth` package from Chapter 2. We add a `shopify_oauth` package to handle Shopify OAuth logic. The structure is:

```
└── ./
    ├── docs
    │   ├── DAY-ONE.md
    │   ├── DAY-TWO.md
    │   └── DAY-THREE.md
    ├── facebook_oauth
    │   ├── __init__.py
    │   ├── routes.py
    │   └── utils.py
    ├── shopify_oauth
    │   ├── __init__.py
    │   ├── routes.py
    │   └── utils.py
    ├── .env.example
    ├── .gitignore
    ├── app.py
    ├── LICENSE
    └── requirements.txt
```

- **facebook_oauth/**: Handles Facebook OAuth for Messenger bot authentication (unchanged).
- **shopify_oauth/**: Handles Shopify OAuth, including routes, token exchange, and raw data fetching.
- **app.py**: Includes the Shopify OAuth router alongside the Facebook OAuth router.
- **.env.example**: Documents Shopify-specific environment variables.
- **requirements.txt**: Unchanged, as existing dependencies support Shopify OAuth.

**Why this structure?**  
The modular design isolates Shopify OAuth logic, ensuring maintainability and scalability. The `shopify_oauth` package is reusable for future Shopify features.

---

#### Step 3: Update app.py — Add the Shopify OAuth Router

The FastAPI application in `app.py` includes the Shopify OAuth router with a `/shopify` prefix, alongside the Facebook OAuth router. The root endpoint guides users to both OAuth flows:

```python
from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from shopify_oauth.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")
app.include_router(shopify_oauth_router, prefix="/shopify")

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Use /facebook/login for Facebook OAuth or /shopify/{shop_name}/login for Shopify OAuth"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

**What’s included?**
- Shopify OAuth router with `/shopify` prefix.
- Root endpoint directing to `/facebook/login` and `/shopify/{shop_name}/login`.

**Why this design?**  
- Supports both OAuth flows with clear entry points.
- Retains CORS middleware and environment variable loading for security and frontend compatibility.

---

#### Step 4: Implement shopify_oauth/routes.py — Handle Shopify OAuth

The Shopify OAuth routes in `shopify_oauth/routes.py` handle authentication and fetch raw GraphQL data. The callback endpoint returns `token_data` and the raw `shopify_data` response, deferring preprocessing to Chapter 5.

```python
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data

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

    # Fetch Shopify data
    shopify_data = await get_shopify_data(token_data["access_token"], shop)

    return JSONResponse(content={
        "token_data": token_data,
        "shopify_data": shopify_data.get("data", {})
    })
```

**Route Details**:
- **/{shop_name}/login**: Initiates Shopify OAuth by redirecting to the shop’s authorization URL, ensuring `shop_name` includes `.myshopify.com`. The scope is set to `read_product_listings,read_inventory,read_discounts,read_locations,read_products`, supporting:
  - `read_product_listings`: Published product listings, excluding drafts.
  - `read_inventory`: Stock availability for tracked products (e.g., snowboards).
  - `read_discounts`: Discount codes (e.g., “CODE_DISCOUNT_BLACKFRIDAY”).
  - `read_locations`: Location-specific inventory details (e.g., “Shop location”).
  - `read_products`: Detailed product data, including variants, metafields, and collections.
- **/callback**: Exchanges the authorization code for an access token, fetches raw Shopify data via a GraphQL call using `get_shopify_data`, and returns `token_data` (access token and scopes) and `shopify_data` (raw GraphQL response). The `shopify_data` includes nested structures for `shop`, `products`, `codeDiscountNodes`, and `collections`, with pagination fields (`pageInfo.hasNextPage`, `endCursor`). Preprocessing (e.g., removing `gid`, `handle`, and handling inventory) is deferred to Chapter 5.

**Why this design?**
- **Efficient Data Retrieval**: A single GraphQL call fetches shop, products, discounts, and collections, minimizing API requests and latency.
- **Raw Response**: Returning `shopify_data` preserves the GraphQL structure (e.g., `products.edges[].node`), allowing Chapter 5 to preprocess it (e.g., remove IDs, `handle`, and optimize inventory).
- **Stateless**: Uses `shop_name` from the URL and query parameters, with no server-side storage.
- **RESTful**: The `/{shop_name}/login` path aligns with REST conventions.
- **Client Flexibility**: Includes pagination fields for future extensibility.

---

#### Step 5: Implement shopify_oauth/utils.py — Shopify Helper Functions

The helper functions in `shopify_oauth/utils.py` handle token exchange and raw data fetching via a GraphQL query optimized for the sales bot.

```python
import os
import httpx
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
```

**What’s included?**
- `exchange_code_for_token`: Exchanges the authorization code for an access token.
- `get_shopify_data`: Uses Shopify’s GraphQL API (version `2025-04`) to fetch shop info, products (with variants, inventory, and metafields), discount codes, and collections in a single call. The query is optimized to include only sales-relevant data, supporting the scope `read_product_listings,read_inventory,read_discounts,read_locations,read_products`.

**Why this query?**
- **Sales-Relevant Data**: Fetches shop details, products (including inventory, metafields, and `handle` for URL construction), discounts, and collections, aligning with the bot’s needs.
- **Scope Alignment**: Supports `read_products`, `read_product_listings`, `read_inventory`, `read_discounts`, and `read_locations` (for variant locations).
- **Inventory Support**: Includes `inventoryLevels` for stock data, with Chapter 5 preprocessing to include `inventory_quantity` only for tracked variants.
- **Discount Flexibility**: Supports percentage and fixed-amount discounts via `codeDiscountNodes`.
- **Collections**: Enables grouped recommendations (e.g., “Premium Snowboards”).
- **Pagination**: Includes `pageInfo` for future extensibility.
- **Efficiency**: Single call minimizes API usage, with retry logic for rate limits (429 errors).

---

#### Step 6: Update Environment Variables — .env.example

The `.env.example` file includes variables for both OAuth flows, with Shopify variables added:

```
# Facebook OAuth credentials (from Chapter 2)
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback

# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
```

**Why these variables?**  
- Authenticate with Shopify’s OAuth system.
- `SHOPIFY_REDIRECT_URI` specifies the callback URL (`/shopify/callback`).
- Stored in `.env` for security, with `.env.example` as a template.

---

#### Step 7: Reuse Existing Dependencies — requirements.txt

The `requirements.txt` file remains unchanged:

```
fastapi
uvicorn
python-dotenv
httpx
```

**Why no changes?**  
- **fastapi**: Powers endpoints and routing.
- **uvicorn**: Runs the ASGI server.
- **python-dotenv**: Manages environment variables.
- **httpx**: Handles async HTTP requests.

---

#### Step 8: .gitignore and LICENSE

No changes are needed for `.gitignore` or `LICENSE`, as they cover sensitive files and the MIT License.

---

#### Step 9: Testing the Shopify OAuth Flow

To test the Shopify OAuth flow:

1. **Set Up Environment Variables:**
   - Ensure Facebook OAuth credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`) are in `.env` (from Chapter 2).
   - Add Shopify OAuth credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`) to `.env`, obtained from your Shopify app.

2. **Run the FastAPI App:**
   - Start the app with `uvicorn app:app --host 0.0.0.0 --port 5000 --reload`.

3. **Test Shopify OAuth:**
   - Visit `http://localhost:5000/shopify/acme-7cu19ngr/login` (or your shop name).
   - Complete the Shopify OAuth flow, which redirects to `/shopify/callback`.
   - Verify the response contains `token_data` and `shopify_data`. The `shopify_data` field includes nested GraphQL data for `shop`, `products`, `codeDiscountNodes`, and `collections`. Confirm the response includes product details (e.g., title, variants, inventory, `handle`), discounts (e.g., “CODE_DISCOUNT_BLACKFRIDAY”), and collections, with pagination fields (`pageInfo`). The data retains raw fields (e.g., `handle`, IDs), which are processed in Chapter 5 to exclude `gid`, `handle`, and optimize inventory.

4. **Reinstall Shopify App if Needed:**
   - If the Shopify app was installed with different scopes, uninstall it via the Shopify admin (`Apps` section), then re-run the OAuth flow to apply the scope: `read_product_listings,read_inventory,read_discounts,read_locations,read_products`.

**Why test this way?**  
- Ensures the OAuth flow fetches raw GraphQL data (shop, products, discounts, collections) in a single call, providing a foundation for preprocessing in Chapter 5.
- Validates the response structure (`token_data`, `shopify_data`) and scope.
- Confirms the query aligns with the sales bot’s needs, with preprocessing handling inventory, IDs, and `handle` removal.

---

#### Summary: Why This Design Excels for a Sales Bot

- **Separation of Concerns**: Isolates Shopify OAuth logic in the `shopify_oauth` package, independent of Facebook OAuth.
- **Stateless**: Relies on URL and query parameters, with no server-side storage.
- **Security**: Uses environment variables and error handling to prevent leaks.
- **Scalability**: Async `httpx` requests ensure non-blocking I/O.
- **RESTful**: Hierarchical URLs (`/shopify/{shop_name}/login`) align with conventions.
- **Efficient Data Retrieval**: Single GraphQL call fetches shop, products, discounts, and collections, minimizing API usage.
- **Raw Response**: Preserves GraphQL structure for flexibility, with Chapter 5 handling preprocessing (e.g., removing `gid`, `handle`, and optimizing inventory).
- **Tailored Scope**: Uses `read_product_listings,read_inventory,read_discounts,read_locations,read_products`, sufficient for product promotion and discounts.
- **Bot Foundation**: Provides raw data for the sales bot, processed in Chapter 5 to meet requirements (e.g., URLs for Messenger, lean output).

**Key Updates from Original**:
- **Scope**: Updated to `read_product_listings,read_inventory,read_discounts,read_locations,read_products`, as specified.
- **GraphQL Query**: Slimmed down to sales-relevant fields (shop, products, discounts, collections), with `status` for filtering drafts/archived products.
- **No Preprocessing**: Returns raw `shopify_data`, excluding `preprocess_shopify_data` from `/shopify/callback`.
- **Narrative**: Structured like Chapter 5, focusing on OAuth and raw data fetching, deferring preprocessing to Chapter 5.
- **Alignment**: Ensures compatibility with your sample JSON data, with Chapter 5 handling `gid`, `handle`, and inventory logic.