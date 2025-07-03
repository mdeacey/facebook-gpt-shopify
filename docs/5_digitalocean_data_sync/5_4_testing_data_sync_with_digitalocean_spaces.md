# Chapter 5: DigitalOcean Integration

## Subchapter 5.3: Testing Data Synchronization with DigitalOcean Spaces for Shopify and Facebook

### Introduction
This subchapter builds on the Shopify and Facebook OAuth flows and Spaces integration from Subchapters 5.1 and 5.2. By navigating to `/facebook/login` and `/shopify/[shop_name]/login` in your browser, you’ll trigger the `/facebook/callback` and `/shopify/callback` endpoints, testing that Shopify data (shop details, products, discounts, collections) and Facebook page data (name, description, category) are uploaded correctly to DigitalOcean Spaces, verifying webhook and polling functionality, and ensuring data is accessible in the cloud for the GPT Messenger sales bot. The JSON responses are displayed directly on the webpage after OAuth redirection. Follow these steps to confirm uploads, check file presence in Spaces, and troubleshoot issues using the webpage responses.

---

### Step 1: Start with the OAuth Flows
**Action**: Trigger the Shopify and Facebook OAuth flows by navigating to their respective login endpoints in your browser, completing authentication to reach the callback endpoints.

**Instructions**:
1. Ensure your FastAPI server is running: `uvicorn app:app --host 0.0.0.0 --port 5000 --reload`.
2. For Shopify:
   - Open your browser and navigate to `http://localhost:5000/shopify/yourshop/login` (replace `yourshop` with your Shopify store name, e.g., `acme-7cu19ngr`).
   - Log in to your Shopify admin and authorize the app.
3. For Facebook:
   - Navigate to `http://localhost:5000/facebook/login`.
   - Log in to your Facebook account and grant `pages_show_list` and `pages_manage_metadata` permissions.
4. After authorization, you’ll be redirected to the respective callback endpoints (`/shopify/callback` or `/facebook/callback`), and the JSON response will appear on the webpage.

**Why?**  
The OAuth flows authenticate the app, fetch initial Shopify and Facebook data, and trigger the Spaces upload processes defined in Subchapters 5.1 and 5.2.

---

### Step 2: Check the Callback Responses on the Webpage
**Action**: After each OAuth callback, inspect the JSON responses displayed on the webpage to verify webhook, polling, and upload statuses for both Shopify and Facebook.

**Instructions**:
1. **Shopify Callback**:
   - After authorizing in Shopify, the browser redirects to `http://localhost:5000/shopify/callback?code=<code>&shop=<yourshop>.myshopify.com&state=<state>`.
   - Check the JSON response displayed on the webpage for:
     ```json
     {
       "token_data": {
         "access_token": "...",
         "scope": "..."
       },
       "shopify_data": {
         "data": {
           "shop": {...},
           "products": {...},
           "codeDiscountNodes": {...},
           "collections": {...},
           "extensions": {...}
         }
       },
       "webhook_test": {"status": "success"} | {"status": "failed", "message": "..."},
       "polling_test": {"status": "success"} | {"status": "error", "message": "..."},
       "upload_status_result": {"status": "success"} | {"status": "failed", "message": "..."}
     }
     ```
2. **Facebook Callback**:
   - After authorizing in Facebook, the browser redirects to `http://localhost:5000/facebook/callback?code=<code>&state=<state>`.
   - Check the JSON response displayed on the webpage for:
     ```json
     {
       "token_data": {
         "access_token": "...",
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
             "access_token": "..."
           }
         ]
       },
       "webhook_test": {"status": "success"} | {"status": "error", "message": "..."},
       "polling_test": [
         {
           "page_id": "123456789",
           "result": {"status": "success"} | {"status": "error", "message": "..."}
         }
       ],
       "upload_status_result": [
         {
           "page_id": "123456789",
           "result": {"status": "success"} | {"status": "failed", "message": "..."}
         }
       ]
     }
     ```

**Expected Output**:
- **Shopify**:
  - `"webhook_test": {"status": "success"}`: Webhook registration and test succeeded.
  - `"polling_test": {"status": "success"}`: Polling retrieved Shopify data successfully.
  - `"upload_status_result": {"status": "success"}`: Shopify data was uploaded or unchanged.
- **Facebook**:
  - `"webhook_test": {"status": "success"}`: Webhook registration and test succeeded.
  - `"polling_test": [{"page_id": "...", "result": {"status": "success"}}]`: Polling succeeded for each page.
  - `"upload_status_result": [{"page_id": "...", "result": {"status": "success"}}]`: Page data was uploaded or unchanged for each page.
- If any field shows `{"status": "failed", "message": "..."}` or `{"status": "error", "message": "..."}`, check the `message` on the webpage and proceed to Step 4 for troubleshooting.

**Why?**  
The JSON responses displayed on the webpage confirm that webhook setup, polling, and Spaces uploads (or change checks) completed successfully for both integrations, ensuring the bot has access to up-to-date data.

---

### Step 3: Verify Files in DigitalOcean Spaces
**Action**: Log into your DigitalOcean dashboard to check the Spaces bucket for uploaded Shopify and Facebook data files.

**Instructions**:
1. Navigate to Spaces > `your_bucket_name` in the DigitalOcean dashboard.
2. For Shopify:
   - Look for a file named `<shop>/shopify_data.json` (e.g., `acme-7cu19ngr.myshopify.com/shopify_data.json`).
   - Download and compare with the `shopify_data` field from the Shopify callback response on the webpage.
   - Verify it contains shop details, products, discounts, and collections.
