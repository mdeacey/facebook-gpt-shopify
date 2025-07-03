# Chapter 1: Facebook Integration
## Subchapter 1.3: Launching and Testing Facebook OAuth

This subchapter guides you through launching the FastAPI application built in Subchapter 1.1 and testing the Facebook OAuth flow configured with the app credentials from Subchapter 1.2. We’ll start the server, verify the root endpoint, initiate the OAuth process via `/facebook/login`, and confirm the callback response at `/facebook/callback`. Each step includes expected outputs (e.g., server logs, JSON responses) and references to screenshots (not provided) to ensure the integration works correctly. This process confirms that your app can authenticate with Facebook and retrieve comprehensive non-sensitive page data for the GPT Messenger sales bot, completing the Facebook integration before moving to Shopify in Chapter 2.

### Step 1: Launch the FastAPI Application
**Action**: Navigate to your project directory and run the FastAPI application using the following command:
```bash
python app.py
```

**Expected Output**: The terminal displays Uvicorn server logs indicating the app is running:
```
INFO:     Will watch for changes in these directories: ['/workspaces/facebook-gpt-shopify']
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
INFO:     Started reloader process [88929] using StatReload
INFO:     Started server process [88932]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Screenshot Reference**: Terminal showing the Uvicorn logs above.
**Why?**
- Running `python app.py` starts the FastAPI server using Uvicorn, as configured in Subchapter 1.1’s `app.py`.
- The logs confirm the server is listening on `http://0.0.0.0:5000` with auto-reload enabled for development.
- In GitHub Codespaces, the server is accessible via a public URL (e.g., `https://your-codespace-id-5000.app.github.dev`), necessary for OAuth redirects.

### Step 2: Test the Root Endpoint
**Action**: Open a browser and navigate to the root URL of your application:
- **Local**: `http://localhost:5000`
- **GitHub Codespaces**: Your public URL, e.g., `https://your-codespace-id-5000.app.github.dev`

**Expected Output**: The browser displays:
```json
{
  "status": "ok",
  "message": "Use /facebook/login for OAuth"
}
```

**Screenshot Reference**: Browser window showing the JSON response above.
**Why?**
- The root endpoint (`@app.get("/")` in Subchapter 1.1’s `app.py`) returns a JSON response to confirm the FastAPI server is running correctly.
- The `message` field guides users to the OAuth endpoint, preparing for the next step.
- In Codespaces, the public URL ensures external access, critical for testing OAuth redirects.

### Step 3: Initiate Facebook OAuth
**Action**: Navigate to the Facebook OAuth login endpoint:
- **Local**: `http://localhost:5000/facebook/login`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev/facebook/login`

**Expected Output**: The browser redirects to a Facebook OAuth dialog URL, e.g.:
```
https://www.facebook.com/v19.0/dialog/oauth?client_id=your_app_id&redirect_uri=...
```

The Facebook page displays a prompt like:
```
Facebook
Reconnect to messenger-gpt-shopify?
This will re-establish your previous settings for this connection.
[Edit previous settings]
By continuing, messenger-gpt-shopify will receive ongoing access to the information you share and Meta will record when messenger-gpt-shopify accesses it. Learn more about this sharing and the settings you have.
[Cancel] [Continue]
```

**Screenshot Reference**: Facebook OAuth dialog with the reconnect prompt for `messenger-gpt-shopify`.
**Why?**
- The `/facebook/login` endpoint (Subchapter 1.1, `facebook_oauth/routes.py`) constructs the OAuth URL with `client_id` (from Subchapter 1.2), `redirect_uri`, scopes (`pages_messaging`, `pages_show_list`, `pages_manage_metadata`), and a CSRF state token.
- The redirect to Facebook’s OAuth dialog confirms the app is correctly initiating authentication.
- The “Reconnect” prompt may appear if the app was previously authorized (common during testing), indicating the `messenger-gpt-shopify` app (Subchapter 1.2) is requesting permissions.

### Step 4: Authorize the App
**Action**: Click "Continue" (or “Reconnect”) on the Facebook OAuth dialog to authorize the `messenger-gpt-shopify` app.

**Expected Output**: The browser redirects to the callback endpoint:
- **Local**: `http://localhost:5000/facebook/callback?code=...&state=...`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev/facebook/callback?code=AQDqeAxEI53Puc9Sv31VbkK2JwbJRKDp9vDNG99cC9mSLVDot4ahBkGVMmRYwFhQ42VzO9kYlnrHbbOiz_o_odW6wOEY-rSoDObi0QJMu4NGJeBRDIIFdfvHEGXlbsRZ-eGWHu5hQt2h1xGpgMiwFNp4jCp7I_zsargoTNW3RBC2ueKPw694UOAUenRP7jszrjQgMID_2fhuZKi7uyh3M2pykWYS7i3K71nkAmU4kFawAOzvI3_jZtpoJA9DiaeXqtOQpzOIMG4w5-HNd-bMnvz_br10_Gon08Xh7vDiFr3Ug1owSiwphEZ-_wuEGZ2D694vvBBwWv2GzNa5IWl-79zzJME7slwQ0Hw9ob8dm1f33h-CsZnbUf4F3Kjma2qI8ZI&state=1751277990%3AMhg1D2nYmAE%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D#_=_`

