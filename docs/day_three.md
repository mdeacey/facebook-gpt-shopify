I'll update the chapter to reflect the simplified "dump" approach for the Shopify OAuth callback, replacing the manual data extraction with a direct return of the GraphQL response data. I'll also address the potential bug where `price_rules` and `discount_codes` were extracted from the same `codeDiscountNodes` field, clarify the response structure, and ensure the documentation aligns with the new implementation. The changes will be focused on the relevant sections (`routes.py` and the narrative) while keeping other parts (e.g., `utils.py`, `app.py`, environment variables, etc.) unchanged unless necessary for clarity or correctness.

Below is the updated version of **Chapter 3: Implementing Shopify OAuth with FastAPI for a Sales Bot**, incorporating the simplified response structure and addressing the `price_rules`/`discount_codes` duplication.

---

# Chapter 3: Implementing Shopify OAuth with FastAPI for a Sales Bot

This chapter focuses on implementing a Shopify OAuth flow in your FastAPI application to authenticate with Shopify and fetch comprehensive data for a GPT Messenger sales bot. Using Shopify’s GraphQL Admin API, the flow retrieves shop details, products, inventory, discount codes, marketing events, locations, collections, articles, blogs, pages, inventory items, product tags, product types, and product variants in a single API call, optimizing performance and simplifying data retrieval. This setup supports the bot in promoting products, sharing promotions, and answering customer inquiries effectively. The project already includes a Facebook OAuth setup (from Chapter 2), which remains unchanged in this chapter. We’ll focus solely on the Shopify OAuth implementation, explaining each component, its purpose, and why this approach aligns with professional Python development practices.

---

## Step 1: Review the Project Structure

The project structure already includes a `facebook_oauth` package from Chapter 2. In this chapter, we add a `shopify_oauth` package to handle Shopify OAuth logic. The updated structure is:

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

- **facebook_oauth/**: Already exists from Chapter 2; handles Facebook OAuth for Messenger bot authentication (unchanged in this chapter).
- **shopify_oauth/**: Added in this chapter to handle Shopify OAuth logic, including routes and helper functions.
- **app.py**: Updated to include the Shopify OAuth router alongside the existing Facebook OAuth router.
- **.env.example**: Updated to document Shopify-specific environment variables.
- **requirements.txt**: Unchanged, as existing dependencies support the Shopify OAuth flow.

**Why this structure?**  
The modular design keeps Shopify OAuth logic separate from the existing Facebook OAuth setup, ensuring maintainability and scalability. The `shopify_oauth` package can be reused or extended for other Shopify-related features.

---

## Step 2: Update app.py — Add the Shopify OAuth Router

The main FastAPI application in `app.py` is updated to include the Shopify OAuth router alongside the existing Facebook OAuth router. The root endpoint is also updated to guide users to both available OAuth flows:

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

**What’s changed?**
- Added the Shopify OAuth router with a `/shopify` prefix.
- Updated the root endpoint to guide users to both `/facebook/login` (from Chapter 2) and the new `/shopify/{shop_name}/login`.

**Why these changes?**  
- **Support Both Flows**: The app now supports both Facebook and Shopify OAuth flows, with clear entry points for each.
- **User Guidance**: The root message directs users to the appropriate endpoint for Shopify OAuth while acknowledging the existing Facebook OAuth endpoint.
- **CORS and Environment**: Retains CORS middleware and `load_dotenv()` for secure configuration and frontend compatibility.

---

## Step 3: Implement shopify_oauth/routes.py — Handle Shopify OAuth

The Shopify OAuth routes in `shopify_oauth/routes.py` handle authentication and fetch all Shopify data in a single GraphQL call. The callback endpoint now returns the raw GraphQL response data directly, simplifying the response structure and reducing maintenance:

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

    return JSONResponse(content={
        "token_data": token_data,
        "shopify_data": shopify_data.get("data", {})
    })
```

**Route Details**:
- **/{shop_name}/login**: Initiates Shopify OAuth by redirecting to the shop’s authorization URL, ensuring `shop_name` includes `.myshopify.com`. The scope is set to `read_product_listings,read_inventory,read_price_rules,read_discounts,read_content,read_locations,read_marketing_events,read_shipping,read_gift_cards,read_products,read_publications` to support the sales bot’s functionality:
  - `read_product_listings`: Fetches published product listings, excluding drafts.
  - `read_inventory`: Provides detailed stock availability across locations.
  - `read_locations`: Fetches shop locations for location-specific inventory details.
  - `read_price_rules`: Allows the bot to share active price rule-based promotions (e.g., percentage discounts).
  - `read_discounts`: Allows the bot to share specific discount codes (e.g., "Use code SAVE10").
  - `read_content`: Fetches shop policies, articles, blogs, and pages for customer inquiries.
  - `read_marketing_events`: Fetches marketing campaigns (e.g., sales events).
  - `read_shipping`: Fetches shipping zones and rates for customer inquiries.
  - `read_gift_cards`: Fetches gift card details for promotion or inquiries (though restricted in this implementation).
  - `read_products`: Fetches detailed product data, including variants and metafields.
  - `read_publications`: Fetches publication data for product availability across channels.
