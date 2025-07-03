### Chapter 3: DigitalOcean Integration

#### Subchapter 3.3: Testing Initial Data Initialization with DigitalOcean Spaces

This subchapter builds on the Shopify OAuth flow and Spaces integration from Subchapters 2.3 and 3.2. After authenticating and reaching the `/shopify/callback` endpoint, we’ll test that the Shopify data is uploaded correctly to DigitalOcean Spaces, verify webhook and polling functionality, and ensure the data is accessible in the cloud for the GPT Messenger sales bot. Follow these steps to confirm the upload, check the file’s presence in Spaces, and troubleshoot common issues.

---

##### Step 1: Start with the Shopify OAuth Flow

**Action**: Follow the Shopify OAuth steps from Subchapter 2.3 to authenticate and trigger the `/shopify/callback` endpoint. This fetches the Shopify data, tests webhooks and polling, and uploads the data to Spaces if it has changed.

**Instructions**:
1. Ensure your FastAPI server is running: `uvicorn app:app --host 0.0.0.0 --port 5000 --reload`.
2. Navigate to `http://localhost:5000/shopify/yourshop/login` (replace `yourshop` with your Shopify store name, e.g., `acme-7cu19ngr`).
3. Complete the OAuth flow in your Shopify admin to authorize the app.
4. After authorization, you’ll be redirected to the `/shopify/callback` endpoint.

**Why?**  
The OAuth flow authenticates the app, fetches initial Shopify data, and triggers the Spaces upload process defined in Subchapter 3.2.

---

##### Step 2: Check the Callback Response for Statuses

**Action**: After the OAuth callback, inspect the JSON response in your browser, terminal (using `curl`), or a tool like Postman to verify the webhook, polling, and upload statuses.

**Instructions**:
1. Make a GET request to `http://localhost:5000/shopify/callback?code=<code>&shop=<yourshop>.myshopify.com&state=<state>` (use the URL from the OAuth redirect).
2. Check the response for the following fields:
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

**Expected Output**:
- `"webhook_test": {"status": "success"}`: Indicates the webhook registration and test were successful.
- `"polling_test": {"status": "success"}`: Confirms the polling test retrieved Shopify data successfully.
- `"upload_status_result": {"status": "success"}`: Verifies the Shopify data was either uploaded to Spaces or unchanged (no upload needed).
- If any field shows `{"status": "failed", "message": "..."}` or `{"status": "error", "message": "..."}`, check the `message` for details and proceed to Step 4 for troubleshooting.

**Why?**  
The callback response confirms that the webhook setup, polling, and Spaces upload (or change check) completed successfully, ensuring the bot has access to up-to-date data.

---

##### Step 3: Verify the File in DigitalOcean Spaces

**Action**: Log into your DigitalOcean dashboard to check the Spaces bucket for the uploaded Shopify data file.

**Instructions**:
1. Navigate to Spaces > `your_bucket_name` in the DigitalOcean dashboard.
2. Look for a file named `<shop>/shopify_data.json` (e.g., `acme-7cu19ngr.myshopify.com/shopify_data.json`).
3. Download the file and compare its contents with the `shopify_data` field from the callback response.
4. Verify that the file contains shop details, products, discounts, and collections as shown in the response.

**Expected Result**:  
The file matches the `shopify_data` from the callback response, containing raw Shopify data (e.g., shop name, product titles, prices, inventory levels, discount codes, and collections).

**Why?**  
This confirms that the Shopify data was correctly uploaded to Spaces, making it accessible for the sales bot.

---

##### Step 4: Troubleshoot Issues

**Action**: If the callback response shows failures or the file is missing in Spaces, use these steps to diagnose and fix issues.

**Common Issues and Fixes**:
1. **Webhook Test Failure (`webhook_test: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Webhook registration or test request failed (e.g., invalid `SHOPIFY_API_SECRET`, network issues, or webhook endpoint not reachable).
   - **Fix**:
     - Check the `message` in `webhook_test` for details (e.g., HTTP 401 for HMAC issues).
     - Verify `SHOPIFY_API_SECRET` in `.env` matches your Shopify app credentials.
     - Ensure `SHOPIFY_WEBHOOK_ADDRESS` (`http://localhost:5000/shopify/webhook`) is accessible (use `ngrok` for local testing if needed).
     - Check server logs for errors like `Webhook setup failed`.

2. **Polling Test Failure (`polling_test: {"status": "error", "message": "..."}`)**:
   - **Cause**: Failed to fetch Shopify data (e.g., invalid access token, API rate limits, or network issues).
   - **Fix**:
     - Check the `message` in `polling_test` (e.g., HTTP 403 for invalid token).
     - Verify the `SHOPIFY_ACCESS_TOKEN_<shop>` environment variable is set correctly.
     - Ensure `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` in `.env` are correct.
     - Check for Shopify API rate limits in logs (e.g., HTTP 429).

3. **Upload Failure (`upload_status_result: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Issues with Spaces configuration, credentials, or connectivity.
   - **Fix**:
     - Verify `.env` contains correct Spaces credentials:
       ```plaintext
       SPACES_ACCESS_KEY=your_access_key
       SPACES_SECRET_KEY=your_secret_key
       SPACES_BUCKET=your_bucket_name
       SPACES_REGION=nyc3
       ```
     - Ensure the bucket name matches exactly and exists in your DigitalOcean account.
     - Confirm the access keys have write permissions for the bucket (check in DigitalOcean dashboard).
     - Check server logs for errors like `Failed to upload to Spaces` or `Failed to fetch existing data`.
     - Verify network connectivity to `https://nyc3.digitaloceanspaces.com`.

4. **File Missing in Spaces**:
   - **Cause**: Upload didn’t occur due to test failures or data being unchanged.
   - **Fix**:
     - Check `upload_status_result` and logs. If `No upload needed: Data unchanged`, the data matches the existing file, which is expected behavior.
     - If tests failed, resolve `webhook_test` or `polling_test` issues first.
     - Manually trigger a new OAuth flow to force an upload if needed.

5. **Response Missing Fields**:
   - **Cause**: Frontend rendering or an outdated server code version.
   - **Fix**:
     - Use `curl` or Postman to test `http://localhost:5000/shopify/callback` directly and confirm the full response.
     - Ensure the deployed `shopify_integration/routes.py` matches the provided code (run `git diff` or check the server’s file).
     - Inspect frontend code for filtering (e.g., only displaying certain fields).

**Why?**  
These steps help identify and resolve issues with webhook setup, polling, or Spaces uploads, ensuring the integration works as expected.

---

##### Summary: Why This Subchapter Matters

You’ve now tested the initial Shopify data upload to DigitalOcean Spaces, confirming that webhooks and polling are functional and that the data is stored correctly in the cloud. This ensures the GPT Messenger sales bot has access to up-to-date Shopify data for generating recommendations. Next, explore Subchapter 3.4 for testing webhook-based updates.

---