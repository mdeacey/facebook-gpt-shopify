# Chapter 2: Facebook Data Sync
## Subchapter 2.3: Testing Facebook Webhooks and Polling

### Introduction
With your Facebook webhooks and polling systems set up in Subchapters 2.1 and 2.2, this subchapter focuses on verifying their functionality through integrated tests within the OAuth flow. Upon successful authentication, your FastAPI application automatically tests both the webhook endpoint and the polling mechanism for each authenticated page, returning consistent JSON results with non-sensitive page data to confirm everything works as expected. This ensures the GPT Messenger sales bot can reliably fetch and process page metadata without exposing sensitive tokens.

### Prerequisites
- Completed Subchapters 2.1 and 2.2: Setting Up Facebook Webhooks and Polling.
- Your FastAPI application is running locally (e.g., `http://localhost:5000`) or in a production-like environment (e.g., GitHub Codespaces).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) are set in your `.env` file.
- `apscheduler` is installed (`pip install apscheduler`).
- Facebook access tokens for pages (e.g., `FACEBOOK_ACCESS_TOKEN_<page_id>`) and the user access token (`FACEBOOK_USER_ACCESS_TOKEN`) are stored in the environment after OAuth, as set in Subchapter 2.1.

---

### Step 1: Test via OAuth Flow
The tests for webhooks and polling are automatically executed during the OAuth callback. Follow these steps to initiate and verify the results.

**Instructions**:
1. Run your app:
   ```bash
   python app.py
   ```
   or
   ```bash
   uvicorn app:app --reload
   ```
2. Initiate the OAuth flow by visiting:
   ```
   http://localhost:5000/facebook/login
   ```
   or, for GitHub Codespaces:
   ```
   https://your-codespace-id-5000.app.github.dev/facebook/login
   ```
3. Log in to your Facebook account and authorize the `messenger-gpt-shopify` app, granting `pages_show_list` and `pages_manage_metadata` permissions.

**Expected Output**:
- The browser redirects to the callback endpoint, e.g.:
  ```
  http://localhost:5000/facebook/callback?code=<code>&state=<state>
  ```
  or, for Codespaces:
  ```
  https://your-codespace-id-5000.app.github.dev/facebook/callback?code=AQDqeAxEI53Puc9Sv31VbkK2JwbJRKDp9vDNG99cC9mSLVDot4ahBkGVMmRYwFhQ42VzO9kYlnrHbbOiz_o_odW6wOEY-rSoDObi0QJMu4NGJeBRDIIFdfvHEGXlbsRZ-eGWHu5hQt2h1xGpgMiwFNp4jCp7I_zsargoTNW3RBC2ueKPw694UOAUenRP7jszrjQgMID_2fhuZKi7uyh3M2pykWYS7i3K71nkAmU4kFawAOzvI3_jZtpoJA9DiaeXqtOQpzOIMG4w5-HNd-bMnvz_br10_Gon08Xh7vDiFr3Ug1owSiwphEZ-_wuEGZ2D694vvBBwWv2GzNa5IWl-79zzJME7slwQ0Hw9ob8dm1f33h-CsZnbUf4F3Kjma2qI8ZI&state=1751277990%3AMhg1D2nYmAE%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D#_=_
  ```
- The browser displays a JSON response, e.g.:
  ```json
  {
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
- Server logs show successful requests and test results, e.g.:
  ```
  INFO:     127.0.0.1:0 - "GET /facebook/login HTTP/1.1" 307 Temporary Redirect
  Webhook subscription for 'name,category' already exists for page 101368371725791
  Received webhook event for page test_page_id: {'id': 'test_page_id', 'changes': [{'field': 'name', 'value': 'Test Page'}]}
  INFO:     127.0.0.1:32930 - "POST /facebook/webhook HTTP/1.1" 200 OK
  Webhook test result: {'status': 'success'}
  Polling test result for page 101368371725791: {'status': 'success'}
  INFO:     127.0.0.1:0 - "GET /facebook/callback?code=...&state=1751524486%3AuVmqs9pr6gI%3AuIVcMQV9UAqWPqQMndy-cWbi8913FNdQQLLi8_6v8_8%3D HTTP/1.1" 200 OK
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test: {"status": "success"}` indicates the webhook endpoint processed the test event correctly.
- **Polling Success**: `polling_test: [{"page_id": "...", "result": {"status": "success"}}]` confirms the polling function retrieved data successfully for each page.
- **Page Data**: `pages.data` includes non-sensitive fields (`id`, `name`, `category`, `about`, `website`, `link`, `picture`, `fan_count`, `verification_status`, `location`, `phone`, `email`, `created_time`) without access tokens.
- **Errors**: If `webhook_test` or any `polling_test` result shows `{"status": "error", "message": "..."}`, address issues using the `message` field (e.g., invalid `FACEBOOK_APP_SECRET`, missing access tokens, or network errors).

**Screenshot Reference**: Browser showing the JSON response with `pages`, `webhook_test`, and `polling_test`; terminal showing logs with test results.

**Why?**
- The OAuth callback triggers automatic tests for webhooks and polling, ensuring both systems are functional.
- The JSON response confirms successful data retrieval and test execution without exposing sensitive tokens.
- Comprehensive page data supports the sales bot’s functionality (e.g., displaying page details or contact info).

### Step 2: Verify Webhook Functionality
**Action**: Simulate a page metadata change to test the webhook endpoint.

**Instructions**:
1. In the Facebook interface, update the `name` or `category` of a page you manage (e.g., “Fast Online Store PH”).
2. Check server logs for webhook event processing.

**Expected Output**:
- Logs show the webhook event, e.g.:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  ```

