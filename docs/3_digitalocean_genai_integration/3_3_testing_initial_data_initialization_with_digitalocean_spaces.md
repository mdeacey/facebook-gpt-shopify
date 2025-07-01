Chapter 3: DigitalOcean Integration
Subchapter 3.3: Testing Initial Data Initialization with DigitalOcean Spaces
This subchapter builds on the Shopify OAuth flow you completed in Subchapter 2.3. After authenticating and receiving the callback, we’ll test that the preprocessed Shopify data is uploaded to DigitalOcean Spaces correctly. Follow these steps to verify the upload, confirm the file’s presence, and address common issues.

Step 1: Start with the Shopify OAuth Flow
Action: Follow the Shopify OAuth steps from Subchapter 2.3 to authenticate and reach the /shopify/callback endpoint. This generates the preprocessed data needed for the Spaces upload.
Note: We won’t repeat those steps here—jump straight to the callback verification below once completed.

Step 2: Check the Callback Response for Upload Status
Action: After the OAuth callback, inspect the JSON response in your browser or terminal. Look for the digitalocean_upload field.
Expected Output:
{
  "token_data": { ... },
  "preprocessed_data": { ... },
  "digitalocean_upload": "success"
}


Success: If digitalocean_upload is "success", the data was uploaded to Spaces.
Failure: If it’s "failed", check the server logs for errors (e.g., credential issues).


Step 3: Verify the File in DigitalOcean Spaces
Action: Log into your DigitalOcean dashboard and check your Spaces bucket.

Navigate to Spaces > your_bucket_name.
Find a file named <shop>/preprocessed_data.json (e.g., acme-7cu19ngr.myshopify.com/preprocessed_data.json).
Download it and confirm it matches the preprocessed_data from the callback.

Expected Result: The file contains shop details, products, discounts, and collections.

Step 4: Troubleshoot Upload Issues
If the upload fails or the file isn’t in Spaces, try these fixes:

Environment Variables: Ensure your .env file has:SPACES_ACCESS_KEY=your_access_key
SPACES_SECRET_KEY=your_secret_key
SPACES_BUCKET=your_bucket_name
SPACES_REGION=nyc3  # Optional, defaults to "nyc3"


Bucket Name: Double-check it matches your Spaces bucket.
Permissions: Verify the access keys allow writing to the bucket.
Logs: Check the FastAPI terminal for errors like Failed to upload to Spaces.


Summary
You’ve now tested the DigitalOcean Spaces upload! This ensures your GPT Messenger sales bot has the initial Shopify data stored in the cloud, ready for future use. Next, explore Subchapter 3.4 for webhook-based updates.