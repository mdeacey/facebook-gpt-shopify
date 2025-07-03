# Chapter 2: Shopify Integration
## Subchapter 2.3: Launching and Testing Shopify OAuth

This subchapter guides you through launching the FastAPI application built in Subchapter 2.1, using the Shopify development store and app credentials from Subchapter 2.2, and testing the Shopify OAuth flow. We’ll start the server, verify the root endpoint, initiate the OAuth process via `/shopify/{shop_name}/login`, authenticate with a Shopify account, and confirm the callback response at `/shopify/callback`. Each step includes expected outputs (e.g., server logs, Shopify login pages, JSON responses) and references to screenshots (not provided). The response includes a UUID to identify the user’s data for future platform integrations. This confirms the app can fetch Shopify data for the GPT Messenger sales bot.

### Step 1: Launch the FastAPI Application
**Action**: Navigate to your project directory and run:
```bash
python app.py
```

**Expected Output**: Terminal displays Uvicorn server logs:
```
INFO:     Will watch for changes in these directories: ['/workspaces/facebook-gpt-shopify']
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
INFO:     Started reloader process [88929] using StatReload
INFO:     Started server process [88932]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Screenshot Reference**: Terminal showing Uvicorn logs.
**Why?**
- Runs the FastAPI server (Subchapter 2.1’s `app.py`).
- Confirms the server is listening on `http://0.0.0.0:5000`.
- In GitHub Codespaces, accessible via `https://your-codespace-id-5000.app.github.dev`.

### Step 2: Test the Root Endpoint
**Action**: Open a browser and navigate to:
- **Local**: `http://localhost:5000`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev`

**Expected Output**: Browser displays:
```json
{
  "status": "ok",
  "message": "Use /facebook/login or /shopify/{shop_name}/login"
}
```

**Screenshot Reference**: Browser showing JSON response.
**Why?**
- Confirms the server supports both Facebook (Chapter 1) and Shopify OAuth flows.
- Guides users to the Shopify OAuth endpoint.

### Step 3: Initiate Shopify OAuth
**Action**: Navigate to the Shopify OAuth login endpoint, using your store name (e.g., `acme-7cu19ngr`):
- **Local**: `http://localhost:5000/shopify/acme-7cu19ngr/login`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev/shopify/acme-7cu19ngr/login`

**Expected Output**: Browser redirects to a Shopify login page, e.g.:
```
https://accounts.shopify.com/select?rid=b2db153c-c9d4-45ef-a1af-b4ae93675596
```

The page displays:
```
Log in to Shopify
Choose an account
to continue to Shopify
Help  Privacy  Terms
```

**Screenshot Reference**: Shopify login page with account selection.
**Why?**
- The `/shopify/{shop_name}/login` endpoint (Subchapter 2.1) constructs the OAuth URL with `SHOPIFY_API_KEY`, `SHOPIFY_REDIRECT_URI`, scopes, and a state token.
- The store name matches the development store (Subchapter 2.2).
- The redirect confirms OAuth initiation.

### Step 4: Select Shopify Account
**Action**: Click the name of your Shopify account.

**Expected Output**: Browser redirects to another Shopify login page, e.g.:
```
https://accounts.shopify.com/lookup?rid=b2db153c-c9d4-45ef-a1af-b4ae93675596&verify=1751278840-X7mx5RekniMCAD1gxvX6MqUyePQA6htIGhhr1avMIV0%3D
```

The page displays:
```
Log in to Shopify
Log in
Continue to Shopify
Email
or
New to Shopify?
Help  Privacy  Terms
```

**Screenshot Reference**: Shopify login page prompting for email or SSO.
**Why?**
- Links the OAuth flow to your Shopify user and store.
- Prepares for authentication.

### Step 5: Authenticate with Shopify (Google SSO)
**Action**: Enter your Shopify email and click “Continue with Email”. If using Google SSO, redirect to Google’s OAuth page, e.g.:
```
https://accounts.google.com/o/oauth2/auth/oauthchooseaccount?access_type=offline&client_id=119434437228-oub0dlcoh7hi08817cqqchrma4ft5hpa.apps.googleusercontent.com&redirect_uri=https%3A%2F%2Faccounts.shopify.com%2Flogin%2Fexternal%2Fgoogle%2Fcallback&response_type=code&scope=openid%20email%20profile
```

Log in with your Google account.

**Expected Output**: Shopify redirects to the callback endpoint.
**Screenshot Reference**: Google OAuth page.
**Why?**
- Shopify supports SSO for streamlined login.
- Google OAuth verifies identity.