3. For Facebook:
   - Look for files named `facebook/<page_id>/page_data.json` (e.g., `facebook/123456789/page_data.json`).
   - Download and compare with the `pages` field from the Facebook callback response on the webpage.
   - Verify it contains page metadata (id, name, description, category).

**Expected Result**:
- Shopify file matches `shopify_data`, containing raw data (e.g., shop name, product titles, prices, inventory levels, discount codes, collections).
- Facebook files match `pages`, containing page metadata for each page.

**Why?**  
This confirms that both Shopify and Facebook data were correctly uploaded to Spaces, making them accessible for the sales bot.

---

### Step 4: Troubleshoot Issues
**Action**: If callback responses on the webpage show failures or files are missing in Spaces, use these steps to diagnose and fix issues for both integrations.

**Common Issues and Fixes**:
1. **Shopify Webhook Test Failure (`webhook_test: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Webhook registration or test failed (e.g., invalid `SHOPIFY_API_SECRET`, network issues).
   - **Fix**:
     - Check the `message` in the webpage response (e.g., HTTP 401 for HMAC issues).
     - Verify `SHOPIFY_API_SECRET` in `.env`.
     - Ensure `SHOPIFY_WEBHOOK_ADDRESS` (`http://localhost:5000/shopify/webhook`) is accessible (use `ngrok` for local testing if needed).
     - Check server logs for `Webhook setup failed`.

2. **Facebook Webhook Test Failure (`webhook_test: {"status": "error", "message": "..."}`)**:
   - **Cause**: Webhook registration, test, or verification failed (e.g., invalid `FACEBOOK_APP_SECRET`, `FACEBOOK_VERIFY_TOKEN`).
   - **Fix**:
     - Check the `message` in the webpage response (e.g., HTTP 401 for HMAC, 403 for token mismatch).
     - Verify `FACEBOOK_APP_SECRET` and `FACEBOOK_VERIFY_TOKEN` in `.env`.
     - Ensure `FACEBOOK_WEBHOOK_ADDRESS` (`http://localhost:5000/facebook/webhook`) is accessible.
     - Check logs for `Webhook test result`.

3. **Shopify Polling Test Failure (`polling_test: {"status": "error", "message": "..."}`)**:
   - **Cause**: Failed to fetch Shopify data (e.g., invalid access token, API rate limits).
   - **Fix**:
     - Check the `message` in the webpage response.
     - Verify `SHOPIFY_ACCESS_TOKEN_<shop>` in the environment.
     - Ensure `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` are correct.
     - Check logs for Shopify API rate limits (HTTP 429).

4. **Facebook Polling Test Failure (`polling_test: [{"page_id": "...", "result": {"status": "error", "message": "..."}]`)**:
   - **Cause**: Failed to fetch page data (e.g., invalid access token, API rate limits).
   - **Fix**:
     - Check the `message` for each page in the webpage response.
     - Verify `FACEBOOK_ACCESS_TOKEN_<page_id>` in the environment.
     - Ensure `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` are correct.
     - Check logs for Facebook API rate limits.

5. **Upload Failure (`upload_status_result: {"status": "failed", "message": "..."}` or `[{"page_id": "...", "result": {"status": "failed", "message": "..."}]`)**:
   - **Cause**: Issues with Spaces configuration, credentials, or connectivity.
   - **Fix**:
     - Verify `.env` credentials:
       ```plaintext
       SPACES_ACCESS_KEY=your_access_key
       SPACES_SECRET_KEY=your_secret_key
       SPACES_BUCKET=your_bucket_name
       SPACES_REGION=nyc3
       ```
     - Ensure the bucket exists in your DigitalOcean account.
     - Confirm access keys have write permissions.
     - Check logs for `Failed to upload to Spaces` or `Failed to fetch existing data`.
     - Verify connectivity to `https://nyc3.digitaloceanspaces.com`.

6. **Files Missing in Spaces**:
   - **Cause**: Upload didn’t occur due to test failures or unchanged data.
   - **Fix**:
     - Check `upload_status_result` and logs in the webpage response. If `No upload needed: Data unchanged`, data matches existing files.
     - Resolve `webhook_test` or `polling_test` failures first.
     - Trigger a new OAuth flow via the browser to force an upload.

7. **Response Not Visible on Webpage**:
   - **Cause**: Browser rendering or outdated server code.
   - **Fix**:
     - Refresh the browser or clear cache to display the JSON response.
     - Verify `shopify_integration/routes.py` and `facebook_integration/routes.py` match the provided code.
     - Check server logs for errors rendering the response.

**Why?**  
These steps identify and resolve issues with webhook setup, polling, or Spaces uploads for both integrations, using webpage JSON responses and server logs for debugging.

---

### Summary: Why This Subchapter Matters
You’ve tested the initial data uploads to DigitalOcean Spaces for both Shopify and Facebook by navigating to `/facebook/login` and `/shopify/[shop_name]/login` and checking JSON responses on the webpage, confirming that webhooks and polling are functional and that data is stored correctly in the cloud. This ensures the GPT Messenger sales bot has access to up-to-date Shopify and Facebook data for generating recommendations and managing page interactions.

### Next Steps:
- Optimize webhook handling for specific event types if needed (Subchapter 5.4).
- Monitor logs regularly to ensure ongoing synchronization success.
- Explore additional Spaces features, such as CDN integration, for production.