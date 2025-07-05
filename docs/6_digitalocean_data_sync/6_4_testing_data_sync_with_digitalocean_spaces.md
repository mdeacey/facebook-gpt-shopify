# Chapter 6: DigitalOcean Integration
## Subchapter 6.4: Testing Data Sync with DigitalOcean Spaces

### Introduction
With Facebook and Shopify data sync updated to use DigitalOcean Spaces (Subchapters 6.1–6.2) and the bucket configured (Subchapter 6.3), this subchapter verifies that webhook and polling mechanisms correctly upload non-sensitive data to Spaces. For Facebook, we test uploads of page metadata (`users/<uuid>/facebook_messenger/<page_id>/page_data.json`) and conversation histories (`users/<uuid>/facebook_messenger/<page_id>/conversations/<sender_id>.json`). For Shopify, we test uploads of shop and product data (`users/<uuid>/shopify/<shop_name>/shopify_data.json`). Tests use the UUID from `TokenStorage` (Chapter 3) and verify new vs. continuing conversation handling, ensuring the GPT Messenger sales bot’s data is stored securely and scalably.

### Prerequisites
- Completed Chapters 1–5 and Subchapters 6.1–6.3.
- FastAPI application running on a DigitalOcean Droplet or locally (e.g., `http://localhost:5000`).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- DigitalOcean Spaces bucket (`gpt-messenger-data`) and credentials configured (Subchapter 6.3).
- Environment variables for Spaces, OAuth, and webhooks set in `.env` (Chapters 1–4, Subchapter 6.3).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- `boto3` installed (`pip install boto3`) for Spaces integration.

---

### Step 1: Test Facebook Data Sync via OAuth Flow
**Action**: Run the Facebook OAuth flow to test webhook and polling uploads to Spaces for metadata and conversations.

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
   or, for GitHub Codespaces:
   ```
   https://your-codespace-id-5000.app.github.dev/facebook/login
   ```
