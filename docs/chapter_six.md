Chapter 4: Launching and Testing the FastAPI Application for Shopify OAuth
This chapter guides you through launching the FastAPI application and testing the Shopify OAuth flow set up in previous chapters. We’ll run the app, verify the root endpoint, initiate the Shopify OAuth process via /shopify/{shop_name}/login, authenticate with a Shopify account, and confirm the callback response at /shopify/callback. Each step includes expected outputs (e.g., server logs, Shopify login pages, JSON responses) and references to screenshots (not provided) to ensure the integration works correctly. The final response contains token_data and preprocessed_data with test demo products, confirming the app can fetch and process Shopify data for the GPT Messenger sales bot.

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

Running python app.py starts the FastAPI server using Uvicorn, as configured in app.py.
The logs confirm the server is listening on http://0.0.0.0:5000 with auto-reload enabled for development.
In GitHub Codespaces, the server is accessible via a public URL (e.g., https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev).


Step 2: Test the Root Endpoint
Action: Open a browser and navigate to the root URL of your application:

Local: http://localhost:5000
GitHub Codespaces: Your public URL, e.g., https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev

Expected Output: The browser displays:
{
  "status": "ok",
  "message": "Use /facebook/login or /shopify/{shop_name}/login"
}

Screenshot Reference: Browser window showing the JSON response above.
Why?

The root endpoint (@app.get("/") in app.py) returns a JSON response to confirm the FastAPI server is running.
The message field indicates available OAuth endpoints, including Shopify’s, ensuring the server is ready for testing.
The public URL in GitHub Codespaces enables external access for OAuth redirects.


Step 3: Initiate Shopify OAuth
Action: Navigate to the Shopify OAuth login endpoint, using your shop name (e.g., acme-7cu19ngr):

Local: http://localhost:5000/shopify/acme-7cu19ngr/login
GitHub Codespaces: https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev/shopify/acme-7cu19ngr/login

Note: Obtain the shop name from the Shopify Partners dashboard (partners.shopify.com) by clicking Stores and noting the name (e.g., acme-7cu19ngr).
Expected Output: The browser redirects through temporary URLs and lands on a Shopify login page, e.g.:
https://accounts.shopify.com/select?rid=b2db153c-c9d4-45ef-a1af-b4ae93675596

The page displays:
Log in to Shopify
Choose an account
to continue to Shopify
Help
Privacy
Terms

Screenshot Reference: Shopify login page with account selection.
Why?

The /shopify/{shop_name}/login endpoint (original Chapter 3, now likely Chapter 5) constructs the OAuth URL with client_id, redirect_uri, scope (read_product_listings,read_inventory,read_discounts,read_locations,read_products), and a CSRF state token.
The shop name (acme-7cu19ngr) is derived from your development store in the Shopify Partners dashboard.
The redirect to Shopify’s login page confirms the app is initiating authentication correctly.


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
Help
Privacy
Terms

Screenshot Reference: Shopify login page prompting for email or SSO.
Why?

Selecting an account associates the OAuth flow with your Shopify user, linked to the acme-7cu19ngr store.
The redirect to the lookup page prepares for authentication, verifying the session.


Step 5: Authenticate with Shopify (Google SSO)
Action: Enter your Shopify email (e.g., marcusdeacey@gmail.com) and click Continue with Email. Since your account uses Google SSO, the browser redirects to Google’s OAuth page, e.g.:
https://accounts.google.com/o/oauth2/auth/oauthchooseaccount?access_type=offline&client_id=119434437228-oub0dlcoh7hi08817cqqchrma4ft5hpa.apps.googleusercontent.com&hd&hl&login_hint=marcusdeacey%40gmail.com&prompt=select_account&redirect_uri=https%3A%2F%2Faccounts.shopify.com%2Flogin%2Fexternal%2Fgoogle%2Fcallback&response_type=code&scope=openid%20email%20profile&state=...

Log in with your Google account by selecting it or entering credentials.
Expected Output: After Google authentication, Shopify completes the OAuth flow.
Screenshot Reference: Google OAuth page for account selection.
Why?

