# Chapter 6: DigitalOcean Integration
## Subchapter 6.4: Testing Data Sync with DigitalOcean Spaces

### Introduction
With Facebook and Shopify data now stored in DigitalOcean Spaces (Subchapters 6.1–6.2), this subchapter verifies the webhook and polling mechanisms for both platforms, ensuring data is correctly uploaded to Spaces in the structure `users/<uuid>/facebook/<page_id>/page_metadata.json`, `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`, `users/<uuid>/shopify/<shop_name>/shop_metadata.json`, and `users/<uuid>/shopify/<shop_name>/shop_products.json`. Tests are integrated into the OAuth flows, using the SQLite-based `TokenStorage` and `SessionStorage` (Chapter 3) to retrieve UUIDs and tokens. The tests confirm non-sensitive data storage, new vs. continuing conversation handling for Facebook, and split Shopify data storage, ensuring the GPT Messenger sales bot has reliable, cloud-based data for customer interactions.

### Prerequisites
- Completed Chapters 1–5 and Subchapters 6.1–6.2.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- DigitalOcean Spaces credentials (`SPACES_KEY`, `SPACES_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`) set in `.env` (Subchapter 6.1).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) and Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Permissions configured for Facebook (`pages_messaging`, `pages_show_list`, `pages_manage_metadata`) and Shopify (`read_product_listings`, `read_inventory`, `read_discounts`, `read_locations`, `read_products`).

---

### Step 1: Test Facebook OAuth Flow
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
4. Log in to your Facebook account and authorize the app.

**Expected Output**:
- The browser displays a JSON response (same as Subchapter 4.4, with `webhook_test` and `polling_test` results).
- Server logs show:
  ```
  Webhook subscription for 'name,category,messages' already exists for page 101368371725791
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json to Spaces
  Metadata webhook test result for page 101368371725791: {'status': 'success'}
  New conversation started for sender test_user_id on page 101368371725791
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/test_user_id.json to Spaces
  Message webhook test result for page 101368371725791: {'status': 'success'}
  Metadata polling test result for page 101368371725791: {'status': 'success'}
  Conversation polling test result for page 101368371725791: {'status': 'success'}
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test` shows `{"status": "success"}` for `metadata` and `messages`.
- **Polling Success**: `polling_test` shows `{"status": "success"}` for `metadata` and `conversations`.
- **Conversation Tracking**: Logs indicate “New conversation started” for the test message.
- **Spaces Uploads**: Logs confirm uploads to `users/<uuid>/facebook/<page_id>/page_metadata.json` and `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`.

**Why?**
- Verifies webhook and polling uploads to Spaces for Facebook data, using the renamed `facebook` directory and `page_metadata.json`.

### Step 2: Test Shopify OAuth Flow
**Action**: Run the Shopify OAuth flow to test webhook and polling uploads to Spaces.

**Instructions**:
1. Run the app (if not already running).
2. Initiate Shopify OAuth:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
3. Log in to your Shopify store and authorize the app.

**Expected Output**:
- The browser displays a JSON response (same as Subchapter 5.3, with `webhook_test` and `polling_test` results).
- Server logs show:
  ```
  Webhook registered for acme-7cu19ngr.myshopify.com: products/update
  Uploaded data to users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json and users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  Polling test result for acme-7cu19ngr.myshopify.com: Success
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test: {"status": "success"}` confirms the webhook endpoint works.
- **Polling Success**: `polling_test: {"status": "success"}` confirms polling functionality.
- **Spaces Uploads**: Logs confirm uploads to `users/<uuid>/shopify/<shop_name>/shop_metadata.json` and `users/<uuid>/shopify/<shop_name>/shop_products.json`.

**Why?**
- Verifies webhook and polling uploads to Spaces for Shopify data, using the split file structure.

### Step 3: Verify Webhook Functionality
**Action**: Simulate webhook events for both platforms to test Spaces uploads.

**Instructions**:
1. **Facebook Webhooks**:
   - Update the `name` or `category` of a connected page in the Facebook interface.
   - Send a test message to the page via Messenger (e.g., “Hello, I’m interested in snowboards”).
   - Send a second message from the same user to test continuing conversation handling.
2. **Shopify Webhooks**:
   - Update a product in Shopify Admin (e.g., change “Premium Snowboard” to “Premium Snowboard Pro”).
3. Check server logs for webhook processing and Spaces uploads.

**Expected Output**:
- Facebook metadata webhook:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json to Spaces
  ```
- Facebook message webhook (first message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  New conversation started for sender 123456789 on page 101368371725791
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json to Spaces
  ```