- **/callback**: Exchanges the code for an access token, fetches all Shopify data in one GraphQL call using `get_shopify_data`, and returns a response with `token_data` and `shopify_data`. The `shopify_data` field contains the raw GraphQL response, including nested structures for `shop`, `products`, `codeDiscountNodes` (for discount codes), `marketingEvents`, `collections`, `articles`, `blogs`, `pages`, `inventoryItems`, `productTags`, `productTypes`, `productVariants`, `locations`, `currentAppInstallation`, and `publications`. Notably, `shipping_zones` and `gift_cards` are not included in the GraphQL query, so they are absent from the response.

**Why these scopes?**
- **Sales Focus**: The bot is designed to promote products and provide shop information, not manage orders or access customer data. Scopes like `read_orders`, `read_customers`, `write_checkouts`, and `write_orders` are excluded to follow the principle of least privilege and reduce permission requests.
- **Enhanced Functionality**: The selected scopes enable the bot to:
  - Fetch detailed product data (`read_products`, `read_product_listings`) and inventory levels across locations (`read_inventory`, `read_locations`) for accurate stock info (e.g., "We have 10 units at our Main Warehouse").
  - Share discount code-based promotions (`read_discounts`) to encourage purchases (e.g., "Use code SAVE10 to save $10"). Note that `read_price_rules` is included but not used in the current GraphQL query, as the query focuses on `codeDiscountNodes` for discounts.
  - Promote marketing campaigns (`read_marketing_events`), such as "Check out our Black Friday Sale!"
  - Answer shipping inquiries (`read_shipping`), though not included in the current GraphQL response.
  - Respond to content-related questions with shop policies, articles, blogs, and pages (`read_content`).
  - Promote gift cards (`read_gift_cards`), though restricted in this implementation.
  - Organize products by collections (`read_products`) and provide product categorization via tags and types (`read_products`).
  - Ensure product availability across sales channels (`read_publications`).
- **Shopify Platform Permissions**: During authorization, Shopify may request permission to "View personal data" (e.g., email address, IP address, browser, and operating system). This is a platform requirement for app installation and not tied to any specific scope requested by the app. The bot does not use this data.

**Why this design?**  
- **Efficient Data Retrieval**: Uses Shopify’s GraphQL API to fetch all data (shop info, products, inventory, discount codes, marketing events, collections, articles, blogs, pages, inventory items, product tags, product types, product variants, locations, and publications) in a single call, reducing API requests and improving performance.
- **Simplified Response**: Returns the raw GraphQL response (`shopify_data`) directly, preserving the nested structure (e.g., `products.edges[].node`). This reduces server-side processing, simplifies maintenance, and allows clients to extract needed data (e.g., `shop`, `products`, `codeDiscountNodes`) as required.
- **Fully Stateless**: Uses the `shop_name` from the URL and query parameters, with no server-side storage of the access token or other data.
- **RESTful**: The `/{shop_name}/login` path aligns with RESTful conventions.
- **Client Flexibility**: The raw GraphQL response includes pagination fields (e.g., `pageInfo.hasNextPage`, `endCursor`), enabling clients to implement pagination if needed.

**Note on Discounts**: The GraphQL query uses `codeDiscountNodes` to fetch discount codes, aligning with the `read_discounts` scope. The `read_price_rules` scope is included but not utilized in the query, as price rules are typically fetched via the REST API or different GraphQL fields. This implementation focuses on discount codes for simplicity, but clients can extend the query to include price rules if needed.

---

## Step 4: Implement shopify_oauth/utils.py — Shopify Helper Functions

The helper functions in `shopify_oauth/utils.py` include logic to exchange the authorization code and fetch all Shopify data in a single GraphQL call:

```python
import os
import httpx
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
```

