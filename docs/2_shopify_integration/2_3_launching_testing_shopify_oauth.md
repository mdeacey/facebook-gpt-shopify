Chapter 2: Shopify Integration
Subchapter 2.3: Launching and Testing Shopify OAuth
This subchapter guides you through launching the FastAPI application built in Subchapter 2.1, using the Shopify development store and app credentials from Subchapter 2.2, and testing the Shopify OAuth flow. We’ll start the server, verify the root endpoint, initiate the OAuth process via /shopify/{shop_name}/login, authenticate with a Shopify account, and confirm the callback response at /shopify/callback. Each step includes expected outputs (e.g., server logs, Shopify login pages, JSON responses) and references to screenshots (not provided) to ensure the integration works correctly. The final response contains token_data and preprocessed_data with test demo products, confirming the app can fetch and process Shopify data for the GPT Messenger sales bot. This subchapter mirrors Subchapter 1.3 (Facebook OAuth testing) and prepares for data preprocessing in Subchapter 2.4.

Step 1: Launch the FastAPI Application
Action: Navigate to your project directory and run the FastAPI application using the following command:
python app.py

Expected Output: The terminal displays Uvicorn server logs indicating the app is running:
INFO:     Will watch for changes in these directories: ['/workspaces/facebook-gpt-shopify']
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
INFO:     Started reloader process [88929] using StatReload
INFO:     Started server process [88932]
INFO:     Waiting for application startup.
INFO:     Application startup complete.

Screenshot Reference: Terminal showing the Uvicorn logs above.
Why?