- Facebook message webhook (second message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  Continuing conversation for sender 123456789 on page 101368371725791
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json to Spaces
  ```
- Shopify webhook:
  ```
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Premium Snowboard Pro'}}
  Uploaded data to users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json and users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Confirms webhook endpoints for both platforms upload data to Spaces.
- Verifies new vs. continuing conversation handling for Facebook.
- Ensures Shopify data is split into `shop_metadata.json` and `shop_products.json`.

### Step 4: Verify Polling Functionality
**Action**: Manually trigger polling for both platforms to test Spaces uploads.

**Instructions**:
1. Modify `app.py` to run `facebook_daily_poll` and `shopify_daily_poll` immediately (temporary):
   ```python
   from facebook_integration.utils import daily_poll as facebook_daily_poll
   from shopify_integration.utils import daily_poll as shopify_daily_poll
   facebook_daily_poll()
   shopify_daily_poll()
   ```
2. Run: `python app.py`.
3. Check logs for polling results and Spaces uploads.

**Expected Output**:
- Facebook polling:
  ```
  Polled metadata for page 101368371725791: Success
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json to Spaces
  Polled conversations for page 101368371725791: Success
  New conversation polled for sender 123456789 on page 101368371725791
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json to Spaces
  ```
- Shopify polling:
  ```
  Uploaded data to users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json and users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Confirms polling uploads data to Spaces for both platforms.
- Verifies new vs. continuing conversation handling for Facebook.
- Ensures Shopify data is split correctly.

### Step 5: Verify Spaces Storage
**Action**: Check the DigitalOcean Spaces bucket for uploaded files.

**Instructions**:
1. Log into your DigitalOcean account and navigate to **Spaces**.
2. Open the bucket specified in `SPACES_BUCKET`.
3. Verify the presence and contents of:
   - `users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json`
   - `users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json`
   - `users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json`
   - `users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json`

**Expected Content**:
- Facebook metadata (`users/.../facebook/101368371725791/page_metadata.json`):
  ```json
  {
    "data": [
      {
        "id": "101368371725791",
        "name": "Fast Online Store PH",
        "category": "Footwear store",
        ...
      }
    ],
    "paging": {...}
  }
  ```
- Facebook conversations (`users/.../facebook/101368371725791/conversations/123456789.json`):
  ```json
  [
    {
      "sender": {"id": "123456789"},
      "recipient": {"id": "101368371725791"},
      "timestamp": 1697051234567,
      "message": {"mid": "m_abc123", "text": "Hello, I'm interested in snowboards"}
    },
    {
      "sender": {"id": "123456789"},
      "recipient": {"id": "101368371725791"},
      "timestamp": 1697051250000,
      "message": {"mid": "m_def456", "text": "Can you send the price list?"}
    }
  ]
  ```
- Shopify metadata (`users/.../shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json`):
  ```json
  {
    "data": {
      "shop": {
        "name": "Acme Snowboards",
        "primaryDomain": {
          "url": "https://acme-7cu19ngr.myshopify.com"
        }
      }
    }
  }
  ```
- Shopify products (`users/.../shopify/acme-7cu19ngr.myshopify.com/shop_products.json`):
  ```json
  {
    "data": {
      "products": {
        "edges": [
          {
            "node": {
              "title": "Premium Snowboard",
              "description": "High-quality snowboard for all levels",
              ...
            }
          }
        ],
        "pageInfo": {
          "hasNextPage": false,
          "endCursor": null
        }
      },
      "codeDiscountNodes": {...},
      "collections": {...}
    }
  }
  ```

**Why?**
- Confirms data is correctly uploaded to Spaces with the updated path structure.
- Verifies split Shopify data and Facebook conversation payloads.

### Step 6: Troubleshoot Issues
**Action**: If logs show failures, diagnose and fix issues.

**Common Issues and Fixes**:
1. **Webhook Test Failure**:
   - **Cause**: Webhook registration or HMAC verification failed.
   - **Fix**: Check logs for errors (e.g., HTTP 401). Verify `FACEBOOK_APP_SECRET`, `SHOPIFY_API_SECRET`, and webhook addresses in `.env`. Ensure webhook URLs are accessible.
2. **Polling Test Failure**:
   - **Cause**: Failed to fetch or upload data.
   - **Fix**: Check logs for API errors (e.g., HTTP 429). Verify tokens in `tokens.db` using `sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"`.
3. **Spaces Upload Failure**:
   - **Cause**: Invalid Spaces credentials or bucket misconfiguration.
   - **Fix**: Verify `SPACES_KEY`, `SPACES_SECRET`, `SPACES_REGION`, and `SPACES_BUCKET`. Check bucket permissions in DigitalOcean.
4. **Missing Files in Spaces**:
   - **Cause**: Uploads failed silently.
   - **Fix**: Check logs for `boto3` errors. Ensure the bucket exists and is accessible.

**Why?**
- Uses logs to debug webhook, polling, or Spaces issues.
- Ensures correct storage paths and data formats.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Confirms webhook and polling systems upload data to Spaces for both platforms.
- **Path Structure**: Verifies `users/<uuid>/facebook/...` and `users/<uuid>/shopify/...` paths, with renamed `facebook` directory and split Shopify files.
- **Conversation Tracking**: Ensures new vs. continuing conversation handling for Facebook.
- **Security**: Excludes sensitive data and uses private ACL.
- **Bot Readiness**: Provides reliable cloud storage for customer interactions.

### Next Steps:
- Implement data backup and recovery (Chapter 7).
- Monitor logs for ongoing test success.