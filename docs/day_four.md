# Chapter 4: Creating a Shopify Development Store and App for API Integration

This chapter walks you through creating a Shopify development store and setting up a new app within the Shopify Partners dashboard. These steps are essential for obtaining the credentials (Client ID and Client Secret) needed for your FastAPI integration with Shopify's API. We'll use the provided screenshots to detail each step and explain the reasoning behind each action.

---

## Step 1: Access the Shopify Partners Dashboard and Navigate to Stores
**Action:** Log into the Shopify Partners dashboard (at `partners.shopify.com`). Once logged in, locate the "Stores" section in the left sidebar and click on it.

**Screenshot Reference:** The first screenshot shows the Shopify Partners dashboard with the "Stores" section selected and no stores listed.

**Why?**
- The "Stores" section is where you manage all your Shopify development stores, which are used for testing apps and themes before deploying to live stores.
- Since no stores are listed ("No stores found"), you need to create a new development store to test your FastAPI app's integration with Shopify.

---

## Step 2: Create a New Development Store
**Action:** On the "Stores" page, click the green "Add store" button at the top right, then select "Create development store" from the dropdown menu.

**Screenshot Reference:** The first screenshot highlights the "Add store" button with the "Create development store" option visible.

**Why?**
- A development store provides a sandbox environment to test your app without affecting a live store.
- Development stores are non-transferable and meant for testing purposes, making them ideal for developing and debugging your FastAPI app's Shopify integration.

---

## Step 3: Configure the Development Store Details
**Action:** In the "Create a store for a client" form, fill in the following fields:
- **Store name:** Enter a unique name, such as `acme-7cu19ngr`.
- **Build version:** Select "Current release" to test the latest version of Shopify.
- **Data and configurations:** Choose "Start with test data" to pre-populate the store with sample data.
Click the green "Create development store" button to proceed.

**Screenshot Reference:** The second screenshot shows the "Create a store for a client" form with the store name, build version, and data options filled out.

**Why?**
- **Store name:** This generates a unique URL (e.g., `acme-7cu19ngr.myshopify.com`) for your development store. It must be unique across Shopify's platform.
- **Build version:** Using the "Current release" ensures you're testing with the latest Shopify features and API versions, which is best for compatibility with your app.
- **Data and configurations:** Starting with test data gives you sample products, customers, and orders to work with, making it easier to test your app's functionality without manually adding data.

---

## Step 4: Navigate to Apps and Create a New App
**Action:** After creating the store, return to the Shopify Partners dashboard. Click "Apps" in the left sidebar, then select "All apps". On the "Apps" page, click the green "Create app" button.

**Screenshot Reference:** The third screenshot shows the "Apps" page with the "Create app" button highlighted.

**Why?**
- The "Apps" section is where you manage apps that interact with Shopify's APIs, such as the one you're building with FastAPI.
- Creating a new app allows you to generate the credentials (Client ID and Client Secret) needed for OAuth authentication and API access.

---

## Step 5: Create the App Manually
**Action:** On the "Create a new app" page, click "Create app manually" to set up the app directly in the dashboard.

**Screenshot Reference:** The fourth screenshot shows the "Create a new app" page with the "Create app manually" button.

**Why?**
- Creating the app manually gives you full control over the setup process, allowing you to configure each aspect directly in the Shopify Partners dashboard.
- This method is particularly useful for a custom FastAPI integration, as it helps you understand and tailor each configuration option to your app's needs.

---

## Step 6: Configure the App Details and URLs
**Action:** After selecting "Create app manually", name your app `messenger-gpt` and proceed to the "Configuration" tab. In the "URLs" section, fill in the following:
- **App URL:** Enter `https://upgraded-space-potato-9vqxrgx5wc59q7-5000.app.github.dev`.
- **Allowed redirection URL(s):** Add `https://upgraded-space-potato-9vqxrgx5wc59q7-5000.app.github.dev/shopify/callback`.
Click "Save and release" to save your changes.

