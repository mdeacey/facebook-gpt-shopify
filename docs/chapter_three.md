Chapter 3: Launching and Testing the FastAPI Application for Facebook OAuth
This chapter guides you through launching the FastAPI application, testing the root endpoint, and verifying the Facebook OAuth flow set up in Chapters 1 and 2. We’ll run the app, check the initial response, initiate the OAuth process via /facebook/login, and confirm the callback response at /facebook/callback. Each step includes expected outputs (e.g., server logs, JSON responses) and references to screenshots (not provided) to ensure the integration works correctly. This process confirms that your app can authenticate with Facebook and retrieve access tokens and page data for the GPT Messenger sales bot.

Step 1: Launch the FastAPI Application
Action: Navigate to your project directory and run the FastAPI application using the following command:
python app.py

Expected Output: The terminal should display Uvicorn server logs indicating the app is running:
INFO:     Will watch for changes in these directories: ['/workspaces/facebook-gpt-shopify']
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
INFO:     Started reloader process [88929] using StatReload
INFO:     Started server process [88932]
INFO:     Waiting for application startup.
INFO:     Application startup complete.

Screenshot Reference: Terminal showing the Uvicorn logs above.
Why?

Running python app.py starts the FastAPI server using Uvicorn, as configured in app.py (Chapter 1).
The logs confirm the server is listening on http://0.0.0.0:5000 with auto-reload enabled for development.
If using GitHub Codespaces, the server is accessible via a public URL (e.g., https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev).


Step 2: Test the Root Endpoint
Action: Open a browser and navigate to the root URL of your application:

Local: http://localhost:5000
GitHub Codespaces: Your public URL, e.g., https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev

Expected Output: The browser should display:
{"status":"ok"}

Screenshot Reference: Browser window showing the JSON response {"status":"ok"}.
Why?

The root endpoint (@app.get("/") in app.py) returns a simple JSON response to confirm the FastAPI server is running correctly.
This verifies that the server is accessible and responding as expected before testing the OAuth flow.
In GitHub Codespaces, the public URL ensures external access, critical for OAuth redirects.


Step 3: Initiate Facebook OAuth
Action: Navigate to the Facebook OAuth login endpoint:

Local: http://localhost:5000/facebook/login
GitHub Codespaces: https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev/facebook/login

Expected Output: The browser redirects to a Facebook OAuth dialog URL, e.g.:
https://m.facebook.com/v19.0/dialog/oauth?encrypted_query_string=...

The Facebook page displays a prompt like:
Facebook
Reconnect Shan Garcia to messenger-gpt-shopify?
This will re-establish your previous settings for this connection.
Edit previous settings.
By continuing, messenger-gpt-shopify will receive ongoing access to the information you share and Meta will record when messenger-gpt-shopify accesses it. Learn more about this sharing and the settings you have.

Screenshot Reference: Facebook OAuth dialog with the reconnect prompt for messenger-gpt-shopify.
Why?

The /facebook/login endpoint (Chapter 1, facebook_oauth/routes.py) constructs the OAuth URL with client_id, redirect_uri, scope (pages_messaging,pages_show_list), and a CSRF state token.
The redirect to Facebook’s OAuth dialog confirms that the app is correctly initiating authentication.
The prompt indicates the app (messenger-gpt-shopify, from Chapter 2) is requesting permissions, and “Reconnect” suggests prior authorization (normal for testing).


Step 4: Authorize the App
Action: Click Reconnect (or “Continue”) on the Facebook OAuth dialog to authorize the app.
Expected Output: The browser briefly shows a temporary forwarding URL, then redirects to the callback endpoint:

Local: http://localhost:5000/facebook/callback?code=...&state=...
GitHub Codespaces: https://stunning-journey-7qr6jxj5j7frg67-5000.app.github.dev/facebook/callback?code=AQDqeAxEI53Puc9Sv31VbkK2JwbJRKDp9vDNG99cC9mSLVDot4ahBkGVMmRYwFhQ42VzO9kYlnrHbbOiz_o_odW6wOEY-rSoDObi0QJMu4NGJeBRDIIFdfvHEGXlbsRZ-eGWHu5hQt2h1xGpgMiwFNp4jCp7I_zsargoTNW3RBC2ueKPw694UOAUenRP7jszrjQgMID_2fhuZKi7uyh3M2pykWYS7i3K71nkAmU4kFawAOzvI3_jZtpoJA9DiaeXqtOQpzOIMG4w5-HNd-bMnvz_br10_Gon08Xh7vDiFr3Ug1owSiwphEZ-_wuEGZ2D694vvBBwWv2GzNa5IWl-79zzJME7slwQ0Hw9ob8dm1f33h-CsZnbUf4F3Kjma2qI8ZI&state=1751277990%3AMhg1D2nYmAE%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D#_=_

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

Clicking “Reconnect” authorizes the app (messenger-gpt-shopify) to access the requested scopes.
Facebook redirects to the callback URL with a code and state parameter, which the FastAPI app validates and exchanges for an access token (Chapter 1, facebook_oauth/utils.py).
The JSON response confirms successful token exchange (access_token, token_type) and retrieval of page data (pages.data), including a page access token and details (e.g., “Fast Online Store PH”).
The presence of MESSAGING in tasks verifies the app can send Messenger messages, critical for the sales bot.


Step 5: Verify the Integration
Action: Review the JSON response to ensure:

token_data.access_token is present and valid.
pages.data includes at least one page with a valid access_token and MESSAGING in tasks.
No errors (e.g., HTTP 400 for invalid state or code) appear in the browser or server logs.

Expected Outcome:

The response matches the example above, indicating the OAuth flow is working.
Server logs show no errors, only successful HTTP 200 responses for /facebook/callback.

Screenshot Reference: Terminal logs showing successful request handling.
Why?

The access tokens enable the app to interact with Facebook’s Messenger API for the sales bot.
The page data confirms the app has access to the required resources (e.g., a business page like “Fast Online Store PH”).
Verifying MESSAGING ensures the bot can send messages, aligning with the project’s goals.


Troubleshooting Common Issues

“Missing code parameter”: Ensure the redirect URL in .env (FACEBOOK_REDIRECT_URI) matches the “Valid OAuth Redirect URIs” in the Facebook app settings (Chapter 2).
“Invalid state token”: Verify STATE_TOKEN_SECRET is set in .env and consistent across requests.
No pages in response: Check that the Facebook user has admin access to a business page and the app is in Development Mode or Live Mode with approved permissions.
404 or 500 errors: Confirm the server is running (http://0.0.0.0:5000) and the public URL is accessible in GitHub Codespaces.

Why?

These checks ensure the OAuth flow is robust and handles edge cases, maintaining security and functionality.


Summary: Why This Testing Matters

Server Verification: Running python app.py and checking the root endpoint confirms the FastAPI server is operational.
OAuth Flow: Navigating to /facebook/login and completing the OAuth process tests the integration with Facebook’s API.
Callback Success: The /facebook/callback response with token_data and pages verifies that credentials (Chapter 2) and OAuth logic (Chapter 1) are correctly implemented.
Bot Readiness: Access tokens and page data prepare the app for Messenger interactions in the GPT sales bot.

With the Facebook OAuth flow working, you’re ready to set up the Shopify OAuth integration (subsequent chapters) to fetch product data for the bot.