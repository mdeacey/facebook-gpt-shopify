# Chapter 2: Shopify Integration
## Subchapter 2.2: Creating a Shopify Development Store and App for API Integration

This subchapter guides you through creating a Shopify development store and setting up a new app within the Shopify Partners dashboard. These steps provide the credentials (`SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET`) and store environment needed for the Shopify OAuth flow implemented in Subchapter 2.1. The development store serves as a sandbox for testing, and the app generates the API credentials to authenticate your FastAPI application with Shopify’s API. We include references to screenshots (not provided) and explain the reasoning behind each action. This subchapter follows the OAuth implementation in Subchapter 2.1, preparing for testing in Subchapter 2.3.

### Step 1: Access the Shopify Partners Dashboard and Navigate to Stores
**Action**: Log into the Shopify Partners dashboard at [partners.shopify.com](https://partners.shopify.com). In the left sidebar, locate and click "Stores".

**Screenshot Reference**: Shows the Partners dashboard with the "Stores" section selected, displaying "No stores found" if no stores exist.

**Why?**
- The "Stores" section manages your Shopify development stores, which are sandbox environments for testing API integrations without affecting live stores.
- If you’re starting fresh, "No stores found" indicates the need to create a development store for testing the OAuth flow (Subchapter 2.1) and data retrieval (Subchapter 2.3).

### Step 2: Create a New Development Store
**Action**: On the "Stores" page, click the green "Add store" button in the top-right corner, then select "Create development store" from the dropdown menu.

**Screenshot Reference**: Highlights the "Add store" button and "Create development store" option.

**Why?**
- Development stores provide a non-transferable sandbox for testing apps and API integrations, ideal for your FastAPI-based sales bot.
- This store (e.g., `acme-7cu19ngr.myshopify.com`) is used in Subchapter 2.1’s OAuth flow and Subchapter 2.3’s testing.

### Step 3: Configure the Development Store Details
**Action**: Fill out the "Create a store for a client" form:
- **Store name**: Enter a unique name, e.g., `acme-7cu19ngr`.
- **Build version**: Select "Current release" to use the latest Shopify version (2025-04).
- **Data and configurations**: Choose "Start with test data" to pre-populate the store with sample products (e.g., snowboards, gift cards) and customers.

Click the green "Create development store" button to proceed.

**Screenshot Reference**: Shows the filled form with store name, build version, and test data options.

**Why?**
- **Store name**: Generates a unique URL (e.g., `acme-7cu19ngr.myshopify.com`) used in the OAuth flow (`/shopify/{shop_name}/login` in Subchapter 2.1).
- **Current release**: Ensures compatibility with the GraphQL API version (2025-04) used in Subchapter 2.1.
- **Test data**: Provides sample products and customers, enabling realistic testing in Subchapter 2.3.

### Step 4: Navigate to Apps and Create a New App
**Action**: In the Shopify Partners dashboard, click "Apps" in the left sidebar, then select "All apps". Click the green "Create app" button.

**Screenshot Reference**: Shows the "Apps" page with the "Create app" button highlighted.

**Why?**
- The "Apps" section manages apps that connect to Shopify’s APIs, such as your FastAPI integration for the sales bot.
- Creating an app generates the `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` required for OAuth in Subchapter 2.1.

### Step 5: Create the App Manually
**Action**: On the "Create a new app" page, click "Create app manually".

**Screenshot Reference**: Shows the "Create app manually" button.

**Why?**
- Manual creation allows full control over app configuration, ideal for custom integrations like your FastAPI OAuth flow.
- This avoids pre-configured templates that may not align with the sales bot’s API needs.

### Step 6: Configure the App Details and URLs
**Action**: Name your app `messenger-gpt` to reflect its integration purpose. In the Configuration tab, fill in:
- **App URL**: Set to your FastAPI app’s base URL, e.g., `https://your-codespace-id-5000.app.github.dev` (or `http://localhost:5000` for local development).
- **Allowed redirection URL(s)**: Set to `https://your-codespace-id-5000.app.github.dev/shopify/callback` (or `http://localhost:5000/shopify/callback`).

Click "Save and release".

**Screenshot Reference**: Shows the app configuration with name and URLs filled in.

**Why?**
- **App name**: `messenger-gpt` aligns with the bot’s purpose, consistent with Chapter 1’s naming.
- **App URL**: Specifies where your FastAPI app runs, used for app interactions and OAuth redirects.
- **Redirect URL**: Matches the `SHOPIFY_REDIRECT_URI` in Subchapter 2.1’s OAuth flow, ensuring secure redirection.

### Step 7: Configure Additional App Settings
**Action**: In the Configuration tab:
- Set **Embed in Shopify admin** to False.
- Set **Event version** to 2025-04 (Latest) to match the API version used in Subchapter 2.1.
- Leave **Compliance webhooks** (e.g., customer/shop data erasure) blank for testing purposes.

Click "Save and release" again.

**Screenshot Reference**: Shows the configuration settings with embed disabled, event version selected, and compliance webhooks empty.

**Why?**
- **Embed in Shopify admin**: Disabling keeps the app standalone, as it’s a backend integration, not a UI within Shopify’s admin.
- **Event version**: Aligns with the GraphQL API version (2025-04) used in Subchapter 2.1.
- **Compliance webhooks**: Optional during development; added in later chapters if needed.

### Step 8: Retrieve App Credentials and Test the App
**Action**: Go to the Overview tab of your app. Copy the API Key and API Secret Key into your `.env` file as follows:
```plaintext
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
```
For GitHub Codespaces:
```plaintext
SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
```

In the **Test your app** section, click **Select store**, choose your development store (e.g., `acme-7cu19ngr`), and click **Install** to test the app installation.

**Screenshot Reference**: Shows the Overview tab with API credentials and installation history after testing.

**Why?**
- **Credentials**: `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` authenticate the OAuth flow in Subchapter 2.1’s `/shopify/{shop_name}/login` and `/shopify/callback` endpoints.
- **Redirect URI**: Must match the “Allowed redirection URL(s)” set in Step 6 and `SHOPIFY_REDIRECT_URI` in Subchapter 2.1.
- **Test Installation**: Verifies the OAuth setup, ensuring credentials work for testing in Subchapter 2.3.

### Step 9: Update Environment Variables
Update your `.env` file to include both Facebook (from Chapter 1) and Shopify credentials.

```plaintext
# Facebook OAuth credentials (from Subchapter 1.2)
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback
# Shopify OAuth credentials (from this subchapter)
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Why?**
- Combines credentials for both integrations, validated in `app.py` (Subchapter 2.1).
- Excludes future variables (e.g., webhook or Spaces settings, introduced in Chapters 5–6).
- **Production Note**: Use a secure, unique `STATE_TOKEN_SECRET`.

### Step 10: Testing Preparation
To verify the store and app setup:
- Confirm the development store (`acme-7cu19ngr.myshopify.com`) is accessible in the Shopify Partners dashboard and contains test data (e.g., snowboards, gift cards).
- Verify the `messenger-gpt` app appears in the dashboard’s "Apps" section with the correct API key and secret.
- Check that the app is installed on the development store (visible in the Overview tab’s installation history).
- Update your `.env` file with the credentials and redirect URI from this subchapter.

Detailed testing of the OAuth flow is covered in Subchapter 2.3.

### Summary: Why This Subchapter Matters
- **Sandbox Environment**: The development store provides a safe space to test OAuth and API calls.
- **API Credentials**: `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` enable authentication for Subchapter 2.1.
- **OAuth Readiness**: Configuring the redirect URI and installing the app ensures the OAuth flow works in Subchapter 2.3.
- **Bot Preparation**: Test data supports realistic testing, with persistent storage introduced in Chapter 3.

### Next Steps:
- Use the credentials in the FastAPI OAuth implementation (Subchapter 2.1, already completed).
- Test the OAuth flow and data retrieval (Subchapter 2.3).