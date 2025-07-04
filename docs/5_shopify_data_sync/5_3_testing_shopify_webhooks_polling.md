# Chapter 5: Shopify Data Sync
## Subchapter 5.3: Testing Shopify Webhooks and Polling

### Introduction
With Shopify webhooks and polling set up in Subchapters 5.1 and 5.2, this subchapter verifies their functionality through integrated tests within the OAuth flow. After successful authentication, the FastAPI application tests the webhook endpoint and polling mechanism for the authenticated shop, using the UUID from the SQLite-based session mechanism (Chapter 3) to identify the user. Data is stored temporarily in `<shop_name>/shopify_data.json`, and tests return consistent JSON results to confirm functionality. This ensures the GPT Messenger sales bot can reliably fetch and process non-sensitive shop and product data using `TokenStorage` and `SessionStorage`.

### Prerequisites
- Completed Chapters 1–4 and Subchapters 5.1–5.2.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) and `STATE_TOKEN_SECRET` set in `.env`.
- `apscheduler` installed (`pip install apscheduler`).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).

---

### Step 1: Test via OAuth Flow
The tests for webhooks and polling are executed during the Shopify OAuth callback, using the `session_id` cookie.

**Instructions**:
1. Run the app:
   ```bash
   python app.py
   ```
2. Initiate Shopify OAuth:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
   or, for GitHub Codespaces:
   ```
   https://your-codespace-id-5000.app.github.dev/shopify/acme-7cu19ngr/login
   ```
3. Log in to your Shopify account and authorize the app, granting `read_product_listings`, `read_inventory`, `read_discounts`, `read_locations`, `read_products` permissions.

**Expected Output**:
- Browser redirects to the callback endpoint, e.g.:
  ```
  http://localhost:5000/shopify/callback?code=05a8747b43fb1d4d1595805ccf0b6db0&hmac=30c8533ffcb5280092c07c01ea4296967149c5071656d5d0bceba77c06ed9319&host=YWRtaW4uc2hvcGlmeS5jb20vc3RvcmUvYWNtZS03Y3UxOW5ncg&shop=acme-7cu19ngr.myshopify.com&state=1751278788%3A8LzrUd5Wj9I%3AtuPOjl3Z2F53YrY-hylu9OKvkYaj7uDtDbQ1MZX9nMc%3D×tamp=1751278994
  ```
- Browser displays JSON response (abridged):
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
    },
    "webhook_test": {"status": "success"},
    "polling_test": {"status": "success"}
  }
  ```
- Server logs show:
  ```
  INFO:     127.0.0.1:0 - "GET /shopify/acme-7cu19ngr/login HTTP/1.1" 307 Temporary Redirect
  Webhook registered for acme-7cu19ngr.myshopify.com: products/update
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Test Product'}}
  INFO:     127.0.0.1:32930 - "POST /shopify/webhook HTTP/1.1" 200 OK
  Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  Polling test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  Wrote data to acme-7cu19ngr.myshopify.com/shopify_data.json for acme-7cu19ngr.myshopify.com
  INFO:     127.0.0.1:0 - "GET /shopify/callback?code=...&hmac=... HTTP/1.1" 200 OK
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test: {"status": "success"}` indicates the webhook endpoint processed the test event.
- **Polling Success**: `polling_test: {"status": "success"}` confirms polling retrieved data.
- **UUID**: `user_uuid` matches the Shopify OAuth UUID (Chapter 3).
- **Shop Data**: `shopify_data` includes shop, products, discounts, and collections.
- **Errors**: If `webhook_test` or `polling_test` shows `{"status": "failed", "message": "..."}`, check the `message`.

**Screenshot Reference**: Browser showing JSON response; terminal showing logs.

**Why?**
- Confirms webhook and polling functionality using `TokenStorage` and `SessionStorage`.
- Ensures non-sensitive data for the sales bot, stored temporarily.

### Step 2: Verify Webhook Functionality
**Action**: Simulate a product update to test the webhook endpoint.

**Instructions**:
1. In the Shopify Admin, update a product’s title or inventory (e.g., “The Complete Snowboard”).
2. Check server logs for webhook event processing.

**Expected Output**:
- Logs show:
  ```
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Updated Snowboard'}}
  Wrote data to acme-7cu19ngr.myshopify.com/shopify_data.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Verifies the `/shopify/webhook` endpoint (Subchapter 5.1) processes `products/update` events using `TokenStorage`.
