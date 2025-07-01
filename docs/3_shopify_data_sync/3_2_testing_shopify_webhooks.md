# Subchapter 1.2: Testing Shopify Webhooks

## Introduction
Shopify webhooks keep your application updated with real-time store events. This subchapter provides a simple and smart way to test your `/shopify/webhook` endpoint, ensuring it handles requests, verifies HMAC signatures, and supports multiple shops. We’ll use a minimal setup with `curl` and your running FastAPI app.

## Prerequisites
- Your FastAPI app is running locally (e.g., `http://localhost:5000`).
- `curl` is installed.
- `SHOPIFY_API_SECRET` is set in your `.env` file.

---

## Testing Steps

### Step 1: Test Webhook Reception with a Simple Request
Send a simulated webhook event to verify your endpoint processes it correctly.

**Instructions**:
1. **Generate an HMAC Signature**:
   - Run this quick Python script to calculate the HMAC:
     ```python
     import hmac, hashlib, base64, os

     secret = os.getenv("SHOPIFY_API_SECRET")
     payload = b'{"product": {"id": 12345, "title": "Test Product"}}'
     hmac_signature = base64.b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()
     print(hmac_signature)
     ```
   - Copy the output HMAC.

2. **Send the Request**:
   - Use `curl` to hit your endpoint:
     ```bash
     curl -X POST http://localhost:5000/shopify/webhook \
       -H "X-Shopify-Topic: products/update" \
       -H "X-Shopify-Shop-Domain: yourshop.myshopify.com" \
       -H "X-Shopify-Hmac-Sha256: <paste_your_hmac_here>" \
       -H "Content-Type: application/json" \
       -d '{"product": {"id": 12345, "title": "Test Product"}}'
     ```
   - Replace `<paste_your_hmac_here>` with the HMAC from the script.

3. **Check the Logs**:
   - Look at your app’s console. You should see:
     ```
     Received products/update event from yourshop.myshopify.com: {'product': {'id': 12345, 'title': 'Test Product'}}
     ```
   - This confirms your endpoint processes the event.

### Step 2: Verify HMAC Security
Ensure your app rejects requests with invalid HMAC signatures.

**Instructions**:
1. **Send with a Fake HMAC**:
   - Use the same `curl` command but change the HMAC to an invalid value:
     ```bash
     curl -X POST http://localhost:5000/shopify/webhook \
       -H "X-Shopify-Topic: products/update" \
       -H "X-Shopify-Shop-Domain: yourshop.myshopify.com" \
       -H "X-Shopify-Hmac-Sha256: invalidhmac" \
       -H "Content-Type: application/json" \
       -d '{"product": {"id": 12345, "title": "Test Product"}}'
     ```

2. **Check the Response**:
   - Your app should return a `401 Unauthorized` error, proving HMAC validation works.

### Step 3: Test Multi-Shop Support
Verify your app handles webhooks from different shops dynamically.

**Instructions**:
1. **Update the Shop Domain**:
   - Send a request for another shop (ensure its access token is in `.env`):
     ```bash
     curl -X POST http://localhost:5000/shopify/webhook \
       -H "X-Shopify-Topic: products/update" \
       -H "X-Shopify-Shop-Domain: anothershop.myshopify.com" \
       -H "X-Shopify-Hmac-Sha256: <hmac_for_anothershop>" \
       -H "Content-Type: application/json" \
       -d '{"product": {"id": 12345, "title": "Test Product"}}'
     ```
   - Use a valid HMAC calculated with the same script for this shop’s secret.

2. **Check the Logs**:
   - Confirm you see an event logged for `anothershop.myshopify.com`.

---

## Edge Cases to Consider
- **Missing Headers**: Send a request without `X-Shopify-Shop-Domain` to ensure a 400 error.
- **Empty Payload**: Test with an empty JSON object (`{}`) to verify handling.

---

## Summary
This subchapter provides a simple, smart way to test your webhook system:
- **Reception**: Confirms your endpoint processes events.
- **Security**: Validates HMAC rejection of invalid requests.
- **Flexibility**: Ensures multi-shop support with dynamic handling.

## Next Steps
- Proceed to Subchapter 1.3 for polling testing.
- Enhance payload processing as needed.