**Screenshot Reference:** The fifth screenshot shows the "Configuration" tab with the app name and URLs filled out.

**Why?**
- **App name:** This identifies your app in the Shopify Partners dashboard. It should reflect its purpose (e.g., integrating Messenger with Shopify).
- **App URL:** This is the base URL of your FastAPI app, where Shopify will interact with your app (e.g., for OAuth redirects or app loading).
- **Allowed redirection URL(s):** This URL is where Shopify redirects after the user authorizes your app during the OAuth flow. It must match the redirect URI in your FastAPI app (e.g., `/shopify/callback`).
- **Save and release:** Saving ensures your configuration is stored, and releasing makes the app ready for further setup, such as testing on a development store.

---

## Step 7: Configure Additional App Settings
**Action:** Still in the "Configuration" tab, adjust the following settings:
- **Embed in Shopify admin:** Set to "False" since your app doesn't need to be embedded in Shopify's admin interface.
- **Event version:** Select "2025-04 (Latest)" to use the latest webhook and event version.
- **Compliance webhooks:** Leave the customer data request, customer data erasure, and shop data erasure endpoints blank for now, as they're not required for initial testing.
Click "Save and release" again to confirm the changes.

**Screenshot Reference:** The sixth screenshot shows the "Configuration" tab with the embed option, event version, and compliance webhooks sections.

**Why?**
- **Embed in Shopify admin:** Setting this to "False" means your app operates independently and doesn't need to be loaded within Shopify's admin UI, which suits a standalone FastAPI app.
- **Event version:** Using the latest version ensures compatibility with the most recent Shopify API features and webhook formats.
- **Compliance webhooks:** These are required for public apps to handle data privacy requests (e.g., GDPR compliance). For now, since you're in development, you can skip these and add them later before making your app public.

---

## Step 8: Retrieve Your App Credentials and Test the App
**Action:** Navigate to the "Overview" tab of your app to find the **Client ID** and **Client Secret**. Copy these values into your `.env` file as `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`, along with the `SHOPIFY_REDIRECT_URI` (e.g., `https://upgraded-space-potato-9vqxrgx5wc59q7-5000.app.github.dev/shopify/callback`). Then, in the "Test your app" section, click "Select store" and choose your development store (`acme-7cu19ngr`).

**Screenshot Reference:** The seventh screenshot shows the "Overview" tab with the Client ID, Client Secret, and "Test your app" section, along with the latest app history showing the store installation.

**Why?**
- **Client ID and Client Secret:** These credentials authenticate your FastAPI app with Shopify's OAuth system, similar to the Facebook setup in Chapter 2. The Client ID identifies your app, and the Client Secret is used to exchange the authorization code for an access token.
- **Storing in `.env`:** Keeping these values in a `.env` file ensures security and flexibility, as explained in previous chapters.
- **Test your app:** Linking your app to a development store allows you to install and test it, verifying that the OAuth flow and API interactions work as expected.
- **App history:** The history log confirms that your app was installed on the store (`acme-7cu19ngr`) on May 22, 2025, at 3:04 AM, indicating a successful setup.

---

## Summary: Why These Steps Matter
- **Development Environment:** Creating a Shopify development store provides a safe space to test your app without impacting live stores.
- **App Setup:** Configuring your app in the Shopify Partners dashboard generates the credentials needed for OAuth and API access, enabling your FastAPI app to interact with Shopify.
- **Testing Readiness:** Installing the app on your development store ensures you can test the OAuth flow and API functionality, preparing you for further development and eventual deployment.
- **Compliance and Compatibility:** Setting the event version and understanding compliance webhooks prepares your app for production, even if those features aren't needed during initial testing.

With your Shopify development store and app set up, you're ready to integrate these credentials into your FastAPI project and test the OAuth flow with Shopify's API.
