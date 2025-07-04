# Chapter 6: DigitalOcean Integration
## Subchapter 6.4: Testing Data Sync with DigitalOcean Spaces

### Introduction
With Facebook and Shopify data sync updated to use DigitalOcean Spaces (Subchapters 6.1–6.2) and the bucket configured (Subchapter 6.3), this subchapter verifies that webhook and polling mechanisms correctly upload non-sensitive data to Spaces (`users/<uuid>/facebook/<page_id>/page_data.json` and `users/<uuid>/shopify/<shop_name>/shopify_data.json`) using the UUID from `TokenStorage` (Chapter 3). We test the OAuth flows for both platforms, trigger webhook events, and verify polling to ensure data is stored securely and scalably for the GPT Messenger sales bot.

### Prerequisites
- Completed Chapters 1–5 and Subchapters 6.1–6.3.
- FastAPI application running on a DigitalOcean Droplet or locally.
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- DigitalOcean Spaces bucket and credentials configured (Subchapter 6.3).
- Environment variables for Spaces, OAuth, and webhooks set in `.env`.

---

### Step 1: Test Facebook Data Sync via OAuth Flow
**Action**: Run the Facebook OAuth flow to test webhook and polling uploads to Spaces.

**Instructions**:
1. Run the app:
   ```bash
   python app.py
   ```
2. Complete Shopify OAuth to set the `session_id` cookie:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
3. Initiate Facebook OAuth:
   ```
   http://localhost:5000/facebook/login
   ```

**Expected Output**:
- Browser redirects to `/facebook/callback` and displays (abridged):
  ```json
  {
    "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "pages": {
      "data": [
        {
          "id": "101368371725791",
          "name": "Fast Online Store PH",
          "category": "Footwear store",
          ...
        }
      ],
      "paging": {...}
    },
    "webhook_test": {"status": "success"},
    "polling_test": [
      {
        "page_id": "101368371725791",
        "result": {"status": "success"}
      }
    ]
  }
  ```
- Server logs show:
  ```
  Webhook subscription for 'name,category' already exists for page 101368371725791
  Received webhook event for page test_page_id: {'id': 'test_page_id', 'changes': [{'field': 'name', 'value': 'Test Page'}]}
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook/test_page_id/page_data.json
  Webhook test result: {'status': 'success'}
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_data.json
  Polling test result for page 101368371725791: {'status': 'success'}
  ```

**Why?**
- Confirms webhook and polling upload data to Spaces using `TokenStorage`.

### Step 2: Test Shopify Data Sync via OAuth Flow
**Action**: Run the Shopify OAuth flow to test webhook and polling uploads.

**Instructions**:
1. Run the app: `python app.py`.
2. Initiate Shopify OAuth:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```

**Expected Output**:
- Browser redirects to `/shopify/callback` and displays (abridged):
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
                ...
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
  Webhook registered for acme-7cu19ngr.myshopify.com: products/update
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Test Product'}}
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shopify_data.json
  Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  Polling test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  ```

**Why?**
- Confirms webhook and polling upload Shopify data to Spaces using `TokenStorage`.

### Step 3: Verify Webhook Functionality
**Action**: Simulate updates to trigger webhooks.

**Instructions**:
1. For Facebook: Update a page’s name or category in the Facebook interface.
2. For Shopify: Update a product’s title or inventory in the Shopify Admin.
3. Check server logs for webhook event processing.

**Expected Output**:
- Facebook logs:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_data.json
  ```
- Shopify logs:
  ```
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Updated Snowboard'}}
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shopify_data.json
  ```

**Why?**
- Verifies webhook endpoints (Subchapters 4.1, 5.1) upload to Spaces using `TokenStorage`.

### Step 4: Verify Polling Functionality
**Action**: Manually trigger daily polling.

**Instructions**:
1. Modify `app.py` to run `facebook_daily_poll` and `shopify_daily_poll`:
   ```python
   from facebook_integration.utils import daily_poll as facebook_daily_poll
   from shopify_integration.utils import daily_poll as shopify_daily_poll
   facebook_daily_poll()
   shopify_daily_poll()
   ```
2. Run: `python app.py`.
3. Check logs for polling results.

**Expected Output**:
- Facebook logs:
  ```
  Polled data for page 101368371725791: Success
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_data.json
  ```
- Shopify logs:
  ```
  Polled data for shop acme-7cu19ngr.myshopify.com: Success
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shopify_data.json
  ```

**Why?**
- Confirms polling functions (Subchapters 4.2, 5.2) upload to Spaces.

### Step 5: Verify Spaces Storage
**Action**: Check the Spaces bucket for uploaded files.

**Instructions**:
1. In the DigitalOcean control panel, navigate to the Spaces bucket (`gpt-messenger-data`).
2. Verify files exist:
   - `users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_data.json`
   - `users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shopify_data.json`
3. Download and inspect files to confirm content matches OAuth responses.

**Expected Content** (abridged):
- Facebook:
  ```json
  {
    "data": [
      {
        "id": "101368371725791",
        "name": "Fast Online Store PH",
        ...
      }
    ],
    "paging": {...}
  }
  ```
- Shopify:
  ```json
  {
    "data": {
      "shop": {
        "name": "acme-7cu19ngr",
        ...
      },
      "products": {
        "edges": [
          {
            "node": {
              "title": "The Complete Snowboard",
              ...
            }
          }
        ]
      }
    }
  }
  ```

**Why?**
- Confirms data is stored correctly in Spaces, organized by UUID.

### Step 6: Troubleshoot Issues
**Action**: Diagnose and fix issues if tests fail.

**Common Issues and Fixes**:
1. **Webhook Test Failure**:
   - **Cause**: Webhook registration or verification failed.
   - **Fix**: Verify `FACEBOOK_WEBHOOK_ADDRESS`, `SHOPIFY_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`, `SHOPIFY_API_SECRET` in `.env`.
2. **Polling Test Failure**:
   - **Cause**: Token or UUID not found.
   - **Fix**: Check `tokens.db` with `sqlite3 /app/data/tokens.db "SELECT key FROM tokens;"`.
3. **Spaces Upload Failure**:
   - **Cause**: Invalid credentials or bucket settings.
   - **Fix**: Verify `SPACES_API_KEY`, `SPACES_API_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`, `SPACES_ENDPOINT` in `.env`.
4. **Missing `session_id` Cookie**:
   - **Fix**: Run Shopify OAuth to set the cookie.
5. **Empty Data**:
   - **Fix**: Ensure permissions and test data exist (Chapters 1–2).
6. **CORS Errors**:
   - **Fix**: Verify CORS settings in Spaces (Subchapter 6.3) and `app.py`.

**Why?**
- Uses logs and JSON responses to debug issues.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Confirms webhook and polling upload to Spaces.
- **Security**: Uses `TokenStorage`, excludes sensitive data.
- **Scalability**: Ensures persistent, UUID-organized storage.
- **Bot Readiness**: Provides up-to-date data for customer interactions.

### Next Steps:
- Proceed to Chapter 7 for data backup and recovery.