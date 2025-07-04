# Chapter 6: DigitalOcean Integration
## Subchapter 6.4: Testing Data Sync with DigitalOcean Spaces

### Introduction
With DigitalOcean Spaces integrated for Facebook (Subchapter 6.1) and Shopify (Subchapter 6.2) data, this subchapter verifies that webhook and polling systems correctly upload data to the UUID-based bucket structure (`users/<uuid>/facebook_messenger/<page_id>/page_data.json`, `users/<uuid>/shopify/shopify_data.json`). Tests are executed during OAuth flows, using the session-based UUID mechanism (Chapter 3) to ensure production-ready operation for multiple users. We confirm data storage in Spaces, check JSON responses, and troubleshoot issues to ensure the GPT Messenger sales bot has reliable, up-to-date data.

### Prerequisites
- Completed Chapters 1–5 and Subchapters 6.1–6.3.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- API credentials (`FACEBOOK_*`, `SHOPIFY_*`, `SPACES_*`) set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- Access tokens (`FACEBOOK_ACCESS_TOKEN_<page_id>`, `SHOPIFY_ACCESS_TOKEN_<shop_key>`) and UUID mappings (`PAGE_UUID_<page_id>`, `USER_UUID_<shop_key>`) stored.
- `boto3` and `apscheduler` installed (`pip install boto3 apscheduler`).
- DigitalOcean Spaces bucket created (Subchapter 6.3).

---

### Step 1: Test via OAuth Flows
Tests for webhooks, polling, and Spaces uploads are executed during the OAuth callbacks for both platforms.

**Instructions**:
1. Run the app:
   ```bash
   python app.py
   ```
2. **Shopify OAuth**:
   - Navigate to:
     ```
     http://localhost:5000/shopify/acme-7cu19ngr/login
     ```
     or, for GitHub Codespaces:
     ```
     https://your-codespace-id-5000.app.github.dev/shopify/acme-7cu19ngr/login
     ```
   - Log in and authorize the app.
   - Expected JSON response (abridged):
     ```json
     {
       "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
       "token_data": {
         "access_token": "shpua_9a72896d590dbff5d3cf818f49710f67",
         "scope": "read_product_listings,read_inventory,read_discounts,read_locations,read_products,write_products,write_inventory"
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
                   ...
                 }
               }
             ]
           }
         }
       },
       "webhook_test": {"status": "success"},
       "polling_test": {"status": "success"},
       "upload_status": {"status": "success"}
     }
     ```
   - Server logs:
     ```
     Webhook registered for acme-7cu19ngr.myshopify.com: products/update
     Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Test Product'}}
     INFO:     127.0.0.1:32930 - "POST /shopify/webhook HTTP/1.1" 200 OK
     Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
     Polling test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
     Uploaded data to Spaces for acme-7cu19ngr.myshopify.com
     INFO:     127.0.0.1:0 - "GET /shopify/callback?code=...&hmac=... HTTP/1.1" 200 OK
     ```
3. **Facebook OAuth**:
   - Navigate to:
     ```
     http://localhost:5000/facebook/login
     ```
     or, for GitHub Codespaces:
     ```
     https://your-codespace-id-5000.app.github.dev/facebook/login
     ```
   - Log in and authorize the app.
   - Expected JSON response:
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
       ],
       "upload_status": [
         {
           "page_id": "101368371725791",
           "result": {"status": "success"}
         }
       ]
     }
     ```
   - Server logs:
     ```
     Webhook subscription for 'name,category' already exists for page 101368371725791
     Received webhook event for page test_page_id: {'id': 'test_page_id', 'changes': [{'field': 'name', 'value': 'Test Page'}]}
     INFO:     127.0.0.1:32930 - "POST /facebook/webhook HTTP/1.1" 200 OK
     Webhook test result: {'status': 'success'}
     Polling test result for page 101368371725791: {'status': 'success'}
     Uploaded data to Spaces for page 101368371725791
     INFO:     127.0.0.1:0 - "GET /facebook/callback?code=...&state=... HTTP/1.1" 200 OK
     ```

**What to Look For**:
- **Webhook Success**: `webhook_test: {"status": "success"}` confirms webhook processing.
- **Polling Success**: `polling_test` confirms data retrieval.
- **Upload Success**: `upload_status` confirms Spaces uploads.
- **UUID**: `user_uuid` matches across both responses.
- **Errors**: Check `message` fields for failures.

**Screenshot Reference**: Browser showing JSON responses; terminal showing logs.
**Why?**
- Verifies webhook, polling, and Spaces integration using the session-based UUID.

### Step 2: Verify Webhook Functionality
**Action**: Simulate updates to trigger webhooks.

**Instructions**:
1. **Shopify**: Update a product’s title or inventory in the Shopify Admin (e.g., “The Complete Snowboard”).
2. **Facebook**: Update a page’s name or category in the Facebook interface (e.g., “Fast Online Store PH”).
3. Check server logs for webhook processing.

**Expected Output**:
- Shopify logs:
  ```
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Updated Snowboard'}}
  Updated data in Spaces for acme-7cu19ngr.myshopify.com via products/update
  ```
- Facebook logs:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  Updated data in Spaces for page 101368371725791
  ```