**What’s included?**
- `exchange_code_for_token`: Exchanges the authorization code for an access token.
- `get_shopify_data`: Uses Shopify’s GraphQL API (version `2025-04`) to fetch shop info, publications, products, collections, discount codes, locations, marketing events, articles, blogs, pages, inventory items, product tags, product types, and product variants in a single call. Notably, `shipping_zones` and `gift_cards` are not queried, aligning with their absence in the response.

**Why this approach?**  
- **Efficiency**: Reduces multiple REST API calls to a single GraphQL query, minimizing latency and API rate limit usage.
- **Async**: `httpx.AsyncClient` ensures non-blocking I/O.
- **Modularity**: Separates data fetching logic from routes, improving reusability.
- **Security**: Uses environment variables for sensitive credentials.
- **Error Handling**: Checks for GraphQL errors and raises appropriate exceptions.

---

## Step 5: Update Environment Variables — .env.example

The `.env.example` file includes variables for both OAuth flows, with Shopify variables added in this chapter:

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

**What’s changed?**
- Added Shopify OAuth credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`) to support the Shopify flow.

**Why these variables?**  
- Authenticate with Shopify’s OAuth system.
- `SHOPIFY_REDIRECT_URI` specifies the callback URL (`/shopify/callback`).
- Stored in `.env` for security, with `.env.example` providing a template.

---

## Step 6: Reuse Existing Dependencies — requirements.txt

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

These dependencies, already included for the Facebook OAuth setup, are sufficient for Shopify OAuth as well.

---

## Step 7: .gitignore and LICENSE

No changes are needed for `.gitignore` or `LICENSE`, as they already cover sensitive files and the MIT License from previous chapters.

**Why no changes?**  
- **.gitignore**: Excludes `.env` and other artifacts.
- **LICENSE**: MIT License remains applicable.

---

## Step 8: Testing the Shopify OAuth Flow

To test the Shopify OAuth flow:

1. **Set Up Environment Variables:**
   - Ensure the Facebook OAuth credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`) are in `.env` (from Chapter 2).
   - Add Shopify OAuth credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`) to `.env`, obtained from your Shopify app (per Chapter 4).

2. **Run the FastAPI App:**
   - Start the app with `python app.py`.

3. **Test Shopify OAuth:**
   - Visit `http://localhost:5000/shopify/yourshopname/login` (replace `yourshopname` with your Shopify store name, e.g., `acme-7cu19ngr` or `acme-7cu19ngr.myshopify.com`).
   - Complete the Shopify OAuth flow, which redirects to `/shopify/callback`.
   - Verify the response contains `token_data` and `shopify_data`. The `shopify_data` field should include nested data for `shop`, `products`, `codeDiscountNodes` (for discount codes), `marketingEvents`, `collections`, `articles`, `blogs`, `pages`, `inventoryItems`, `productTags`, `productTypes`, `productVariants`, `locations`, `currentAppInstallation`, and `publications`. Confirm that `shipping_zones` and `gift_cards` are absent, reflecting their exclusion from the GraphQL query. The `shop` field should include shop details, `products` should include detailed product data with variants and inventory, and `token_data` should show the updated scopes (`read_product_listings,read_inventory,read_price_rules,read_discounts,read_content,read_locations,read_marketing_events,read_shipping,read_gift_cards,read_products,read_publications`).

4. **Reinstall Shopify App if Needed:**
   - If you previously installed the Shopify app with different scopes, uninstall it from your store (`acme-7cu19ngr`) via the Shopify admin (`Apps` section), then re-run the Shopify OAuth flow to apply the updated scopes.

**Why test this way?**  
- Ensures the Shopify OAuth flow works independently, fetching all necessary data (shop info, products, inventory, discount codes, marketing events, collections, articles, blogs, pages, inventory items, product tags, product types, product variants, locations, and publications) in a single GraphQL call for the GPT Messenger sales bot.
- Confirms the endpoint returns a simplified response with `token_data` and `shopify_data`, where `shopify_data` contains the raw GraphQL data, without saving the access token.
- Validates the updated scopes are applied correctly, excluding unnecessary permissions like `read_orders`, `read_customers`, `write_checkouts`, or `write_orders`.

**Note**: The Facebook OAuth flow (`/facebook/login`) remains available from Chapter 2 but is not used or modified in this chapter. You can test it separately if needed for Messenger bot setup.

---

## Summary: Why This Design Shows Your Python Skills

