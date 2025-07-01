Chapter 1: Facebook Integration
Subchapter 1.3: Launching and Testing Facebook OAuth
This subchapter guides you through launching the FastAPI application built in Subchapter 1.1 and testing the Facebook OAuth flow configured with the app credentials from Subchapter 1.2. We’ll start the server, verify the root endpoint, initiate the OAuth process via /facebook/login, and confirm the callback response at /facebook/callback. Each step includes expected outputs (e.g., server logs, JSON responses) and references to screenshots (not provided) to ensure the integration works correctly. This process confirms that your app can authenticate with Facebook and retrieve access tokens and page data for the GPT Messenger sales bot, completing the Facebook integration before moving to Shopify in Chapter 2.

Step 1: Launch the FastAPI Application
Action: Navigate to your project directory and run the FastAPI application using the following command:
python app.py

Expected Output: The terminal displays Uvicorn server logs indicating the app is running:
INFO:     Will watch for changes in these directories: ['/workspaces/facebook-gpt-shopify']
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
INFO:     Started reloader process [88929] using StatReload
INFO:     Started server process [88932]
INFO:     Waiting for application startup.
INFO:     Application startup complete.

Screenshot Reference: Terminal showing the Uvicorn logs above.
Why?

Running python app.py starts the FastAPI server using Uvicorn, as configured in Subchapter 1.1’s app.py.
The logs confirm the server is listening on http://0.0.0.0:5000 with auto-reload enabled for development.
In GitHub Codespaces, the server is accessible via a public URL (e.g., https://your-codespace-id-5000.app.github.dev), necessary for OAuth redirects.


Step 2: Test the Root Endpoint
Action: Open a browser and navigate to the root URL of your application:

Local: http://localhost:5000
GitHub Codespaces: Your public URL, e.g., https://your-codespace-id-5000.app.github.dev

Expected Output: The browser displays:
{
  "status": "ok",
  "message": "Use /facebook/login for OAuth"
}

Screenshot Reference: Browser window showing the JSON response above.
Why?

The root endpoint (@app.get("/") in Subchapter 1.1’s app.py) returns a JSON response to confirm the FastAPI server is running correctly.
The message field guides users to the OAuth endpoint, preparing for the next step.
In Codespaces, the public URL ensures external access, critical for testing OAuth redirects.


Step 3: Initiate Facebook OAuth
Action: Navigate to the Facebook OAuth login endpoint:

Local: http://localhost:5000/facebook/login
GitHub Codespaces: https://your-codespace-id-5000.app.github.dev/facebook/login

Expected Output: The browser redirects to a Facebook OAuth dialog URL, e.g.:
https://www.facebook.com/v19.0/dialog/oauth?client_id=your_app_id&redirect_uri=...

The Facebook page displays a prompt like:
Facebook
Reconnect to messenger-gpt-shopify?
This will re-establish your previous settings for this connection.
[Edit previous settings]
By continuing, messenger-gpt-shopify will receive ongoing access to the information you share and Meta will record when messenger-gpt-shopify accesses it. Learn more about this sharing and the settings you have.
[Cancel] [Continue]

Screenshot Reference: Facebook OAuth dialog with the reconnect prompt for messenger-gpt-shopify.
Why?

The /facebook/login endpoint (Subchapter 1.1, facebook_oauth/routes.py) constructs the OAuth URL with client_id (from Subchapter 1.2), redirect_uri, scopes (pages_messaging, pages_show_list), and a CSRF state token.
The redirect to Facebook’s OAuth dialog confirms the app is correctly initiating authentication.
The “Reconnect” prompt may appear if the app was previously authorized (common during testing), indicating the messenger-gpt-shopify app (Subchapter 1.2) is requesting permissions.


Step 4: Authorize the App
Action: Click "Continue" (or “Reconnect”) on the Facebook OAuth dialog to authorize the messenger-gpt-shopify app.
Expected Output: The browser redirects to the callback endpoint:

Local: http://localhost:5000/facebook/callback?code=...&state=...
GitHub Codespaces: https://your-codespace-id-5000.app.github.dev/facebook/callback?code=AQDqeAxEI53Puc9Sv31VbkK2JwbJRKDp9vDNG99cC9mSLVDot4ahBkGVMmRYwFhQ42VzO9kYlnrHbbOiz_o_odW6wOEY-rSoDObi0QJMu4NGJeBRDIIFdfvHEGXlbsRZ-eGWHu5hQt2h1xGpgMiwFNp4jCp7I_zsargoTNW3RBC2ueKPw694UOAUenRP7jszrjQgMID_2fhuZKi7uyh3M2pykWYS7i3K71nkAmU4kFawAOzvI3_jZtpoJA9DiaeXqtOQpzOIMG4w5-HNd-bMnvz_br10_Gon08Xh7vDiFr3Ug1owSiwphEZ-_wuEGZ2D694vvBBwWv2GzNa5IWl-79zzJME7slwQ0Hw9ob8dm1f33h-CsZnbUf4F3Kjma2qI8ZI&state=1751277990%3AMhg1D2nYmAE%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D#_=_

The browser displays a JSON response like:
{
  "token_data": {
    "access_token": "EAA6DtFWoZBscBO4RuMgD36ZCL2orzwZCAAkzhKY7l5ZAYJkNEsLJEB81fjq1oP73M1F4mtQ9ZC9iWlZBEWKFKQcEJ05kwtrumMPzE4NQvw6Rv6u905it7lZBSgfwZC3MdWqaCANIhe4UoHth9pUQZAEDcZAV5ZAkQcsp3o2MDGX5HRAt9rnNMmp4Cn0noo7CSwjLUE0G2eV3hxxZCRmmH9nEf4oZAyW98RzwGWWrOWsuBJYtBtp8GT93xDCMcWajR",
    "token_type": "bearer"
  },
  "pages": {
    "data": [
      {
        "access_token": "EAA6DtFWoZBscBO9NqGBTTDTSNcvBo4S9UmPLPuXNJAnBaZBsUUZBDyK7jZAvSH1WdLWfltta9nlAGK6Y3ZCgvSnnd44Jc3AWTXG0UTEsBg38YFnFZCETG80btSZA2rGFBV2TdW1kRnYRv81W6kZA9hoYw3dTPYCZCg0mTIKRL3xdD6s6b4e5uPXm5M5NMRAd4xeYFVPMZD",
        "category": "Footwear store",
        "category_list": [
          {
            "id": "109512302457693",
            "name": "Footwear store"
          }
        ],
        "name": "Fast Online Store PH",
        "id": "101368371725791",
        "tasks": [
          "MODERATE",
          "MESSAGING",
          "ANALYZE",
          "ADVERTISE",
          "CREATE_CONTENT",
          "MANAGE"
        ]
      }
    ],
    "paging": {
      "cursors": {
        "before": "QVFIUnp5enFBc21kckE2d1pud2g3Mjd1bEFSOUs4ZAEdSSEpIdHZAoSjVPdlgzVHN6aTZAReEpyOWdHMEF3MmJoRmpXNWI3dlFpa3BWLWoza2hMMDd4TzhMSUF3",
        "after": "QVFIUnp5enFBc21kckE2d1pud2g3Mjd1bEFSOUs4ZAEdSSEpIdHZAoSjVPdlgzVHN6aTZAReEpyOWdHMEF3MmJoRmpXNWI3dlFpa3BWLWoza2hMMDd4TzhMSUF3"
      }
    }
  }
}

Screenshot Reference: Browser showing the JSON response with token_data and pages.
Why?

Authorizing the app grants the requested scopes (pages_messaging, pages_show_list), allowing access to Pages and Messenger APIs.
Facebook redirects to the callback URL with a code and state parameter, which the FastAPI app (Subchapter 1.1) validates and exchanges for an access token.
The response confirms successful token exchange (access_token, token_type) and retrieval of page data (pages.data), including a page access token and details (e.g., “Fast Online Store PH”).
The MESSAGING task verifies the app can send Messenger messages, critical for the sales bot.


Step 5: Verify the Integration
Action: Review the JSON response to ensure:

token_data.access_token is present and valid.
pages.data includes at least one page with a valid access_token and MESSAGING in tasks.
No errors (e.g., HTTP 400 for invalid state or code) appear in the browser or server logs.

Expected Outcome:

The response matches the example above, confirming the OAuth flow is working.
Server logs show successful HTTP 200 responses for /facebook/callback, e.g.:

INFO:     127.0.0.1:12345 - "GET /facebook/callback?code=...&state=... HTTP/1.1" 200 OK

Screenshot Reference: Terminal logs showing successful request handling.
Why?

The access tokens enable the sales bot to interact with Facebook’s Messenger API.
Page data confirms access to business pages (e.g., “Fast Online Store PH”), necessary for sending messages.
Verifying MESSAGING ensures the bot’s core functionality is supported.


Step 6: Troubleshooting Common Issues
If issues arise, check the following:

“Missing code parameter”: Ensure FACEBOOK_REDIRECT_URI in .env matches the “Valid OAuth Redirect URIs” in the Facebook app settings (Subchapter 1.2).
“Invalid state token”: Verify STATE_TOKEN_SECRET is set in .env and consistent across requests (Subchapter 1.1).
No pages in response: Confirm the Facebook user has admin access to a business page and the app is in Development Mode (Subchapter 1.2). If in Live Mode, ensure pages_messaging permission is approved by Meta.
404 or 500 errors: Check that the server is running (http://0.0.0.0:5000) and the Codespaces public URL is accessible.
“Invalid App ID”: Verify FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in .env match the values from Subchapter 1.2’s app settings.

Why?

These checks ensure a secure and functional OAuth flow, addressing common setup errors.
Proper configuration prevents issues during testing and prepares the app for production.


Step 7: Example Sales Bot Context
With the OAuth flow working, the sales bot can use the page access_token (from pages.data) to send messages. For example:
Customer: I’m looking for snowboards.Bot: Check out our premium snowboards at Fast Online Store PH! We’ll share some options from our Shopify store soon. Stay tuned!  
This functionality integrates with Shopify data in Chapter 2.

Summary: Why This Subchapter Matters

Server Verification: Launching the app and checking the root endpoint confirms the FastAPI setup from Subchapter 1.1 is operational.
OAuth Flow: Initiating and completing the OAuth process tests the integration with Facebook’s API, using credentials from Subchapter 1.2.
Callback Success: The /facebook/callback response verifies that the OAuth logic and credentials are correctly implemented, providing access tokens and page data.
Bot Readiness: The MESSAGING task and page access tokens prepare the app for Messenger interactions, enabling the sales bot to engage customers.

Next Steps:

Review the Facebook OAuth implementation (Subchapter 1.1) and app setup (Subchapter 1.2) if issues arise.
Proceed to Chapter 2 for Shopify integration, starting with creating a Shopify development store and app (Subchapter 2.1).
