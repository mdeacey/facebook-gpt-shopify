# Chapter 4: Facebook Data Sync
## Subchapter 4.3: Testing Facebook Webhooks and Polling

### Introduction
With the Facebook webhooks and polling systems set up in Subchapters 4.1 and 4.2, this subchapter verifies their functionality through integrated tests within the OAuth flow. After successful authentication, the FastAPI application automatically tests the webhook endpoint and polling mechanism for each authenticated page, using the UUID from the session-based mechanism (Chapter 3) to identify the user. Data is temporarily stored in a file-based structure (`facebook/<page_id>/page_data.json`), and tests return consistent JSON results to confirm functionality. This ensures the GPT Messenger sales bot can reliably fetch and process non-sensitive page metadata.

### Prerequisites
- Completed Chapters 1–3 (Facebook OAuth, Shopify OAuth, UUID/session management).
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) set in `.env`.
- `apscheduler` installed (`pip install apscheduler`).
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- Page access tokens (`FACEBOOK_ACCESS_TOKEN_<page_id>`) and UUID mappings (`PAGE_UUID_<page_id>`) stored in the environment.

---

### Step 1: Test via OAuth Flow
The tests for webhooks and polling are executed during the OAuth callback, using the session ID cookie to retrieve the UUID.

**Instructions**:
1. Run the app:
   ```bash
   python app.py
   ```
   or
   ```bash
   uvicorn app:app --reload
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
4. Log in to your Facebook account and authorize the `messenger-gpt-shopify` app, granting `pages_show_list` and `pages_manage_metadata` permissions.

**Expected Output**:
- The browser redirects to the callback endpoint, e.g.:
  ```
  http://localhost:5000/facebook/callback?code=<code>&state=1751277990%3AMhg1D2nYmAE%3A550e8400-e29b-41d4-a716-446655440000%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D#_=_
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
  INFO:     127.0.0.1:0 - "GET /facebook/login HTTP/1.1" 307 Temporary Redirect
  Webhook subscription for 'name,category' already exists for page 101368371725791
  Received webhook event for page test_page_id: {'id': 'test_page_id', 'changes': [{'field': 'name', 'value': 'Test Page'}]}
  INFO:     127.0.0.1:32930 - "POST /facebook/webhook HTTP/1.1" 200 OK
  Webhook test result: {'status': 'success'}
  Polling test result for page 101368371725791: {'status': 'success'}
  INFO:     127.0.0.1:0 - "GET /facebook/callback?code=...&state=1751524486%3AuVmqs9pr6gI%3A550e8400-e29b-41d4-a716-446655440000%3AuIVcMQV9UAqWPqQMndy-cWbi8913FNdQQLLi8_6v8_8%3D HTTP/1.1" 200 OK
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test: {"status": "success"}` indicates the webhook endpoint processed the test event.
- **Polling Success**: `polling_test: [{"page_id": "...", "result": {"status": "success"}}]` confirms polling retrieved data.
- **UUID**: `user_uuid` matches the Shopify OAuth response (Chapter 3).
- **Page Data**: `pages.data` includes non-sensitive fields without access tokens.
- **Errors**: If `webhook_test` or `polling_test` shows `{"status": "error", "message": "..."}`, check the `message`.

**Screenshot Reference**: Browser showing JSON response; terminal showing logs.
**Why?**
- Confirms webhook and polling functionality using the UUID from the session.
- Ensures non-sensitive data for the sales bot.

### Step 2: Verify Webhook Functionality
**Action**: Simulate a page metadata change to test the webhook endpoint.

**Instructions**:
1. In the Facebook interface, update the `name` or `category` of a page you manage (e.g., “Fast Online Store PH”).
2. Check server logs for webhook event processing.

**Expected Output**:
- Logs show:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  Wrote data to facebook/101368371725791/page_data.json for page 101368371725791
  ```

**Why?**
- Verifies the `/facebook/webhook` endpoint (Subchapter 4.1) processes `name` or `category` changes.
- Confirms data is stored in `facebook/<page_id>/page_data.json`.

### Step 3: Verify Polling Functionality
**Action**: Manually trigger the daily polling function.

**Instructions**:
1. Modify `app.py` to run `facebook_daily_poll` immediately (temporary):
   ```python
   from facebook_integration.utils import daily_poll as facebook_daily_poll
   facebook_daily_poll()  # Add this line
   ```
2. Run: `python app.py`.
3. Check logs for polling results.

**Expected Output**:
- Logs show:
  ```
  Polled data for page 101368371725791: Success
  Wrote data to facebook/101368371725791/page_data.json for page 101368371725791
  ```

**Why?**
- Confirms `poll_facebook_data` (Subchapter 4.2) retrieves data using the UUID.
- Ensures the daily poll works.

### Step 4: Verify Temporary File Storage
**Action**: Check the temporary file storage for page data.

**Instructions**:
1. Verify files exist in the project directory (e.g., `facebook/101368371725791/page_data.json`).
2. Open the file and confirm it matches the `pages` data from the JSON response.

**Expected Content** (example):
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

**Why?**
- Confirms data is stored correctly using the UUID-based structure, preparing for cloud storage in a later chapter.

### Step 5: Troubleshoot Issues
**Action**: If the JSON response or logs show failures, diagnose and fix issues.

**Common Issues and Fixes**:
1. **Webhook Test Failure (`webhook_test: {"status": "error", "message": "..."}`)**:
   - **Cause**: Webhook registration or verification failed.
   - **Fix**:
     - Check the `message` (e.g., HTTP 401 for HMAC issues).
     - Verify `FACEBOOK_APP_SECRET` and `FACEBOOK_VERIFY_TOKEN` in `.env`.
     - Ensure `FACEBOOK_WEBHOOK_ADDRESS` is accessible (use ngrok for local testing).
     - Check logs for `Webhook test result`.
2. **Polling Test Failure (`polling_test: [{"page_id": "...", "result": {"status": "error", "message": "..."}]`)**:
   - **Cause**: Failed to fetch page data.
   - **Fix**:
     - Check the `message` (e.g., “User access token not found”).
     - Verify `FACEBOOK_ACCESS_TOKEN_<page_id>` and `PAGE_UUID_<page_id>` in the environment.
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
     - Ensure `pages_show_list` and `pages_manage_metadata` are granted.
     - Confirm user has admin access to a business page and app is in Development Mode (Chapter 1).
6. **Missing Files**:
   - **Cause**: File writing failed.
   - **Fix**: Check write permissions in the project directory and logs for errors.

**Why?**
- Uses JSON responses and logs to debug webhook, polling, or session issues.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Tests confirm webhook and polling systems work, using the UUID from the session.
- **Security**: Excludes sensitive tokens and validates sessions.
- **Comprehensive Data**: Stores non-sensitive page metadata for the sales bot.
- **Bot Readiness**: Ensures up-to-date data for customer interactions.

### Next Steps:
- Proceed to Chapter 5 for Shopify data synchronization.
- Monitor logs to ensure ongoing test success.