**Why?**
- Verifies that the `/facebook/webhook` endpoint (Subchapter 2.1) receives and logs real-time events for `name` or `category` changes.
- Ensures HMAC verification (`verify_webhook`) is working correctly.

### Step 3: Verify Polling Functionality
**Action**: Manually trigger the daily polling function to test data retrieval.

**Instructions**:
1. Temporarily modify `app.py` to run `facebook_daily_poll` immediately (for testing):
   ```python
   from facebook_oauth.utils import daily_poll as facebook_daily_poll
   facebook_daily_poll()  # Add this line temporarily
   ```
2. Run the app: `python app.py`.
3. Check logs for polling results.

**Expected Output**:
- Logs show successful polling for each page, e.g.:
  ```
  Polled data for page 101368371725791: Success
  ```

**Why?**
- Confirms that `poll_facebook_data` (Subchapter 2.2) retrieves page data using the user access token.
- Ensures the `daily_poll` scheduler will work at midnight.

### Step 4: Troubleshoot Issues
**Action**: If the JSON response or logs show failures, use these steps to diagnose and fix issues.

**Common Issues and Fixes**:
1. **Webhook Test Failure (`webhook_test: {"status": "error", "message": "..."}`)**:
   - **Cause**: Webhook registration, test, or verification failed (e.g., invalid `FACEBOOK_APP_SECRET`, `FACEBOOK_VERIFY_TOKEN`).
   - **Fix**:
     - Check the `message` in the response (e.g., HTTP 401 for HMAC issues, 403 for token mismatch).
     - Verify `FACEBOOK_APP_SECRET` and `FACEBOOK_VERIFY_TOKEN` in `.env`.
     - Ensure `FACEBOOK_WEBHOOK_ADDRESS` (`http://localhost:5000/facebook/webhook`) is accessible (use ngrok for local testing).
     - Check logs for `Webhook test result`.

2. **Polling Test Failure (`polling_test: [{"page_id": "...", "result": {"status": "error", "message": "..."}]`)**:
   - **Cause**: Failed to fetch page data (e.g., invalid user access token, API rate limits).
   - **Fix**:
     - Check the `message` for each page in the response (e.g., “User access token not found”).
     - Verify `FACEBOOK_USER_ACCESS_TOKEN` and `FACEBOOK_ACCESS_TOKEN_<page_id>` in the environment.
     - Ensure `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` are correct.
     - Check logs for API errors (e.g., HTTP 400 or 429).

3. **Empty `pages` Data**:
   - **Cause**: No pages returned or permissions missing.
   - **Fix**:
     - Ensure `pages_show_list` and `pages_manage_metadata` are granted in the OAuth flow.
     - Confirm the user has admin access to a business page and the app is in Development Mode (Subchapter 1.2).
     - If in Live Mode, verify permissions are approved by Meta.

4. **Missing Page Fields (e.g., `email`, `phone`)**:
   - **Cause**: Fields may be null if not set for the page.
   - **Fix**: Update the page’s settings in the Facebook interface to include `email`, `phone`, or other fields.

5. **Response Not Visible**:
   - **Cause**: Browser rendering or outdated code.
   - **Fix**:
     - Refresh the browser or clear cache.
     - Verify `facebook_oauth/routes.py` matches the code in Subchapter 2.2.
     - Check logs for errors rendering the response.

**Why?**
- These steps use the JSON response and logs to identify issues with webhook or polling functionality, ensuring robust testing.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Integrated tests within the OAuth flow confirm webhook and polling systems work, returning non-sensitive page data.
- **Security**: Excludes user and page access tokens from the response, enhancing security.
- **Comprehensive Data**: Includes extensive page metadata (`id`, `name`, `category`, `about`, etc.) for the sales bot.
- **Bot Readiness**: Ensures the bot can access up-to-date page data for customer interactions.

### Next Steps:
- Proceed to Shopify integration (Chapter 3) for product data.
- Monitor logs regularly to ensure ongoing test success and data consistency.