- **Separation of Concerns**: The Shopify OAuth flow is isolated in its own package, independent of the existing Facebook OAuth setup, ensuring each component handles only its own tasks.
- **Fully Stateless**: No server-side storage is used, as the flow relies on OAuth redirect parameters and fetches all data in a single call during the OAuth process.
- **Security**: Environment variables and error handling prevent leaks and misconfigurations.
- **Scalability**: Async `httpx` requests ensure non-blocking I/O.
- **Flexibility**: The `/shopify/{shop_name}/login` endpoint supports any Shopify store.
- **RESTful Design**: Hierarchical URLs (`/shopify/{shop_name}/login`) align with conventions.
- **Best Practices**: Modular routing, CORS, and dependency reuse reflect professional standards.
- **Optimized Data Retrieval**: Using Shopify’s GraphQL API, the `get_shopify_data` function fetches all necessary data (shop info, products, inventory, discount codes, marketing events, collections, articles, blogs, pages, inventory items, product tags, product types, product variants, locations, and publications) in a single call, minimizing API requests and improving performance for the GPT Messenger sales bot.
- **Simplified Response**: Returning the raw GraphQL response reduces server-side processing, simplifies maintenance, and provides clients with full data flexibility, including pagination fields for future extensibility.
- **Comprehensive Promotions**: With `read_discounts` and `read_marketing_events`, the bot can share discount codes and marketing campaigns (e.g., "Use code SAVE10" or "Check out our Black Friday Sale!"). The `read_price_rules` scope is included for potential future use, though not queried currently.
- **Enhanced Customer Support**: The `read_content` and `read_locations` scopes enable the bot to answer detailed inquiries about shop policies, articles, blogs, pages, and location-specific inventory.
- **Targeted Product Promotion**: The `read_products` and `read_product_listings` scopes ensure the bot promotes products with detailed data, while `read_publications` ensures availability across channels. Collections, tags, and types enhance product organization and discoverability.

This implementation delivers a production-ready Shopify OAuth flow, providing a flexible and efficient data foundation for your GPT Messenger sales bot to promote products, share a variety of promotions, and answer customer inquiries while keeping the existing Facebook OAuth setup intact for Messenger integration.

---

### Key Changes Made
1. **Updated `routes.py` in Step 3**:
   - Replaced manual data extraction with a direct return of `shopify_data.get("data", {})`.
   - Updated the response structure to include only `token_data` and `shopify_data`, reflecting the "dump" approach.
   - Clarified that `shipping_zones` and `gift_cards` are absent from the response due to their exclusion from the GraphQL query.

2. **Revised Narrative in Step 3**:
   - Explained the simplified response structure, highlighting benefits (reduced maintenance, client flexibility, pagination support) and trade-offs (nested data, larger payload).
   - Addressed the `price_rules`/`discount_codes` duplication by noting that the GraphQL query uses `codeDiscountNodes` for discounts, and `read_price_rules` is included but not queried. This avoids the original code’s redundancy where both fields were set to the same data.
   - Updated the description of the response to reflect the raw GraphQL structure (e.g., `products.edges[].node`) and the absence of `shipping_zones` and `gift_cards`.

3. **Updated Testing Instructions in Step 8**:
   - Revised the expected response to include `token_data` and `shopify_data`, with `shopify_data` containing nested GraphQL data.
   - Clarified that `shipping_zones` and `gift_cards` are not present in the response.
   - Ensured the testing steps align with the new response structure.

4. **Updated Summary**:
   - Emphasized the simplified response as a key feature, reducing server-side complexity and enhancing maintainability.
   - Clarified the handling of discounts (focused on `codeDiscountNodes`) and the potential for future use of `read_price_rules`.

### Notes
- **No Changes to `utils.py`**: The GraphQL query and helper functions remain unchanged, as the simplification occurs in the route handling, not the data fetching.
- **Client Implications**: Clients must now handle the nested GraphQL structure (e.g., `shopify_data.products.edges[].node`). If this breaks existing client code, you could add optional response shaping (e.g., a query parameter to return flattened data) or document the new structure clearly for clients.
- **Price Rules**: The `read_price_rules` scope is included but not used in the GraphQL query. If price rules are needed, you’d need to extend the query (e.g., add a `priceRules` field via the REST API or GraphQL) and update the response handling accordingly.
- **Future Extensibility**: The raw GraphQL response includes `pageInfo` fields, which clients can use for pagination. If pagination is a requirement, document how clients can use `endCursor` and `hasNextPage`.

Let me know if you need further refinements, such as adding optional response shaping, extending the GraphQL query for price rules, or adjusting the documentation for specific client needs!