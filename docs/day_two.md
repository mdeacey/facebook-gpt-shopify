# Chapter 2: Adding a Facebook App for OAuth Integration

This chapter guides you through the process of creating a Facebook app to obtain the necessary credentials (App ID and App Secret) for your FastAPI OAuth integration. These credentials are critical for authenticating your application with Facebook's API. We'll use the provided screenshots to outline each step and explain the reasoning behind each action.

---

## Step 1: Access the Facebook Developer Portal and Navigate to Apps
**Action:** Log into the Facebook Developer Portal (likely at `developers.facebook.com`). Once logged in, locate the "Apps" section in the navigation bar at the top and click on it.

**Screenshot Reference:** The first screenshot shows the "Apps" page with a "Create App" button.

**Why?**
- The "Apps" section is where you manage all your applications that interact with Facebook's APIs.
- Since you’re starting fresh (as indicated by "No apps yet"), you need to create a new app to generate the credentials required for OAuth.

---

## Step 2: Start Creating a New App
**Action:** On the "Apps" page, click the green "Create App" button located at the top right.

**Screenshot Reference:** The first screenshot highlights the "Create App" button.

**Why?**
- Clicking "Create App" initiates the process of setting up a new application in the Facebook Developer Portal.
- This app will serve as the entity that requests permissions (like `pages_messaging` and `pages_show_list`) and handles OAuth flows for your FastAPI backend.

---

## Step 3: Enter App Details (App Name and Contact Email)
**Action:** In the "Create an app" form, fill in the following fields:
- **App name:** Enter a descriptive name, such as `messenger-gpt-shopify` (as shown in the screenshot).
- **App contact email:** Provide a valid email address, like `marcusdeacey@gmail.com`.
- Leave the "Business portfolio" field as "No business portfolio selected" unless you need specific business-related permissions.

**Screenshot Reference:** The second screenshot shows the "App details" tab with the fields filled out.

**Why?**
- **App name:** This name identifies your app in the Facebook Developer Portal and on your "My Apps" page. It should reflect the app’s purpose (e.g., integrating with Messenger for a Shopify app).
- **App contact email:** Facebook uses this email to communicate important updates, such as policy changes, app restrictions, or deletion notices. It ensures you stay informed.
- **Business portfolio:** This is optional unless your app requires business-specific permissions (e.g., managing ads). For a basic OAuth setup, you can skip this.

---

## Step 4: Select the App Use Case
**Action:** Click "Next" to proceed to the "Use cases" tab. Review the available use cases and select "Other" at the bottom.

**Screenshot Reference:** The third screenshot shows the "Use cases" tab with "Other" selected.

**Why?**
- Facebook provides predefined use cases (e.g., "Access the Threads API," "Launch a game on Facebook") to streamline permission and feature selection for common scenarios.
- Selecting "Other" is appropriate when your app doesn’t fit a predefined use case, such as a custom OAuth integration for FastAPI. This option allows you to manually choose permissions and features in the next steps.

---

## Step 5: Choose the App Type
**Action:** Click "Next" to move to the "Type" tab. Select "Negosyo" (Business) as the app type.

**Screenshot Reference:** The fourth screenshot shows the "Type" tab with "Negosyo" selected.

**Why?**
- **App Type:** Facebook requires you to specify whether your app is for business ("Negosyo") or consumer use. "Negosyo" is suitable for apps that manage business assets (e.g., Pages, Ads, or Messenger interactions), which aligns with the scopes (`pages_messaging`, `pages_show_list`) used in your FastAPI app.
- This choice impacts the permissions and features available to your app. For example, a business app can access Messenger APIs for customer interactions, which is likely your goal with `messenger-gpt-shopify`.
- Note: The app type cannot be changed after creation, so choose carefully.

---

## Step 6: Review and Create the App
**Action:** Click "Next" to return to the "App details" tab, which now shows a summary with a checkmark on the "Type" tab indicating completion. Verify that all details (app name, contact email) are correct. Agree to the Meta Platform Terms and Developer Policies by proceeding. Finally, click the green "Create app" button.

**Screenshot Reference:** The fifth screenshot shows the "App details" tab with the "Type" tab marked as complete, and the "Create app" button.

**Why?**
- **Review:** Double-checking the app name and email ensures there are no typos or errors that could cause issues later (e.g., notifications going to the wrong email).
- **Terms and Policies:** Agreeing to Meta’s terms is mandatory to create the app. These terms govern how you can use Facebook’s APIs and handle user data, ensuring compliance with privacy and security standards.
- **Create App:** This final action registers your app with Facebook, generating the App ID and App Secret needed for OAuth. After creation, you’ll be able to access these credentials in the app’s settings.

---

## Step 7: Retrieve Your App Credentials
**Action:** After creating the app, navigate to the app’s settings in the Facebook Developer Portal to find your **App ID** and **App Secret**. Copy these values and add them to your `.env` file as `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET`, along with the `FACEBOOK_REDIRECT_URI` (e.g., `http://localhost:5000/facebook/callback`).

**Why?**
- **App ID and App Secret:** These credentials authenticate your FastAPI app with Facebook’s OAuth system. The App ID identifies your app, while the App Secret is a private key used to securely exchange the authorization code for an access token.
- **Storing in `.env`:** Keeping these sensitive values in a `.env` file (as outlined in Chapter 1) ensures they are not hardcoded in your codebase, enhancing security and making configuration easier across environments (e.g., development, production).

---

## Summary: Why These Steps Matter
- **Correct Setup:** Creating a Facebook app properly ensures you have the credentials and permissions needed for OAuth integration.
- **Security and Compliance:** Providing a valid contact email and agreeing to Meta’s terms keeps your app compliant and ensures you receive important updates.
- **Flexibility:** Choosing the "Negosyo" type and "Other" use case allows your app to access the specific permissions (`pages_messaging`, `pages_show_list`) required for your FastAPI project.
- **Preparation for OAuth:** The App ID and App Secret are essential for the OAuth flow in your FastAPI routes, enabling secure communication with Facebook’s API.

With your Facebook app created, you’re ready to integrate these credentials into your FastAPI project (as shown in Chapter 1) and proceed with testing the OAuth flow.