Shopify supports SSO (e.g., Google) for user authentication, streamlining login for accounts linked to Google.
The Google OAuth page requests openid, email, and profile scopes to verify your identity.
This step is specific to your setup; users without Google SSO may enter a Shopify password directly.


Step 6: Verify the Callback Response
Action: After authentication, the browser redirects to the callback endpoint:

Local: http://localhost:5000/shopify/callback?code=...&hmac=...&host=...&shop=...&state=...&timestamp=...
GitHub Codespaces: https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev/shopify/callback?code=05a8747b43fb1d4d1595805ccf0b6db0&hmac=30c8533ffcb5280092c07c01ea4296967149c5071656d5d0bceba77c06ed9319&host=YWRtaW4uc2hvcGlmeS5jb20vc3RvcmUvYWNtZS03Y3UxOW5ncg&shop=acme-7cu19ngr.myshopify.com&state=1751278788%3A8LzrUd5Wj9I%3AtuPOjl3Z2F53YrY-hylu9OKvkYaj7uDtDbQ1MZX9nMc%3D×tamp=1751278994

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
        "starts_at": "2025-11-28T00:00:00Z",
        "ends_at": "2025-11-29T00:00:00Z",
        "percentage": 80.0
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

Shopify redirects to the callback URL with code, hmac, host, shop, state, and timestamp parameters, which the FastAPI app validates and uses to exchange for an access token (original Chapter 3, now likely Chapter 5).
The preprocessed_data reflects the test demo products from your acme-7cu19ngr development store, processed to exclude internal IDs, handle inventory (e.g., omitting inventory_quantity for untracked items like gift cards), and include URLs for Messenger preview cards.
The response confirms successful OAuth authentication and data retrieval, ready for the sales bot.


Step 7: Verify the Integration
Action: Review the JSON response to ensure:

token_data.access_token is present and valid.
token_data.scope includes read_product_listings,read_inventory,read_discounts,read_locations,read_products.
preprocessed_data contains shop, discounts, collections, and products with test demo data (e.g., “The Complete Snowboard”, “Gift Card”).
products have correct inventory_quantity for tracked variants (e.g., 10 for “The Complete Snowboard”) and omit it for untracked ones (e.g., “Gift Card”).
No errors (e.g., HTTP 400 for invalid state or HMAC) appear in the browser or server logs.

Expected Outcome:

The response matches the example above, confirming the Shopify OAuth flow and data preprocessing work.
Server logs show successful HTTP 200 responses for /shopify/callback.

Screenshot Reference: Terminal logs showing successful request handling.
Why?

The access token enables API calls to Shopify’s GraphQL Admin API for the sales bot.
The preprocessed_data verifies that the app fetches and processes shop data correctly, aligning with the preprocessing logic (original Chapter 5, now likely Chapter 7).
The test demo products ensure the bot has realistic data for recommendations and promotions.


Troubleshooting Common Issues

“Missing code/shop/state”: Ensure SHOPIFY_REDIRECT_URI in .env matches the “Allowed redirection URL(s)” in the Shopify app settings (original Chapter 4, now likely Chapter 6).
“Invalid state token”: Verify STATE_TOKEN_SECRET is set in .env and consistent.
“Invalid HMAC”: Check that SHOPIFY_API_KEY and SHOPIFY_API_SECRET in .env match the Shopify app credentials.
No products in response: Confirm the acme-7cu19ngr store has test data (added in original Chapter 4, now likely Chapter 6) and the app has the correct scopes.
404 or 500 errors: Ensure the server is running and the public URL is accessible in GitHub Codespaces.

Why?

These checks ensure the OAuth flow is secure and handles edge cases, preparing the app for production use.


Summary: Why This Testing Matters

Server Verification: Running python app.py and checking the root endpoint confirms the FastAPI server is operational.
OAuth Flow: Navigating to /shopify/acme-7cu19ngr/login and authenticating tests the Shopify integration.
Callback Success: The /shopify/callback response with token_data and preprocessed_data verifies that credentials and OAuth logic are correctly implemented.
Bot Readiness: The processed test demo products prepare the app for sales bot interactions, such as promoting snowboards and gift cards.

With the Shopify OAuth flow working, you’ve confirmed the app can fetch and process data for the GPT Messenger sales bot, integrating with the Facebook OAuth flow (Chapter 3).