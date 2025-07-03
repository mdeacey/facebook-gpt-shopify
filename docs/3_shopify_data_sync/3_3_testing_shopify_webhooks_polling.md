# Subchapter 1.3: Tests

## Introduction
With your Shopify webhooks and polling systems set up in Subchapters 1.1 and 1.2, this subchapter focuses on verifying their functionality through the integrated testing process within the OAuth flow. Upon successful authentication, your FastAPI application automatically tests both the webhook endpoint and the polling mechanism, returning consistent JSON results to confirm everything works as expected.

## Prerequisites
- Your FastAPI application from Subchapters 1.1 and 1.2 is running locally (e.g., `http://localhost:5000`).
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) are set.
- `apscheduler` is installed (`pip install apscheduler`).
- Shopify access tokens are stored in your `.env` file (e.g., `SHOPIFY_ACCESS_TOKEN_acme-7cu19ngr.myshopify_com`).

---

#### Step 1: Test via OAuth Flow
The tests for webhooks and polling are automatically executed during the OAuth callback. Follow these steps to initiate and verify the results.

**Instructions**:
1. Run your app: `python app.py` or `uvicorn app:app --reload`.
2. Initiate the OAuth flow by visiting:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
3. Log in to your Shopify account and authorize the app.

**Expected Output**:
- The browser or terminal displays a JSON response, e.g.:
  ```json
  {
    "token_data": {...},
    "shopify_data": {...},
    "webhook_test": {"status": "success"},
    "polling_test": {"status": "success"}
  }
  ```
- The logs should show (based on your provided output and updated structure):
  ```
  INFO:     120.29.87.70:0 - "GET /shopify/acme-7cu19ngr/login HTTP/1.1" 307 Temporary Redirect
  Webhook for products/create already exists for acme-7cu19ngr.myshopify.com
  Webhook for products/update already exists for acme-7cu19ngr.myshopify.com
  Webhook for products/delete already exists for acme-7cu19ngr.myshopify.com
  Webhook for inventory_levels/update already exists for acme-7cu19ngr.myshopify.com
  Webhook for discounts/create already exists for acme-7cu19ngr.myshopify.com
  Webhook for discounts/update already exists for acme-7cu19ngr.myshopify.com
  Webhook for discounts/delete already exists for acme-7cu19ngr.myshopify.com
  Webhook for collections/create already exists for acme-7cu19ngr.myshopify.com
  Webhook for collections/update already exists for acme-7cu19ngr.myshopify.com
  Webhook for collections/delete already exists for acme-7cu19ngr.myshopify.com
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Test Product'}}
  INFO:     127.0.0.1:32930 - "POST /shopify/webhook HTTP/1.1" 200 OK
  Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  Polling test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  INFO:     120.29.87.70:0 - "GET /shopify/callback?code=5597fe3f235515942adacdd8056c2fe7&hmac=cc4804507760e7b80bb2bf1289e83c40b9ce31790d3757db357ee6c0ee0508df&host=YWRtaW4uc2hvcGlmeS5jb20vc3RvcmUvYWNtZS03Y3UxOW5ncg&shop=acme-7cu19ngr.myshopify.com&state=1751524486%3AuVmqs9pr6gI%3AuIVcMQV9UAqWPqQMndy-cWbi8913FNdQQLLi8_6v8_8%3D×tamp=1751524488 HTTP/1.1" 200 OK
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test` shows `{"status": "success"}`, indicating the webhook endpoint processed the test event.
- **Polling Success**: `polling_test` shows `{"status": "success"}`, confirming the polling function retrieved data successfully.
- **Errors**: If `webhook_test` or `polling_test` shows `{"status": "error", "message": "..."}`, address issues (e.g., invalid `SHOPIFY_API_SECRET`, network errors, or invalid access tokens).

**Troubleshooting**:
- **No Response**: Ensure the app is running and `SHOPIFY_WEBHOOK_ADDRESS` matches `http://localhost:5000/shopify/webhook`.
- **401 Error**: Verify `SHOPIFY_API_SECRET` in `.env` and app scopes in the Shopify Partners dashboard.
- **Polling Failure**: Check access tokens in `.env` and network connectivity.

---

#### Summary
This subchapter leverages the integrated tests within the OAuth flow to verify webhook and polling functionality. Completing authentication triggers both tests, returning consistent JSON results (`webhook_test` and `polling_test`) for validation.

#### Next Steps
- Proceed to Subchapter 1.4 for deployment or additional enhancements.
- Optionally, monitor logs regularly to ensure ongoing test success.