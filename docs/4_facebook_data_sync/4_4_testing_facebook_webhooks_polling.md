# Chapter 4: Facebook Data Sync
## Subchapter 4.4: Testing Facebook Webhooks and Polling

### Introduction
With Facebook webhooks and polling set up in Subchapters 4.1–4.3, this subchapter verifies their functionality through integrated tests within the OAuth flow. After successful authentication, the FastAPI application tests the webhook endpoint and polling mechanism for each authenticated page, covering both metadata (`name`, `category`) and message events, using the UUID from the SQLite-based session mechanism (Chapter 3) to identify the user. Data is stored in temporary files (`facebook/<page_id>/page_metadata.json` for metadata and `facebook/<page_id>/conversations/<sender_id>.json` for conversation payloads), and tests confirm new vs. continuing conversation handling. The tests return consistent JSON results to ensure the GPT Messenger sales bot reliably processes and stores non-sensitive data using `TokenStorage` and `SessionStorage`. The `facebook` directory reflects both metadata and messaging, aligning with the final structure in Chapter 6 (`users/<uuid>/facebook/<page_id>/...`).

### Prerequisites
- Completed Chapters 1–3 (Facebook OAuth, Shopify OAuth, Persistent Storage and User Identification) and Subchapters 4.1–4.3.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) and `STATE_TOKEN_SECRET` set in `.env` (Chapter 1, Subchapter 4.1).
- `apscheduler` installed (`pip install apscheduler`) from Subchapter 4.3.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Permissions `pages_messaging`, `pages_show_list`, and `pages_manage_metadata` configured in the Meta Developer Portal (Chapter 1, Subchapter 4.2).

---

### Step 1: Test via OAuth Flow
The tests for webhooks and polling are executed during the OAuth callback, using the `session_id` cookie to retrieve the UUID.

**Instructions**:
1. Run the app:
   ```bash
   python app.py
   ```
2. Complete Shopify OAuth (Chapter 2) to set the `session_id` cookie:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
3. Initiate the Facebook OAuth flow:
   ```
   http://localhost:5000/facebook/login
   ```
   or, for GitHub Codespaces:
   ```
   https://your-codespace-id-5000.app.github.dev/facebook/login
   ```
4. Log in to your Facebook account and authorize the `messenger-gpt-shopify` app, granting `pages_messaging`, `pages_show_list`, and `pages_manage_metadata` permissions.

**Expected Output**:
- The browser redirects to the callback endpoint, e.g.:
  ```
  http://localhost:5000/facebook/callback?code=AQDqeAxEI53Puc9Sv31VbkK2JwbJRKDp9vDNG99cC9mSLVDot4ahBkGVMmRYwFhQ42VzO9kYlnrHbbOiz_o_odW6wOEY-rSoDObi0QJMu4NGJeBRDIIFdfvHEGXlbsRZ-eGWHu5hQt2h1xGpgMiwFNp4jCp7I_zsargoTNW3RBC2ueKPw694UOAUenRP7jszrjQgMID_2fhuZKi7uyh3M2pykWYS7i3K71nkAmU4kFawAOzvI3_jZtpoJA9DiaeXqtOQpzOIMG4w5-HNd-bMnvz_br10_Gon08Xh7vDiFr3Ug1owSiwphEZ-_wuEGZ2D694vvBBwWv2GzNa5IWl-79zzJME7slwQ0Hw9ob8dm1f33h-CsZnbUf4F3Kjma2qI8ZI&state=1751277990%3AMhg1D2nYmAE%3A550e8400-e29b-41d4-a716-446655440000%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D#_=_
  ```
