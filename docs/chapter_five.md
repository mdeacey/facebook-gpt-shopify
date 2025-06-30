Here’s the updated **Chapter 4** focused entirely on **creating the Shopify development store and app for API integration**, as you specified — separate from the code in Chapter 3 and detailed with step-by-step instructions and reasoning.

---

# Chapter 4: Creating a Shopify Development Store and App for API Integration

This chapter walks you through creating a Shopify development store and setting up a new app within the Shopify Partners dashboard. These steps are essential for obtaining the credentials (API Key and Secret Key) needed for your FastAPI integration with Shopify’s API. We include screenshots references and explain the reasoning behind each action.

---

## Step 1: Access the Shopify Partners Dashboard and Navigate to Stores

**Action:** Log into the Shopify Partners dashboard at [partners.shopify.com](https://partners.shopify.com). In the left sidebar, locate and click on **"Stores"**.

**Screenshot Reference:** Shows the Partners dashboard with the "Stores" section selected, no stores listed.

**Why?**

* The "Stores" section manages all your Shopify development stores.
* Since this is your first store, you will see "No stores found" and need to create a new development store.

---

## Step 2: Create a New Development Store

**Action:** On the "Stores" page, click the green **"Add store"** button in the top-right, then select **"Create development store"** from the dropdown.

**Screenshot Reference:** Highlights the "Add store" button and "Create development store" option.

**Why?**

* Development stores provide sandbox environments for testing apps and themes without affecting live stores.
* They are non-transferable and ideal for testing your FastAPI app integration safely.

---

## Step 3: Configure the Development Store Details

**Action:** Fill out the "Create a store for a client" form:

* **Store name:** Enter a unique name like `acme-7cu19ngr`.
* **Build version:** Select **"Current release"** to use the latest Shopify version.
* **Data and configurations:** Choose **"Start with test data"** to pre-populate with sample products and customers.

Click the green **"Create development store"** button to proceed.

**Screenshot Reference:** Shows the filled form with store name, build version, and data options.

**Why?**

* Unique store name creates the store’s URL (`acme-7cu19ngr.myshopify.com`).
* Using the current release ensures you test with the latest API versions.
* Test data saves time by providing sample content to experiment with your app.

---

## Step 4: Navigate to Apps and Create a New App

**Action:** Back in the Shopify Partners dashboard, click **"Apps"** in the left sidebar, then select **"All apps"**. Click the green **"Create app"** button.

**Screenshot Reference:** Shows the "Apps" page with the "Create app" button highlighted.

**Why?**

* The Apps section manages apps that connect to Shopify APIs.
* Creating a new app generates the credentials (API Key, Secret Key) your FastAPI app needs.

---

## Step 5: Create the App Manually

**Action:** On the "Create a new app" page, click **"Create app manually"**.

**Screenshot Reference:** Shows the "Create app manually" button.

**Why?**

* Manual creation gives you full control over app configuration.
* It’s suitable for custom FastAPI integrations requiring tailored setup.

---

## Step 6: Configure the App Details and URLs

**Action:** Name your app `messenger-gpt`. Go to the **Configuration** tab and fill in:

* **App URL:** `https://your-fastapi-app-url` (e.g., `https://upgraded-space-potato-9vqxrgx5wc59q7-5000.app.github.dev`)
* **Allowed redirection URL(s):** `https://your-fastapi-app-url/shopify/callback`

Click **"Save and release"**.

**Screenshot Reference:** Shows app configuration with name and URLs.

**Why?**

* App URL is the base URL your FastAPI app listens on.
* Allowed redirection URLs are critical for OAuth to securely redirect users after authentication.
* Saving applies your configuration.

---

## Step 7: Configure Additional App Settings

**Action:** In the Configuration tab:

* Set **Embed in Shopify admin** to **False**.
* Set **Event version** to **2025-04 (Latest)**.
* Leave **Compliance webhooks** (customer/shop data erasure) blank for now.

Click **"Save and release"** again.

**Screenshot Reference:** Shows embed setting, event version, and compliance webhook options.

**Why?**

* Not embedding keeps the app standalone (not inside Shopify admin UI).
* Using the latest event version ensures webhook compatibility.
* Compliance webhooks can be added later before public release.

---

## Step 8: Retrieve App Credentials and Test the App

**Action:** Go to the **Overview** tab of your app. Copy the **API Key** and **API Secret Key** into your `.env` file as `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET`, respectively. Also set `SHOPIFY_REDIRECT_URI` to your callback URL.

In the **Test your app** section, click **Select store**, choose your development store (`acme-7cu19ngr`), and install the app.

**Screenshot Reference:** Shows Overview tab with API credentials and installation history.

**Why?**

* Credentials authenticate your FastAPI app with Shopify’s OAuth system.
* Testing app installation on your dev store verifies the OAuth flow and API access work correctly.

---

## Summary: Why These Steps Matter

* **Safe Testing Environment:** Development stores isolate your tests from live data.
* **App Credentials:** Generate API keys required for OAuth and API access.
* **OAuth Redirects:** Proper URLs ensure secure authentication flows.
* **Testing Readiness:** Installing the app on a dev store verifies integration before production.
* **Future Compliance:** Event versions and webhook settings prepare your app for eventual public release.

---

With your Shopify development store and app ready, you’re set to integrate these credentials into your FastAPI project and test the Shopify OAuth flow as implemented in Chapter 3.

---

If you want, I can also help you prepare a `.env.example` snippet reflecting these credentials or any other follow-up docs!