Running python app.py starts the FastAPI server using Uvicorn, as configured in Subchapter 2.1’s app.py.
The logs confirm the server is listening on http://0.0.0.0:5000 with auto-reload enabled for development.
In GitHub Codespaces, the server is accessible via a public URL (e.g., https://your-codespace-id-5000.app.github.dev), critical for OAuth redirects.


Step 2: Test the Root Endpoint
Action: Open a browser and navigate to the root URL of your application:

Local: http://localhost:5000
GitHub Codespaces: Your public URL, e.g., https://your-codespace-id-5000.app.github.dev

Expected Output: The browser displays:
{
  "status": "ok",
  "message": "Use /facebook/login or /shopify/{shop_name}/login"
}

Screenshot Reference: Browser window showing the JSON response above.
Why?

The root endpoint (@app.get("/") in Subchapter 2.1’s app.py) confirms the FastAPI server is running and supports both Facebook (Chapter 1) and Shopify OAuth flows.
The message field guides users to the Shopify OAuth endpoint, preparing for the next step.
The public URL in Codespaces ensures external access for OAuth redirects, consistent with Subchapter 1.3.


Step 3: Initiate Shopify OAuth
Action: Navigate to the Shopify OAuth login endpoint, using your store name from Subchapter 2.2 (e.g., acme-7cu19ngr):

Local: http://localhost:5000/shopify/acme-7cu19ngr/login
GitHub Codespaces: https://your-codespace-id-5000.app.github.dev/shopify/acme-7cu19ngr/login

Note: Find your store name in the Shopify Partners dashboard under “Stores” (e.g., acme-7cu19ngr).
Expected Output: The browser redirects to a Shopify login page, e.g.:
https://accounts.shopify.com/select?rid=b2db153c-c9d4-45ef-a1af-b4ae93675596

The page displays:
Log in to Shopify
Choose an account
to continue to Shopify
Help  Privacy  Terms

Screenshot Reference: Shopify login page with account selection.
Why?

The /shopify/{shop_name}/login endpoint (Subchapter 2.1, shopify_oauth/routes.py) constructs the OAuth URL with SHOPIFY_API_KEY, SHOPIFY_REDIRECT_URI, scopes (read_product_listings,read_inventory,read_discounts,read_locations,read_products), and a CSRF state token.
The store name (acme-7cu19ngr) matches the development store created in Subchapter 2.2.
The redirect to Shopify’s login page confirms the OAuth flow is initiated correctly.


Step 4: Select Shopify Account
Action: On the Shopify login page, click the name of your Shopify account to proceed.
Expected Output: The browser redirects to another Shopify login page, e.g.:
https://accounts.shopify.com/lookup?rid=b2db153c-c9d4-45ef-a1af-b4ae93675596&verify=1751278840-X7mx5RekniMCAD1gxvX6MqUyePQA6htIGhhr1avMIV0%3D

The page displays:
Log in to Shopify
Log in
Continue to Shopify
Email
or
New to Shopify?
Help  Privacy  Terms

Screenshot Reference: Shopify login page prompting for email or SSO.
Why?

Selecting an account links the OAuth flow to your Shopify user, associated with the acme-7cu19ngr store from Subchapter 2.2.
The redirect to the lookup page prepares for authentication, verifying the session.


Step 5: Authenticate with Shopify (Google SSO)
Action: Enter your Shopify email (e.g., your-email@example.com) and click Continue with Email. If your account uses Google SSO, the browser redirects to Google’s OAuth page, e.g.:
https://accounts.google.com/o/oauth2/auth/oauthchooseaccount?access_type=offline&client_id=119434437228-oub0dlcoh7hi08817cqqchrma4ft5hpa.apps.googleusercontent.com&redirect_uri=https%3A%2F%2Faccounts.shopify.com%2Flogin%2Fexternal%2Fgoogle%2Fcallback&response_type=code&scope=openid%20email%20profile

Log in with your Google account by selecting it or entering credentials.
Expected Output: After Google authentication, Shopify completes the OAuth flow, redirecting to the callback endpoint.
Screenshot Reference: Google OAuth page for account selection.
Why?

Shopify supports SSO (e.g., Google) for user authentication, streamlining login for accounts linked to Google.
The Google OAuth page requests openid, email, and profile scopes to verify your identity.
This step may vary; users without SSO may enter a Shopify password directly.


Step 6: Verify the Callback Response
Action: After authentication, Shopify redirects to the callback endpoint:

Local: http://localhost:5000/shopify/callback?code=...&hmac=...&host=...&shop=...&state=...&timestamp=...
GitHub Codespaces: https://your-codespace-id-5000.app.github.dev/shopify/callback?code=05a8747b43fb1d4d1595805ccf0b6db0&hmac=30c8533ffcb5280092c07c01ea4296967149c5071656d5d0bceba77c06ed9319&host=YWRtaW4uc2hvcGlmeS5jb20vc3RvcmUvYWNtZS03Y3UxOW5ncg&shop=acme-7cu19ngr.myshopify.com&state=1751278788%3A8LzrUd5Wj9I%3AtuPOjl3Z2F53YrY-hylu9OKvkYaj7uDtDbQ1MZX9nMc%3D&timestamp=1751278994

The browser displays a JSON response like:
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
            "location": "Shop location",
            "inventory_quantity": 10
          },
          {
            "title": "Dawn",
            "price": 699.95,
            "available": true,
            "location": "Shop location",
            "inventory_quantity": 10
          },
          {
            "title": "Powder",
            "price": 699.95,
            "available": true,
            "location": "Shop location",
            "inventory_quantity": 10
          },
          {
            "title": "Electric",
            "price": 699.95,
            "available": true,
            "location": "Shop location",
            "inventory_quantity": 10
          },
          {
            "title": "Sunset",
            "price": 699.95,
            "available": true,
            "location": "Shop location",
            "inventory_quantity": 10
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
            "location": "Shop location",
            "inventory_quantity": 50
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
            "location": "Shop location",
            "inventory_quantity": 10
          },
          {
            "title": "Special Selling Plans Ski Wax",
            "price": 49.95,
            "available": true,
            "location": "Shop location",
            "inventory_quantity": 10
          },
          {
            "title": "Sample Selling Plans Ski Wax",
            "price": 9.95,
            "available": true,
            "location": "Shop location",
            "inventory_quantity": 10
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
            "location": "Shop location",
            "inventory_quantity": 50
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
            "location": "Shop location",
            "inventory_quantity": 50
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
            "location": "Shop location",
            "inventory_quantity": 50
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
            "location": "Shop location",
            "inventory_quantity": 10
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
            "location": "Shop location",
            "inventory_quantity": 50
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
            "location": "Shop location",
            "inventory_quantity": 50
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
            "location": "Shop location",
            "inventory_quantity": 50
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
            "location": "Snow City Warehouse",
            "inventory_quantity": 20
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
            "location": "Shop location",
            "inventory_quantity": 50
          }
        ]
      }
    ]
  }
}

Screenshot Reference: Browser showing the JSON response with token_data and preprocessed_data.
Why?