- The browser displays a JSON response:
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
    ]
  }
  ```
- Server logs show:
  ```
  INFO:     127.0.0.1:0 - "GET /facebook/login HTTP/1.1" 307 Temporary Redirect
  Webhook subscription for 'name,category,messages' already exists for page 101368371725791
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'Test Page'}]}
  Wrote metadata to facebook/101368371725791/page_metadata.json for page 101368371725791
  Metadata webhook test result for page 101368371725791: {'status': 'success'}
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  New conversation started for sender test_user_id on page 101368371725791
  Wrote conversation payload to facebook/101368371725791/conversations/test_user_id.json for sender test_user_id on page 101368371725791 (new: True)
  Message webhook test result for page 101368371725791: {'status': 'success'}
  Metadata polling test result for page 101368371725791: {'status': 'success'}
  Conversation polling test result for page 101368371725791: {'status': 'success'}
  INFO:     127.0.0.1:0 - "GET /facebook/callback?code=...&state=... HTTP/1.1" 200 OK
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test` includes `metadata` and `messages` entries with `{"status": "success"}`, confirming both webhook types work.
- **Polling Success**: `polling_test` includes `metadata` and `conversations` entries with `{"status": "success"}`, confirming polling functionality.
- **UUID**: `user_uuid` matches the Shopify OAuth response (Chapter 3).
- **Page Data**: `pages.data` includes non-sensitive fields without access tokens.
- **Conversation Tracking**: Logs indicate “New conversation started” for the test message.
- **Errors**: If `webhook_test` or `polling_test` shows `{"status": "error", "message": "..."}`, check the `message` for details.

**Screenshot Reference**: Browser showing JSON response; terminal showing logs.

**Why?**
- Confirms webhook and polling functionality for both metadata and messages using `TokenStorage` and `SessionStorage`.
- Verifies new conversation handling in the message webhook test.
- Ensures non-sensitive data storage in `facebook/<page_id>/page_metadata.json` and `facebook/<page_id>/conversations/<sender_id>.json` for the sales bot, preparing for Spaces (`users/<uuid>/facebook/<page_id>/...`) in Chapter 6.

### Step 2: Verify Webhook Functionality
**Action**: Simulate metadata and message events to test the webhook endpoint.

**Instructions**:
1. **Metadata Webhook**:
   - In the Facebook interface, update the `name` or `category` of a page you manage (e.g., “Fast Online Store PH”).
   - Check server logs for webhook event processing.
2. **Message Webhook**:
   - Send a test message to the connected page via Messenger (e.g., “Hello, I’m interested in snowboards”).
   - Send a second message from the same user (e.g., “Can you send the price list?”) to test continuing conversation handling.
   - Check server logs for new vs. continuing conversation processing.

**Expected Output**:
- Metadata webhook logs:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  Wrote metadata to facebook/101368371725791/page_metadata.json for page 101368371725791
  ```