- Confirms data is stored in temporary files.

### Step 3: Verify Polling Functionality
**Action**: Manually trigger the daily polling function.

**Instructions**:
1. Modify `app.py` to run `shopify_daily_poll` immediately (temporary):
   ```python
   from shopify_integration.utils import daily_poll as shopify_daily_poll
   shopify_daily_poll()  # Add this line
   ```
2. Run: `python app.py`.
3. Check logs for polling results.

**Expected Output**:
- Logs show:
  ```
  Polled data for shop acme-7cu19ngr.myshopify.com: Success
  Wrote data to acme-7cu19ngr.myshopify.com/shopify_data.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Confirms `poll_shopify_data` (Subchapter 5.2) retrieves data using `TokenStorage`.
- Ensures the daily poll works with temporary file storage.

### Step 4: Verify Temporary File Storage
**Action**: Check the temporary file storage for shop data.

**Instructions**:
1. Verify the file exists: `acme-7cu19ngr.myshopify.com/shopify_data.json`.
2. Open the file and confirm it matches the `shopify_data` from the JSON response.

**Expected Content** (abridged):
```json
{
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
            ...
          }
        }
      ]
    }
  }
}
```

**Why?**
- Confirms data is stored correctly, preparing for cloud storage in Chapter 6.

### Step 5: Troubleshoot Issues
**Action**: Diagnose and fix issues if the JSON response or logs show failures.

**Common Issues and Fixes**:
1. **Webhook Test Failure (`webhook_test: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Webhook registration or verification failed.
   - **Fix**:
     - Check the `message` (e.g., HTTP 401 for HMAC issues).
     - Verify `SHOPIFY_API_SECRET` and `SHOPIFY_WEBHOOK_ADDRESS` in `.env`.
     - Ensure `SHOPIFY_WEBHOOK_ADDRESS` is accessible (use ngrok).
     - Check logs for `Webhook test result`.
2. **Polling Test Failure (`polling_test: {"status": "error", "message": "..."}`)**:
   - **Cause**: Failed to fetch shop data.
   - **Fix**:
     - Check the `message` (e.g., “User UUID not found”).
     - Verify tokens in `tokens.db` using `sqlite3 /app/data/tokens.db "SELECT key FROM tokens;"`.
     - Check logs for API errors (e.g., HTTP 429).
3. **Missing `session_id` Cookie**:
   - **Cause**: Shopify OAuth not completed.
   - **Fix**: Run `/shopify/acme-7cu19ngr/login` to set the cookie.
4. **Invalid or Expired Session**:
   - **Cause**: Session expired or invalid.
   - **Fix**: Re-run Shopify OAuth to set a new `session_id` cookie.
5. **Empty `shopify_data`**:
   - **Cause**: No products or missing permissions.
   - **Fix**:
     - Ensure scopes (`read_products`, etc.) are granted.
     - Confirm the store has test data (Subchapter 2.2).
6. **Missing Files**:
   - **Cause**: File writing failed.
   - **Fix**: Check write permissions and logs for errors.

**Why?**
- Uses JSON responses and logs to debug webhook, polling, or session issues.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Tests confirm webhook and polling systems work, using `TokenStorage` and `SessionStorage`.
- **Security**: Excludes sensitive tokens, validates sessions, and uses encrypted storage.
- **Comprehensive Data**: Stores non-sensitive shop and product data for the sales bot.
- **Bot Readiness**: Ensures up-to-date data for customer interactions.

### Next Steps:
- Proceed to Chapter 6 for cloud storage integration.
- Monitor logs to ensure ongoing test success.