4. Log in to your Facebook account and authorize the `messenger-gpt-shopify` app, granting `pages_messaging`, `pages_show_list`, and `pages_manage_metadata` permissions.

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
          "category_list": [
            {
              "id": "109512302457693",
              "name": "Footwear store"
            }
          ],
          "about": "Your one-stop shop for premium footwear in the Philippines!",
          "website": "https://www.faststoreph.com",
          "link": "https://www.facebook.com/FastOnlineStorePH",
          "picture": {
            "data": {
              "url": "https://scontent.xx.fbcdn.net/v/.../profile.jpg"
            }
          },
          "fan_count": 1500,
          "verification_status": "verified",
          "location": {
            "city": "Manila",
            "country": "Philippines"
          },
          "phone": "+63 2 1234 5678",
          "email": "contact@faststoreph.com",
          "created_time": "2020-05-15T10:00:00+0000"
        }
      ],
      "paging": {
        "cursors": {
          "before": "QVFIUnp5enFBc21kckE2d1pud2g3Mjd1bEFSOUs4ZAEdSSEpIdHZAoSjVPdlgzVHN6aTZAReEpyOWdHMEF3MmJoRmpXNWI3dlFpa3BWLWoza2hMMDd4TzhMSUF3",
          "after": "QVFIUnp5enFBc21kckE2d1pud2g3Mjd1bEFSOUs4ZAEdSSEpIdHZAoSjVPdlgzVHN6aTZAReEpyOWdHMEF3MmJoRmpXNWI3dlFpa3BWLWoza2hMMDd4TzhMSUF3"
        }
      }
    },
    "webhook_test": [
      {
        "page_id": "101368371725791",
        "type": "metadata",
        "result": {"status": "success"}
      },
      {
        "page_id": "101368371725791",
        "type": "messages",
        "result": {"status": "success"}
      }
    ],
    "polling_test": [
      {
        "page_id": "101368371725791",
        "type": "metadata",
        "result": {"status": "success"}
      },
      {
        "page_id": "101368371725791",
        "type": "conversations",
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
- Server logs show:
  ```
  INFO:     127.0.0.1:0 - "GET /facebook/login HTTP/1.1" 307 Temporary Redirect
  Webhook subscription for 'name,category,messages' already exists for page 101368371725791
  Uploaded metadata to Spaces for page 101368371725791
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'Test Page'}]}
  Uploaded metadata to Spaces for page 101368371725791
  Metadata webhook test result for page 101368371725791: {'status': 'success'}
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  New conversation started for sender test_user_id on page 101368371725791
  Uploaded conversation payload to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/conversations/test_user_id.json (new: True)
  Message webhook test result for page 101368371725791: {'status': 'success'}
  Polled metadata for page 101368371725791: Success
  Metadata polling test result for page 101368371725791: {'status': 'success'}
  Polled conversations for page 101368371725791: Success
  Conversation polling test result for page 101368371725791: {'status': 'success'}
  Upload status verified for page 101368371725791: Success
  INFO:     127.0.0.1:0 - "GET /facebook/callback?code=...&state=... HTTP/1.1" 200 OK
  ```

**Why?**
- Confirms webhook and polling upload metadata and conversation payloads to Spaces using `TokenStorage`.
- Verifies new conversation handling for the message webhook test.
- Ensures `upload_status` confirms successful uploads.

### Step 2: Test Shopify Data Sync via OAuth Flow
**Action**: Run the Shopify OAuth flow to test webhook and polling uploads.

**Instructions**:
1. Run the app: `python app.py`.
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
                "description": "This PREMIUM snowboard is so SUPERDUPER awesome!",
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
- Unaffected by recent changes to Facebook data handling.

### Step 3: Verify Webhook Functionality
**Action**: Simulate updates to trigger webhooks.

**Instructions**:
1. **Facebook Metadata**: Update a page’s name or category in the Facebook interface (e.g., change “Fast Online Store PH” to “New Store Name”).
2. **Facebook Messages**: Send a test message to the connected page via Messenger (e.g., “Hello, I’m interested in snowboards”), followed by a second message (e.g., “Can you send the price list?”) to test continuing conversation handling.
3. **Shopify**: Update a product’s title or inventory in the Shopify Admin (e.g., change “The Complete Snowboard” title).
4. Check server logs for webhook event processing.

**Expected Output**:
- Facebook metadata logs:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  Uploaded metadata to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/page_data.json
  ```
- Facebook message logs (first message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  New conversation started for sender 123456789 on page 101368371725791
  Uploaded conversation payload to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/conversations/123456789.json (new: True)
  ```
- Facebook message logs (second message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  Continuing conversation for sender 123456789 on page 101368371725791
  Uploaded conversation payload to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/conversations/123456789.json (new: False)
  ```
- Shopify logs:
  ```
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Updated Snowboard'}}
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shopify_data.json
  ```

**Why?**
- Verifies webhook endpoints (Subchapters 4.1, 4.2, 5.1) upload to Spaces.
- Confirms new vs. continuing conversation handling for message webhooks.

### Step 4: Verify Polling Functionality
**Action**: Manually trigger daily polling for both platforms.

**Instructions**:
1. Modify `app.py` to run `facebook_daily_poll` and `shopify_daily_poll` immediately (temporary):
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
  Polled metadata for page 101368371725791: Success
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/page_data.json
  Polled conversations for page 101368371725791: Success
  New conversation polled for sender 123456789 on page 101368371725791
  Uploaded conversation payloads to Spaces: users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/conversations/123456789.json (new: True)
  ```
- Shopify logs:
  ```
  Polled data for shop acme-7cu19ngr.myshopify.com: Success
  Uploaded data to Spaces: users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shopify_data.json
  ```

**Why?**
- Confirms polling functions (Subchapters 4.3, 5.2) upload to Spaces, with `poll_facebook_data` using the updated signature.

### Step 5: Verify Spaces Storage
**Action**: Check the Spaces bucket for uploaded files.

**Instructions**:
1. In the DigitalOcean control panel, navigate to the Spaces bucket (`gpt-messenger-data`).
2. Verify files exist:
   - Metadata: `users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/page_data.json`
   - Conversations: `users/550e8400-e29b-41d4-a716-446655440000/facebook_messenger/101368371725791/conversations/123456789.json`
   - Shopify: `users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shopify_data.json`
3. Download and inspect files to confirm content matches OAuth responses.

**Expected Content** (abridged):
- Facebook metadata (`page_data.json`):
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
- Facebook conversations (`conversations/123456789.json`):
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
- Shopify (`shopify_data.json`):
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

**Why?**
- Confirms data is stored correctly in Spaces, organized by UUID.
- Verifies conversation files maintain the array-of-payloads structure from Subchapter 4.2.

### Step 6: Troubleshoot Issues
**Action**: Diagnose and fix issues if tests fail.

**Common Issues and Fixes**:
1. **Webhook Test Failure (`webhook_test: [{"page_id": "...", "type": "...", "result": {"status": "error", "message": "..."}]` or `webhook_test: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Webhook registration or verification failed.
   - **Fix**:
     - Check the `message` (e.g., HTTP 401 for HMAC issues).
     - Verify `FACEBOOK_WEBHOOK_ADDRESS`, `SHOPIFY_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`, `SHOPIFY_API_SECRET` in `.env`.
     - Ensure webhook addresses are accessible (use ngrok for local testing).
     - Check logs for `Webhook test result`.
2. **Polling Test Failure (`polling_test: [{"page_id": "...", "type": "...", "result": {"status": "error", "message": "..."}]` or `polling_test: {"status": "error", "message": "..."}`)**:
   - **Cause**: Failed to fetch data or upload to Spaces.
   - **Fix**:
     - Check the `message` (e.g., “User access token not found” or “Conversation fetch failed”).
     - Verify tokens in `tokens.db` using `sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"`.
     - Check logs for API errors (e.g., HTTP 400 or 429).
3. **Upload Status Failure (`upload_status: [{"page_id": "...", "result": {"status": "failed", "message": "..."}]`)**:
   - **Cause**: Upload verification failed.
   - **Fix**: Verify `SPACES_API_KEY`, `SPACES_API_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`, `SPACES_ENDPOINT` in `.env`; check Spaces bucket for files.
4. **Missing `session_id` Cookie**:
   - **Cause**: Shopify OAuth not completed.
   - **Fix**: Run `/shopify/acme-7cu19ngr/login` to set the cookie.
5. **Empty Data**:
   - **Cause**: Missing permissions or test data.
   - **Fix**: Ensure `pages_messaging`, `pages_show_list`, `pages_manage_metadata` (Facebook) and `read_products`, etc. (Shopify) are granted; confirm test data exists (Chapters 1–2).
6. **CORS Errors**:
   - **Cause**: Spaces bucket misconfigured.
   - **Fix**: Verify CORS settings in Spaces (Subchapter 6.3) and `app.py`.

**Why?**
- Uses logs and JSON responses to debug webhook, polling, or Spaces issues.
- Ensures conversation data is correctly uploaded and retrievable.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Confirms webhook and polling systems upload metadata, conversations, and Shopify data to Spaces.
- **Conversation Tracking**: Verifies new vs. continuing conversation handling in webhook and polling uploads.
- **Security**: Uses `TokenStorage`, excludes sensitive data, and ensures private ACLs.
- **Scalability**: Ensures persistent, UUID-organized storage for production.
- **Bot Readiness**: Provides up-to-date data for customer interactions.

### Next Steps:
- Proceed to Chapter 7 for data backup and recovery.
- Monitor Spaces uploads for ongoing reliability.