Shopify redirects to the callback URL with code, hmac, host, shop, state, and timestamp parameters, which the FastAPI app (Subchapter 2.1) validates and uses to exchange for an access token.
The preprocessed_data reflects the test demo products from the acme-7cu19ngr store (Subchapter 2.2), processed by preprocess_shopify_data (Subchapter 2.4) to exclude internal IDs, handle inventory (e.g., omitting inventory_quantity for untracked items like gift cards), and include URLs for Messenger preview cards.
The response confirms successful OAuth authentication and data processing, ready for the sales bot.


Step 7: Verify the Integration
Action: Review the JSON response to ensure:

token_data.access_token is present and valid.
token_data.scope includes read_product_listings,read_inventory,read_discounts,read_locations,read_products.
preprocessed_data contains shop, discounts, collections, and products with test demo data (e.g., “The Complete Snowboard”, “Gift Card”).
products have correct inventory_quantity for tracked variants (e.g., 10 for “The Complete Snowboard”) and omit it for untracked ones (e.g., “Gift Card”).
No empty lists (e.g., tags: []) or dictionaries (e.g., metafields: {}) appear, per Subchapter 2.4.
No errors (e.g., HTTP 400 for invalid state or hmac) appear in the browser or server logs.

Expected Outcome:

The response matches the example above, confirming the OAuth flow and data preprocessing work.
Server logs show successful HTTP 200 responses for /shopify/callback, e.g.:

INFO:     127.0.0.1:12345 - "GET /shopify/callback?code=...&hmac=... HTTP/1.1" 200 OK

Screenshot Reference: Terminal logs showing successful request handling.
Why?

The access token enables API calls to Shopify’s GraphQL Admin API for the sales bot.
The preprocessed_data verifies that the app fetches and processes shop data correctly, as implemented in Subchapters 2.1 and 2.4.
Test demo products ensure the bot has realistic data for recommendations and promotions.


Step 8: Troubleshooting Common Issues
If issues arise, check the following:

“Missing code/shop/state”: Ensure SHOPIFY_REDIRECT_URI in .env matches the “Allowed redirection URL(s)” in the Shopify app settings (Subchapter 2.2).
“Invalid state token”: Verify STATE_TOKEN_SECRET is set in .env and consistent (Subchapter 2.1).
“Invalid HMAC”: Confirm SHOPIFY_API_KEY and SHOPIFY_API_SECRET in .env match the Shopify app credentials from Subchapter 2.2.
No products in response: Ensure the acme-7cu19ngr store has test data (Subchapter 2.2) and the app has the correct scopes.
404 or 500 errors: Verify the server is running (http://0.0.0.0:5000) and the Codespaces public URL is accessible.

Why?

These checks ensure a secure and functional OAuth flow, addressing common setup errors.
Proper configuration prepares the app for production use, integrating with Chapter 1’s Facebook functionality.


Step 9: Example Sales Bot Interaction
Using the preprocessed data, the sales bot (combined with Chapter 1’s Messenger integration) can respond to customers:
Customer: I’m looking for a premium snowboard.Bot: Try The Complete Snowboard! It’s a premium snowboard for $699.95, with only 10 units left in Ice or Dawn variants. Use CODE_DISCOUNT_BLACKFRIDAY for 80% off (Nov 28–29, 2025), just $139.99. Check it out: [https://acme-7cu19ngr.myshopify.com/products/the-complete-snowboard]. Explore our Premium Snowboards collection: [https://acme-7cu19ngr.myshopify.com/collections/automated-collection].  
Customer: Any gift cards?Bot: Our Gift Card comes in $10–$100 options, perfect for gifting! Available now: [https://acme-7cu19ngr.myshopify.com/products/gift-card].  
Why?

The preprocessed data (from Subchapter 2.4) provides URLs, inventory details, and discounts, enabling the bot to generate Messenger preview cards and promotions.
This integrates with Chapter 1’s Messenger API access for seamless customer interactions.


Summary: Why This Subchapter Matters

Server Verification: Launching the app and checking the root endpoint confirms the FastAPI setup from Subchapter 2.1 is operational.
OAuth Flow: Initiating and completing the OAuth process tests the integration with Shopify’s API, using credentials from Subchapter 2.2.
Callback Success: The /shopify/callback response verifies that the OAuth logic (Subchapter 2.1) and preprocessing (Subchapter 2.4) work, providing sales-ready data.
Bot Readiness: The processed test demo products enable the bot to recommend products and promotions, integrating with Chapter 1’s Facebook functionality.

Next Steps:

Review the OAuth implementation (Subchapter 2.1) and store setup (Subchapter 2.2) if issues arise.
Preprocess the Shopify data for optimized bot interactions (Subchapter 2.4).