- Message webhook logs (first message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  New conversation started for sender 123456789 on page 101368371725791
  Wrote conversation payload to facebook/101368371725791/conversations/123456789.json for sender 123456789 on page 101368371725791 (new: True)
  ```
- Message webhook logs (second message):
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  Continuing conversation for sender 123456789 on page 101368371725791
  Wrote conversation payload to facebook/101368371725791/conversations/123456789.json for sender 123456789 on page 101368371725791 (new: False)
  ```

**Why?**
- Verifies the `/facebook/webhook` endpoint (Subchapters 4.1–4.2) processes `name,category` and `messages` events using `TokenStorage`.
- Confirms new vs. continuing conversation handling via file existence checks.
- Ensures data is stored in temporary files (`facebook/<page_id>/page_metadata.json` and `facebook/<page_id>/conversations/<sender_id>.json`).

### Step 3: Verify Polling Functionality
**Action**: Manually trigger the daily polling function to test metadata and conversation polling.

**Instructions**:
1. Modify `app.py` to run `daily_poll` immediately (temporary):
   ```python
   from facebook_integration.utils import daily_poll
   daily_poll()  # Add this line
   ```
2. Run: `python app.py`.
3. Check logs for polling results.

**Expected Output**:
- Logs show:
  ```
  Polled metadata for page 101368371725791: Success
  Wrote metadata to facebook/101368371725791/page_metadata.json for page 101368371725791
  Polled conversations for page 101368371725791: Success
  New conversation polled for sender 123456789 on page 101368371725791
  Wrote conversation payloads to facebook/101368371725791/conversations/123456789.json for sender 123456789 on page 101368371725791 (new: True)
  ```

**Why?**
- Confirms `poll_facebook_data` and `poll_facebook_conversations` (Subchapter 4.3) retrieve data using `TokenStorage`.
- Verifies new vs. continuing conversation handling in polling.
- Ensures the daily poll works with temporary file storage (`facebook/<page_id>/...`).

### Step 4: Verify Temporary File Storage
**Action**: Check the temporary file storage for metadata and conversation data.

**Instructions**:
1. Verify files exist in the project directory:
   - Metadata: `facebook/101368371725791/page_metadata.json`
   - Conversations: `facebook/101368371725791/conversations/123456789.json`
2. Open the files and confirm their contents.

**Expected Content**:
- Metadata (`facebook/101368371725791/page_metadata.json`):
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
- Conversations (`facebook/101368371725791/conversations/123456789.json`):
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

**Why?**
- Confirms data is stored correctly in temporary files (`facebook/<page_id>/page_metadata.json` and `facebook/<page_id>/conversations/<sender_id>.json`), consistent with Subchapters 4.1–4.3.
- Verifies conversation payloads are arrays of raw `messaging` events, with new messages appended correctly, preparing for Spaces in Chapter 6.

### Step 5: Troubleshoot Issues
**Action**: If the JSON response or logs show failures, diagnose and fix issues.

**Common Issues and Fixes**:
1. **Webhook Test Failure (`webhook_test: [{"page_id": "...", "type": "...", "result": {"status": "error", "message": "..."}]`)**:
   - **Cause**: Webhook registration or verification failed.
   - **Fix**:
     - Check the `message` (e.g., HTTP 401 for HMAC issues).
     - Verify `FACEBOOK_APP_SECRET` and `FACEBOOK_VERIFY_TOKEN` in `.env`.
     - Ensure `FACEBOOK_WEBHOOK_ADDRESS` is accessible (use ngrok for local testing).
     - Check logs for `Webhook test result`.
2. **Polling Test Failure (`polling_test: [{"page_id": "...", "type": "...", "result": {"status": "error", "message": "..."}]`)**:
   - **Cause**: Failed to fetch metadata or conversations.
   - **Fix**:
     - Check the `message` (e.g., “User access token not found” or “Conversation fetch failed”).
     - Verify tokens in `tokens.db` using `sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"`.
     - Check logs for API errors (e.g., HTTP 400 or 429).
3. **Missing `session_id` Cookie**:
   - **Cause**: Shopify OAuth (Chapter 2) not completed.
   - **Fix**: Run `/shopify/acme-7cu19ngr/login` to set the cookie.
4. **Invalid or Expired Session**:
   - **Cause**: Session expired or invalid.
   - **Fix**: Re-run Shopify OAuth to set a new `session_id` cookie.
5. **Empty `pages` Data**:
   - **Cause**: No pages or missing permissions.
   - **Fix**:
     - Ensure `pages_show_list`, `pages_messaging`, and `pages_manage_metadata` are granted.
     - Confirm user has admin access to a business page and app is in Development Mode (Chapter 1).
6. **Missing Files**:
   - **Cause**: File writing failed.
   - **Fix**: Check write permissions in the project directory and logs for errors.

**Why?**
- Uses JSON responses and logs to debug webhook, polling, or session issues.
- Ensures new vs. continuing conversation handling is verified in `facebook/<page_id>/conversations/<sender_id>.json`.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Tests confirm webhook and polling systems work for metadata and messages, using `TokenStorage` and `SessionStorage`.
- **Conversation Tracking**: Verifies new vs. continuing conversation handling via file existence checks.
- **Security**: Excludes sensitive tokens, validates sessions, and uses encrypted storage.
- **Comprehensive Data**: Stores non-sensitive metadata (`page_metadata.json`) and full conversation payloads for the sales bot.
- **Bot Readiness**: Ensures up-to-date data for customer interactions, preparing for Spaces (`users/<uuid>/facebook/<page_id>/...`) in Chapter 6.

### Next Steps:
- Proceed to Chapter 5 for Shopify data synchronization.
- Monitor logs to ensure ongoing test success.