The browser displays a JSON response like:
```json
{
  "pages": {
    "data": [
      {
        "id": "101368371725791",
        "name": "Fast Online Store PH",
        "category": "Footwear store",
        "category_list": [
          {
            "id": "109512302457693",
            "name": "Footwear store"
          }
        ],
        "about": "Your one-stop shop for premium footwear in the Philippines!",
        "website": "https://www.faststoreph.com",
        "link": "https://www.facebook.com/FastOnlineStorePH",
        "picture": {
          "data": {
            "url": "https://scontent.xx.fbcdn.net/v/.../profile.jpg"
          }
        },
        "fan_count": 1500,
        "verification_status": "verified",
        "location": {
          "city": "Manila",
          "country": "Philippines"
        },
        "phone": "+63 2 1234 5678",
        "email": "contact@faststoreph.com",
        "created_time": "2020-05-15T10:00:00+0000"
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
```

**Screenshot Reference**: Browser showing the JSON response with `pages` containing non-sensitive fields.
**Why?**
- Authorizing the app grants the requested scopes (`pages_messaging`, `pages_show_list`, `pages_manage_metadata`), allowing access to Pages and Messenger APIs.
- Facebook redirects to the callback URL with a `code` and `state` parameter, which the FastAPI app (Subchapter 1.1) validates and exchanges for a user access token (stored server-side).
- The response contains non-sensitive page data (`id`, `name`, `category`, `about`, `website`, `link`, `picture`, `fan_count`, `verification_status`, `location`, `phone`, `email`, `created_time`), excluding user and page access tokens for security.
- The `category_list` field provides additional category details, and `paging` supports pagination if the user manages multiple pages.

### Step 5: Verify the Integration
**Action**: Review the JSON response to ensure:
- `pages.data` includes at least one page with non-sensitive fields (e.g., `id`, `name`, `category`, `about`, etc.).
- No sensitive tokens (user or page access tokens) are present in the response.
- No errors (e.g., HTTP 400 for invalid state or code) appear in the browser or server logs.

**Expected Outcome**:
- The response matches the example above, confirming successful authentication and data retrieval.
- Server logs show successful HTTP 200 responses for `/facebook/callback`, e.g.:
```
INFO:     127.0.0.1:12345 - "GET /facebook/callback?code=...&state=... HTTP/1.1" 200 OK
```

**Screenshot Reference**: Terminal logs showing successful request handling.
**Why?**
- The absence of tokens ensures a secure response, while comprehensive page data supports the sales bot’s functionality (e.g., displaying page info or linking to the website).
- Non-sensitive fields like `fan_count` and `verification_status` provide context for marketing, and `location`, `phone`, and `email` enable customer contact integration.
- Verifying `pages_messaging` scope (implied by successful data retrieval) ensures the bot can send Messenger messages.

### Step 6: Troubleshooting Common Issues
If issues arise, check the following:
- **“Missing code parameter”**: Ensure `FACEBOOK_REDIRECT_URI` in `.env` matches the “Valid OAuth Redirect URIs” in the Facebook app settings (Subchapter 1.2).
- **“Invalid state token”**: Verify `STATE_TOKEN_SECRET` is set in `.env` and consistent across requests (Subchapter 1.1).
- **No pages in response**: Confirm the Facebook user has admin access to a business page and the app is in Development Mode (Subchapter 1.2). If in Live Mode, ensure `pages_messaging` and `pages_manage_metadata` permissions are approved by Meta.
- **404 or 500 errors**: Check that the server is running (`http://0.0.0.0:5000`) and the Codespaces public URL is accessible.
- **“Invalid App ID”**: Verify `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` in `.env` match the values from Subchapter 1.2’s app settings.
- **Missing fields (e.g., `email`, `phone`)**: Some fields may be null if not set for the page. Check the page’s settings in the Facebook interface.

**Why?**
- These checks ensure a secure and functional OAuth flow, addressing common setup errors.
- Proper configuration prevents issues during testing and prepares the app for production.

### Step 7: Example Sales Bot Context
With the OAuth flow working, the sales bot can use the page data to personalize interactions. For example:
```
Customer: I’m looking for snowboards.
Bot: Welcome to Fast Online Store PH, your verified footwear store in Manila! Check out our premium snowboards at https://www.faststoreph.com. Contact us at contact@faststoreph.com or +63 2 1234 5678 for more details!
```
This functionality integrates with Shopify data in Chapter 2.

### Summary: Why This Subchapter Matters
- **Server Verification**: Launching the app and checking the root endpoint confirms the FastAPI setup from Subchapter 1.1 is operational.
- **OAuth Flow**: Initiating and completing the OAuth process tests the integration with Facebook’s API, using credentials from Subchapter 1.2.
- **Callback Success**: The `/facebook/callback` response verifies that the OAuth logic and credentials are correctly implemented, providing comprehensive non-sensitive page data.
- **Security**: Excluding user and page access tokens from the response enhances security.
- **Bot Readiness**: The retrieved page data (e.g., `name`, `website`, `fan_count`) prepares the app for Messenger interactions, enabling the sales bot to engage customers.

### Next Steps:
- Review the Facebook OAuth implementation (Subchapter 1.1) and app setup (Subchapter 1.2) if issues arise.
- Proceed to Chapter 2 for Shopify integration, starting with creating a Shopify development store and app (Subchapter 2.1).