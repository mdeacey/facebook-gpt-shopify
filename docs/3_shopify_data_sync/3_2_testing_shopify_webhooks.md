# Subchapter 1.2: Testing Shopify Webhooks with OAuth

## Introduction
With your Shopify webhook setup integrated into the OAuth flow in Subchapter 1.1, this subchapter guides you to test it by completing the authentication process. The app automatically simulates a webhook event post-OAuth, using the authenticated shop’s details to verify functionality.

## Prerequisites
- Your FastAPI application is running locally (e.g., `http://localhost:5000`).
- Shopify credentials are configured in your `.env` file, including `SHOPIFY_WEBHOOK_ADDRESS`.

---

## Testing Steps

### Step 1: Initiate the OAuth Flow
Trigger the webhook test by authenticating a Shopify shop.

**Instructions**:
- Open your browser and navigate to:
  ```
  http://localhost:5000/shopify/yourshop/login
  ```
  Replace `yourshop` with your Shopify development store name (e.g., `acme-7cu19ngr`).

- Log in to your Shopify account and authorize the app.

### Step 2: Verify the Webhook Test Result
After OAuth completes, check the callback response and logs.

**Expected Output**:
- The browser or terminal displays a JSON response with a `webhook_test` field, e.g.:
  ```json
  {
    "token_data": {...},
    "preprocessed_data": {...},
    "webhook_test": {"status": "success"}
  }
  ```
- The app logs should show:
  ```
  Webhook test result for yourshop.myshopify.com: {'status': 'success'}
  Received products/update event from yourshop.myshopify.com: {'product': {'id': 12345, 'title': 'Test Product'}}
  ```

**What to Look For**:
- **Success**: `webhook_test` shows `{"status": "success"}`, indicating the endpoint processed the test event.
- **HMAC Failure**: If `webhook_test` shows `{"error": "401 Unauthorized"}`, verify `SHOPIFY_API_SECRET` in `.env`.
- **Multi-Shop Support**: Test with another shop to confirm dynamic handling.

### Step 3: Troubleshoot (if Needed)
- **No Response**: Ensure the app is running and `SHOPIFY_WEBHOOK_ADDRESS` matches `http://localhost:5000/shopify/webhook`.
- **401 Error**: Check `SHOPIFY_API_SECRET` and app scopes in the Shopify Partners dashboard.
- **Connection Issues**: Confirm network access to `localhost:5000`.

---

## Summary
This subchapter simplifies testing by embedding it in the OAuth flow. Completing authentication triggers an automatic webhook test, validating reception, security, and multi-shop support with the updated `SHOPIFY_WEBHOOK_ADDRESS`.

## Next Steps
- Move to Subchapter 1.3 for polling testing.
- Optionally, remove the test logic from the callback after verification.