Chapter 1: Facebook Integration
Subchapter 1.2: Adding a Facebook App for OAuth Integration
This subchapter guides you through creating a Facebook app in the Meta Developer Portal to obtain the credentials (FACEBOOK_APP_ID and FACEBOOK_APP_SECRET) required for the OAuth flow implemented in Subchapter 1.1. These credentials enable your FastAPI application to authenticate with Facebook’s API, accessing Pages and Messenger APIs for the GPT Messenger sales bot. We outline each step, explain the reasoning, and reference screenshots (not provided) for clarity. This subchapter builds on the FastAPI setup in Subchapter 1.1 and prepares for testing in Subchapter 1.3.

Step 1: Access the Meta Developer Portal and Navigate to Apps
Action: Log into the Meta Developer Portal at developers.facebook.com. In the top navigation bar, click "My Apps" to access the apps management page.
Screenshot Reference: Shows the "My Apps" page with a "Create App" button, indicating no apps exist yet.
Why?

The "My Apps" section manages all your applications that interact with Meta’s APIs, including Facebook’s OAuth and Messenger APIs.
Since you’re starting fresh (likely with "No apps yet"), creating a new app is the first step to generate the credentials needed for OAuth.


Step 2: Start Creating a New App
Action: On the "My Apps" page, click the green "Create App" button in the top-right corner.
Screenshot Reference: Highlights the "Create App" button on the "My Apps" page.
Why?

The "Create App" button initiates the app creation process, allowing you to configure a new application for OAuth integration.
This app will handle permissions (e.g., pages_messaging, pages_show_list) and OAuth flows for your FastAPI backend, as implemented in Subchapter 1.1.


Step 3: Enter App Details
Action: In the "Create an app" form, fill in the following fields:

App name: Enter messenger-gpt-shopify to reflect the app’s purpose (integrating Messenger with Shopify).
App contact email: Provide a valid email, e.g., your-email@example.com.
Business portfolio: Leave as "No business portfolio selected" unless you need business-specific features (e.g., ads management).

Click "Next" to proceed.
Screenshot Reference: Shows the "App details" tab with the app name and email filled in.
Why?

App name: Identifies your app in the Meta Developer Portal and during OAuth prompts. messenger-gpt-shopify clearly ties to the sales bot’s functionality.
App contact email: Ensures Meta can send updates (e.g., policy changes, app restrictions). Use an email you monitor regularly.
Business portfolio: Optional for this project, as the app focuses on Messenger and Page access, not business-specific features.


Step 4: Select the App Use Case
Action: In the "Use cases" tab, review the predefined use cases (e.g., "Access the Threads API") and select "Other" at the bottom.
Screenshot Reference: Shows the "Use cases" tab with "Other" selected.
Why?

Meta’s predefined use cases streamline setup for common scenarios, but "Other" is suitable for custom integrations like your FastAPI OAuth flow for the sales bot.
Selecting "Other" allows manual configuration of permissions (pages_messaging, pages_show_list) in later steps, aligning with Subchapter 1.1’s requirements.


Step 5: Choose the App Type
Action: In the "Type" tab, select "Business" as the app type.
Screenshot Reference: Shows the "Type" tab with "Business" selected.
Why?

Business type suits apps managing business assets (e.g., Pages, Messenger interactions), matching the sales bot’s goal of sending product promotions via Messenger.
This choice enables access to the required scopes (pages_messaging, pages_show_list), critical for Subchapter 1.1’s implementation.
Note: App type is permanent, so "Business" ensures compatibility with the bot’s functionality.


Step 6: Review and Create the App
Action: Return to the "App details" tab to review your inputs (app name, email, app type). Ensure all details are correct. Agree to Meta’s Platform Terms and Developer Policies by checking the required box (if prompted). Click the green "Create app" button to finalize.
Screenshot Reference: Shows the "App details" tab with a checkmark on the "Type" tab and the "Create app" button highlighted.
Why?

Review: Verifies no errors (e.g., typos in email) that could cause issues, such as missed notifications.
Terms and Policies: Mandatory for app creation, ensuring compliance with Meta’s rules on API usage and data handling.
Create App: Registers the app, generating the FACEBOOK_APP_ID and FACEBOOK_APP_SECRET needed for OAuth.


Step 7: Retrieve App Credentials
Action: After creation, navigate to the app’s "Settings > Basic" page in the Meta Developer Portal. Locate the App ID and App Secret (click "Show" to reveal the secret, if hidden). Copy these values into your .env file as follows:
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback

For GitHub Codespaces, use the public URL:
FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback

Screenshot Reference: Shows the "Settings > Basic" page with App ID and App Secret fields.
Why?

App ID and App Secret: Authenticate your FastAPI app with Facebook’s OAuth system, as used in Subchapter 1.1’s /facebook/login and /facebook/callback endpoints.
Redirect URI: Must match the callback endpoint in Subchapter 1.1 and be added to the app’s "Facebook Login > Settings > Valid OAuth Redirect URIs" field (do this after app creation).
Environment File: Storing credentials in .env (excluded by .gitignore) enhances security, as outlined in Subchapter 1.1.


Step 8: Configure OAuth Redirect URI
Action: In the Meta Developer Portal, go to "Products", add "Facebook Login" (if not already added), and navigate to "Facebook Login > Settings". In the "Valid OAuth Redirect URIs" field, enter the redirect URI from your .env file (e.g., http://localhost:5000/facebook/callback or the Codespaces URL). Save changes.
Screenshot Reference: Shows the "Facebook Login > Settings" page with the redirect URI field.
Why?

The redirect URI must match the FACEBOOK_REDIRECT_URI used in Subchapter 1.1’s OAuth flow to ensure Facebook redirects back to your app after authentication.
This step prevents “Invalid redirect URI” errors during testing (Subchapter 1.3).
For Codespaces, the public URL ensures external accessibility.


Step 9: Set App to Development Mode
Action: In the app’s "Settings > Basic" page, ensure the app is in Development Mode (default for new apps). This restricts access to users with a role in the app (e.g., Admin, Developer), suitable for testing.
Screenshot Reference: Shows the app status toggle set to "Development Mode".
Why?

Development Mode limits API access to authorized users, ideal for testing in Subchapter 1.3 without requiring public app approval.
You can switch to Live Mode later, after testing, if the app needs public access (requires Meta’s permission review for pages_messaging).


Step 10: Testing Preparation
To verify the app setup:

Update your .env file with the FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, and FACEBOOK_REDIRECT_URI from this subchapter.
Ensure the redirect URI is added to the app’s "Facebook Login > Settings".
Run the FastAPI app (python app.py, from Subchapter 1.1) and navigate to /facebook/login to initiate OAuth (detailed testing in Subchapter 1.3).

Note: If you encounter errors (e.g., “Invalid App ID”), double-check the credentials in .env against the portal’s values.

Summary: Why This Subchapter Matters

Credentials Acquisition: Creates a Facebook app to obtain FACEBOOK_APP_ID and FACEBOOK_APP_SECRET, essential for the OAuth flow in Subchapter 1.1.
OAuth Setup: Configures the redirect URI and app type, enabling secure authentication with Facebook’s API.
Compliance: Adhering to Meta’s terms and using Development Mode ensures a safe testing environment.
Bot Readiness: Prepares the app for Messenger integration, allowing the sales bot to send messages (tested in Subchapter 1.3).

Next Steps:

Implement the FastAPI OAuth flow (Subchapter 1.1, already completed) using these credentials.
Test the OAuth flow to verify authentication and page data retrieval (Subchapter 1.3).
Proceed to Shopify integration (Chapter 2) for product data.