### Step 6: Verify the Callback Response
**Action**: After authentication, Shopify redirects to:
- **Local**: `http://localhost:5000/shopify/callback?code=...&hmac=...&host=...&shop=...&state=...&timestamp=...`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev/shopify/callback?code=05a8747b43fb1d4d1595805ccf0b6db0&hmac=30c8533ffcb5280092c07c01ea4296967149c5071656d5d0bceba77c06ed9319&host=YWRtaW4uc2hvcGlmeS5jb20vc3RvcmUvYWNtZS03Y3UxOW5ncg&shop=acme-7cu19ngr.myshopify.com&state=1751278788%3A8LzrUd5Wj9I%3AtuPOjl3Z2F53YrY-hylu9OKvkYaj7uDtDbQ1MZX9nMc%3D&timestamp=1751278994`

Browser displays JSON response (abridged):
```json
{
  "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "token_data": {
    "access_token": "shpua_9a72896d590dbff5d3cf818f49710f67",
    "scope": "read_product_listings,read_inventory,read_discounts,read_locations,read_products"
  },
  "shopify_data": {
    "data": {
      "shop": {
        "name": "acme-7cu19ngr",
        "primaryDomain": {"url": "https://acme-7cu19ngr.myshopify.com"}
      },
      "products": {
        "edges": [
          {
            "node": {
              "title": "The Complete Snowboard",
              "description": "This PREMIUM snowboard is so SUPERDUPER awesome!",
              "handle": "the-complete-snowboard",
              "productType": "snowboard",
              "vendor": "Snowboard Vendor",
              "tags": ["Premium", "Snow", "Snowboard", "Sport", "Winter"],
              "status": "ACTIVE",
              "variants": {
                "edges": [
                  {
                    "node": {
                      "title": "Ice",
                      "price": "699.95",
                      "availableForSale": true,
                      "inventoryItem": {
                        "inventoryLevels": {
                          "edges": [
                            {
                              "node": {
                                "quantities": [
                                  {"name": "available", "quantity": 10}
                                ],
                                "location": {"name": "Shop location"}
                              }
                            }
                          ]
                        }
                      }
                    }
                  }
                ]
              }
            }
          }
        ]
      }
    }
  }
}
```

**Screenshot Reference**: Browser showing JSON response with `user_uuid`.
**Why?**
- Shopify redirects with parameters, which `/shopify/callback` validates and uses to generate a UUID and fetch data.
- The `user_uuid` prepares for multi-platform integration.

### Step 7: Verify the Integration
**Action**: Review the JSON response to ensure:
- `user_uuid` is a valid UUID (e.g., `550e8400-e29b-41d4-a716-446655440000`).
- `token_data.access_token` is present.
- `token_data.scope` includes requested scopes.
- `shopify_data` contains shop, products, discounts, and collections.
- No errors (e.g., HTTP 400) appear.

**Expected Outcome**:
- Response matches the example.
- Server logs show HTTP 200:
```
INFO:     127.0.0.1:12345 - "GET /shopify/callback?code=...&hmac=... HTTP/1.1" 200 OK
```

**Screenshot Reference**: Terminal logs.
**Why?**
- Verifies OAuth and data retrieval for the sales bot.

### Step 8: Troubleshooting Common Issues
If issues arise:
- **“Missing code/shop/state”**: Ensure `SHOPIFY_REDIRECT_URI` matches the Shopify app settings (Subchapter 2.2).
- **“Invalid state token”**: Verify `STATE_TOKEN_SECRET` in `.env`.
- **“Invalid HMAC”**: Check `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET`.
- **No products in response**: Confirm the store has test data (Subchapter 2.2) and correct scopes.
- **No UUID in response**: Verify UUID generation in `/shopify/callback` (Subchapter 2.1).
- **404 or 500 errors**: Check server and Codespaces URL.

**Why?**
- Ensures a functional OAuth flow.

### Step 9: Example Sales Bot Interaction
The sales bot can use the data in later integrations, e.g.:
```
Customer: I’m looking for a premium snowboard.
Bot: Try The Complete Snowboard for $699.95! Check it out: [https://acme-7cu19ngr.myshopify.com/products/the-complete-snowboard].
```

### Summary: Why This Subchapter Matters
- **Server Verification**: Confirms FastAPI setup (Subchapter 2.1).
- **OAuth Flow**: Tests Shopify API integration (Subchapter 2.2).
- **UUID Generation**: Prepares for multi-platform linking.
- **Bot Readiness**: Provides data for recommendations.

### Next Steps:
- Review Subchapter 2.1 or 2.2 if issues arise.
- Proceed to Chapter 3 for platform linking.