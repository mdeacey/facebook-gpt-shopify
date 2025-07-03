### Chapter 3: DigitalOcean Integration
#### Subchapter 3.2: Creating a DigitalOcean Spaces Bucket and Generating API Keys for Integration

This subchapter guides you through creating a DigitalOcean Spaces bucket and generating API keys to access it programmatically. These steps provide a scalable storage solution and the necessary credentials for your FastAPI application to interact with DigitalOcean's object storage. The Spaces bucket will store files such as product images or data backups for the GPT Messenger sales bot, while the API keys enable secure read and write operations. We include references to screenshots (not provided) and explain the reasoning behind each action. This subchapter follows the initial DigitalOcean setup (assumed in Subchapter 3.1) and prepares you for integrating the bucket with your application in Subchapter 3.3, building on the Shopify integration from Chapter 2 and the bot foundation from Chapter 1. Timestamps are included to ensure a logical flow, reflecting the sequence of actions.

---

**Step 1: Access the DigitalOcean Dashboard and Navigate to Spaces**  
**Action:** Log into your DigitalOcean dashboard at [cloud.digitalocean.com](https://cloud.digitalocean.com). In the left sidebar, under the "MANAGE" section, locate and click "Spaces Object Storage".  
**Screenshot Reference:** Shows the DigitalOcean dashboard with the "Spaces Object Storage" option highlighted in the sidebar at 10:00 AM.  
**Timestamp:** 10:00 AM  
**Why?**  
- The "Spaces Object Storage" section is where you manage DigitalOcean Spaces, which are object storage buckets similar to AWS S3. These buckets are ideal for storing files like product images or backups for your sales bot, providing a scalable and cost-effective storage solution.

---

**Step 2: Create a New Spaces Bucket**  
**Action:** On the "Spaces Object Storage" page, click the green "CREATE" button in the top-right corner and select "Spaces Bucket" from the dropdown menu.  
**Screenshot Reference:** Highlights the "CREATE" button and the "Spaces Bucket" option selected at 10:02 AM.  
**Timestamp:** 10:02 AM  
**Why?**  
- Creating a Spaces bucket establishes a dedicated storage area for your sales bot’s data, analogous to the Shopify development store created in Chapter 2. This bucket will hold files needed for your application, such as media assets or exported data.

---

**Step 3: Configure the Spaces Bucket Settings**  
**Action:** Fill out the "Create a Spaces Bucket" form:  
- **Bucket Name:** Enter a unique name, e.g., `messenger-gpt-bucket`.  
- **Datacenter Region:** Select a region close to your users or application, e.g., "New York (NYC3)".  
- **CDN (Optional):** Leave "Enable CDN" unchecked for now (can be enabled later for production).  
- **Project:** Assign the bucket to your current project (e.g., "facebook-gpt-shopify").  
Click "Create Spaces Bucket" to proceed.  
**Screenshot Reference:** Shows the filled form with the bucket name, region, and project selected at 10:05 AM.  
**Timestamp:** 10:05 AM  
**Why?**  
- **Bucket Name:** A unique name like `messenger-gpt-bucket` ensures no conflicts across DigitalOcean Spaces and reflects its purpose for the sales bot.  
- **Region:** Choosing "NYC3" minimizes latency if your application or users are nearby; adjust based on your needs.  
- **CDN:** Disabling CDN simplifies the initial setup; it can be enabled later for faster content delivery.  
- **Project:** Assigning to a project organizes resources, similar to how Shopify apps are linked to stores.

---

**Step 4: Generate Spaces Access Keys**  
**Action:** In the DigitalOcean dashboard, navigate to "API" in the left sidebar under "MANAGE". On the "API" page, scroll to the "Spaces access keys" section and click "Generate New Key".  
**Screenshot Reference:** Shows the "API" page with the "Generate New Key" button highlighted under "Spaces access keys" at 10:10 AM.  
**Timestamp:** 10:10 AM  
**Why?**  
- Spaces access keys (an access key and secret key pair) are specifically designed for interacting with Spaces buckets via the S3-compatible API. They authenticate your application for operations like uploading or retrieving files, similar to Shopify’s API credentials in Chapter 2.

---

**Step 5: Retrieve and Store the Spaces Access Keys**  
**Action:** After clicking "Generate New Key", name the key (e.g., `messenger-gpt-spaces-key`). DigitalOcean will display the access key and secret key. Copy these values immediately (the secret key is only shown once) and add them to your `.env` file:  
```
DO_SPACES_KEY=your_access_key
DO_SPACES_SECRET=your_secret_key
```  
**Screenshot Reference:** Shows the generated access key and secret key (blurred for security) at 10:12 AM.  
**Timestamp:** 10:12 AM  
**Why?**  
- The access key and secret key pair authenticates your FastAPI application when accessing the Spaces bucket. Storing them in the `.env` file keeps them secure and accessible, mirroring the credential storage approach used for Shopify in Chapter 2.

---

**Step 7: Update Environment Variables**  
**Action:** Update your `.env` file to include the DigitalOcean Spaces credentials alongside previous credentials (e.g., Facebook and Shopify). Use the example below as a guide:  
```
# Facebook OAuth credentials (from Subchapter 1.2)
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback

# Shopify OAuth credentials (from Subchapter 2.2)
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback

# DigitalOcean Spaces credentials (from this subchapter)
DO_SPACES_KEY=your_access_key
DO_SPACES_SECRET=your_secret_key
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
DO_SPACES_BUCKET=messenger-gpt-bucket
DO_SPACES_REGION=nyc3

# Shared secret for state token CSRF protection (from Subchapter 1.1)
STATE_TOKEN_SECRET=replace_with_secure_token
```  
**Screenshot Reference:** Not applicable (text file update), but assume this is completed at 10:17 AM.  
**Timestamp:** 10:17 AM  
**Why?**  
- Consolidating all credentials in the `.env` file ensures your FastAPI application can access all required APIs (Facebook, Shopify, and DigitalOcean) for the sales bot’s functionality. The additional Spaces-specific variables (`ENDPOINT`, `BUCKET`, `REGION`) provide complete configuration for API interactions.

---

### Summary: Why This Subchapter Matters
- **Storage Solution:** The Spaces bucket offers a scalable environment for storing sales bot data, such as product images or customer backups, enhancing the bot’s capabilities beyond Shopify’s scope.  
- **API Access:** The generated Spaces access keys enable secure, programmatic interaction with the bucket, supporting file operations in your FastAPI application.  
- **Integration Readiness:** Testing the bucket and keys ensures your setup is functional, preparing you for deeper integration in Subchapter 3.3.

### Next Steps:
- Use the Spaces bucket to store and retrieve data for the sales bot (Subchapter 3.3).  
- Integrate the bucket with your FastAPI application for seamless file management (Subchapter 3.4).  
- Combine Shopify and DigitalOcean integrations to enhance the sales bot’s features (Chapter 4).