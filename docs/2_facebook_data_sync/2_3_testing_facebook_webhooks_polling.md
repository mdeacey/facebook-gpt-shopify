# Subchapter 2.3: Testing Facebook Webhooks and Polling

## Introduction
With your Facebook webhooks and polling systems set up in Subchapters 2.1 and 2.2, this subchapter focuses on verifying their functionality through integrated tests within the OAuth flow. Upon successful authentication, your FastAPI application automatically tests both the webhook endpoint and the polling mechanism for each authenticated page, returning consistent JSON results to confirm everything works as expected.

## Prerequisites
- Completed Subchapters 2.1 and 2.2: Setting Up Facebook Webhooks and Polling.
- Your FastAPI application is running locally (e.g., `http://localhost:5000`).
- Facebook API credentials (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `FACEBOOK_WEBHOOK_ADDRESS`, `FACEBOOK_VERIFY_TOKEN`) are set in your `.env` file.
- `apscheduler` is installed (`pip install apscheduler`).
- Facebook access tokens for pages (e.g., `FACEBOOK_ACCESS_TOKEN_<page_id>`) are stored in the environment after OAuth, as set in Subchapter 2.1.

---

#### Step 1: Test via OAuth Flow
The tests for webhooks and polling are automatically executed during the OAuth callback. Follow these steps to initiate and verify the results.

**Instructions**:
1. Run your app: `python app.py` or `uvicorn app:app --reload`.
2. Initiate the OAuth flow by visiting:
   ```
   http://localhost:5000/facebook/login
   ```
3. Log in to your Facebook account and authorize the app, granting `pages_show_list` and `pages_manage_metadata` permissions.

**Expected Output**:
- The browser or terminal displays a JSON response, e.g.:
  ```json
  {
    "token_data": {
      "access_token": "your_access_token",
      "token_type": "bearer",
      "expires_in": 5184000
    },
    "pages": {
      "data": [
        {
          "id": "123456789",
          "name": "Test Page",
          "description": "A test page description",
          "category": "Retail",
          "access_token": "page_access_token"
        }
      ]
    },
    "webhook_test": {"status": "success"},
    "polling_test": [
      {
        "page_id": "123456789",
        "result": {"status": "success"}
      }
    ]
  }
  ```
- The logs should show (based on the structure from Subchapters 2.1 and 2.2):
  ```
  INFO:     127.0.0.1:0 - "GET /facebook/login HTTP/1.1" 307 Temporary Redirect
  Webhook subscription for 'name,description,category' already exists for page 123456789
  Received webhook event for page test_page_id: {'id': 'test_page_id', 'changes': [{'field': 'name', 'value': 'Test Page'}]}
  INFO:     127.0.0.1:32930 - "POST /facebook/webhook HTTP/1.1" 200 OK
  Webhook test result: {'status': 'success'}
  Polling test result for page 123456789: {'status': 'success'}
  INFO:     127.0.0.1:0 - "GET /facebook/callback?code=your_code&state=1751524486%3AuVmqs9pr6gI%3AuIVcMQV9UAqWPqQMndy-cWbi8913FNdQQLLi8_6v8_8%3D HTTP/1.1" 200 OK
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test` shows `{"status": "success"}`, indicating the webhook endpoint processed the test event correctly.
- **Polling Success**: `polling_test` contains an array of results, with each page’s `result` showing `{"status": "success"}`, confirming the polling function retrieved data successfully for each page.
- **Errors**: If `webhook_test` or any `polling_test` result shows `{"status": "error", "message": "..."}`, address issues (e.g., invalid `FACEBOOK_APP_SECRET`, missing access tokens, or network errors).

**Troubleshooting**:
- **No Response**: Ensure the app is running and `FACEBOOK_REDIRECT_URI` matches `http://localhost:5000/facebook/callback`.
- **401 Webhook Error**: Verify `FACEBOOK_APP_SECRET` in `.env` and ensure the test payload’s HMAC signature is computed correctly.
- **403 Webhook Verification Error**: Check that `FACEBOOK_VERIFY_TOKEN` matches the value set in `.env` and in your Facebook App’s webhook settings.
- **Polling Failure**: Confirm that access tokens (`FACEBOOK_ACCESS_TOKEN_<page_id>`) are stored in the environment and that the Facebook API is accessible (check for rate limits or permission issues).
- **Empty `pages` Data**: Ensure `pages_show_list` permission is granted in the OAuth flow.

---

#### Summary
This subchapter leverages integrated tests within the OAuth flow to verify webhook and polling functionality for Facebook pages. Completing authentication triggers both tests, returning consistent JSON results (`webhook_test` and `polling_test`) for validation, ensuring your sales bot can reliably fetch non-sensitive page metadata.

#### Next Steps
- Proceed to Subchapter 2.4 for integrating DigitalOcean Spaces or additional enhancements.
- Monitor logs regularly to ensure ongoing test success and data consistency.