**Why?**
- Confirms `/shopify/webhook` and `/facebook/webhook` process events and upload to Spaces with the `users/` prefix.

### Step 3: Verify Polling Functionality
**Action**: Manually trigger daily polling.

**Instructions**:
1. Modify `app.py` to run polling immediately (temporary):
   ```python
   from facebook_integration.utils import daily_poll as facebook_daily_poll
   from shopify_integration.utils import daily_poll as shopify_daily_poll
   facebook_daily_poll()
   shopify_daily_poll()
   ```
2. Run: `python app.py`.
3. Check logs for polling results.

**Expected Output**:
- Shopify logs:
  ```
  Polled data for shop acme-7cu19ngr.myshopify.com: Success
  Polled and uploaded data for acme-7cu19ngr.myshopify.com: Success
  ```
- Facebook logs:
  ```
  Polled data for page 101368371725791: Success
  Polled and uploaded data for page 101368371725791: Success
  ```

**Why?**
- Confirms `poll_shopify_data` and `poll_facebook_data` retrieve data and upload to Spaces with the `users/` prefix.

### Step 4: Verify Spaces Storage
**Action**: Check the Spaces bucket for uploaded files.

**Instructions**:
1. Log into the DigitalOcean Control Panel and navigate to **Spaces > your_bucket_name**.
2. Verify files exist:
   - `users/<uuid>/shopify/shopify_data.json`
   - `users/<uuid>/facebook_messenger/101368371725791/page_data.json`
3. Download and confirm contents match the JSON responses from Step 1.

**Expected Content** (abridged):
- Shopify (`users/<uuid>/shopify/shopify_data.json`):
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
              ...
            }
          }
        ]
      }
    }
  }
  ```
- Facebook (`users/<uuid>/facebook_messenger/101368371725791/page_data.json`):
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

**Why?**
- Confirms data is stored in the UUID-based structure with the `users/` prefix in Spaces.

### Step 5: Troubleshoot Issues
**Action**: Diagnose and fix issues if JSON responses or logs show failures.

**Common Issues and Fixes**:
1. **Webhook Test Failure**:
   - **Cause**: Webhook registration or verification failed.
   - **Fix**:
     - Check `message` in `webhook_test`.
     - Verify `FACEBOOK_APP_SECRET`, `SHOPIFY_API_SECRET`, and webhook addresses in `.env`.
     - Ensure webhook addresses are accessible (use ngrok).
2. **Polling Test Failure**:
   - **Cause**: Failed to fetch data.
   - **Fix**:
     - Check `message` in `polling_test`.
     - Verify access tokens and UUIDs in the environment.
     - Check API error logs (e.g., HTTP 429).
3. **Upload Failure (`upload_status: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Spaces access issues.
   - **Fix**:
     - Verify `SPACES_*` variables in `.env` (Subchapter 6.3).
     - Check bucket permissions and region.
     - Ensure `boto3` is installed.
4. **Missing `session_id` Cookie**:
   - **Cause**: Shopify OAuth not completed.
   - **Fix**: Run `/shopify/acme-7cu19ngr/login`.
5. **Invalid or Expired Session**:
   - **Cause**: Session expired or invalid.
   - **Fix**: Re-run Shopify OAuth to set a new `session_id` cookie.
6. **Empty Data**:
   - **Cause**: Missing permissions or data.
   - **Fix**:
     - Ensure correct scopes and test data in Shopify/Facebook.
     - Verify admin access to pages and stores.

**Why?**
- Uses JSON responses and logs to debug integration issues.

### Summary: Why This Subchapter Matters
- **Storage Verification**: Confirms data is correctly uploaded to Spaces with the `users/` prefix.
- **UUID Integration**: Ensures data is organized by UUID for multi-platform linking.
- **Security**: Validates session-based UUID retrieval and non-sensitive data storage.
- **Bot Readiness**: Provides reliable data for customer interactions.

### Next Steps:
- Monitor logs for ongoing webhook and polling success.
- Explore additional platform integrations as needed.