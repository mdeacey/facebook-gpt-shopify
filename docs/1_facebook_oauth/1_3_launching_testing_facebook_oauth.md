# Chapter 1: Facebook Integration
## Subchapter 1.3: Launching and Testing Facebook OAuth

This subchapter guides you through launching the FastAPI application built in Subchapter 1.1, using the Facebook app credentials from Subchapter 1.2, and testing the Facebook OAuth flow. We’ll start the server, verify the root endpoint, initiate the OAuth process via `/facebook/login`, and confirm the callback response at `/facebook/callback`. Each step includes expected outputs (e.g., server logs, JSON responses) and references to screenshots (not provided) to ensure the integration works correctly. This confirms that your app can authenticate with Facebook and retrieve comprehensive, non-sensitive page data for the GPT Messenger sales bot. Persistent storage for tokens is introduced in Chapter 3.

### Step 1: Launch the FastAPI Application
**Action**: Navigate to your project directory and run:
```bash
python app.py
```

**Expected Output**: Terminal displays Uvicorn server logs:
```
INFO:     Will watch for changes in these directories: ['/workspaces/facebook-gpt-shopify']
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
INFO:     Started reloader process [88929] using StatReload
INFO:     Started server process [88932]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Screenshot Reference**: Terminal showing Uvicorn logs.

**Why?**
- Runs the FastAPI server using Uvicorn (Subchapter 1.1’s `app.py`).
- Confirms the server is listening on `http://0.0.0.0:5000`.
- In GitHub Codespaces, accessible via a public URL (e.g., `https://your-codespace-id-5000.app.github.dev`).
- Validates environment variables (`FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI`, `STATE_TOKEN_SECRET`) to prevent runtime errors.

### Step 2: Test the Root Endpoint
**Action**: Open a browser and navigate to:
- **Local**: `http://localhost:5000`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev`

**Expected Output**: Browser displays:
```json
{
  "status": "ok",
  "message": "Use /facebook/login for OAuth"
}
```

**Screenshot Reference**: Browser showing JSON response.

**Why?**
- Confirms the FastAPI server is running (Subchapter 1.1).
- Guides users to the OAuth endpoint.
- Excludes references to future integrations (e.g., Shopify, introduced in Chapter 2).

### Step 3: Initiate Facebook OAuth
**Action**: Navigate to:
- **Local**: `http://localhost:5000/facebook/login`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev/facebook/login`

**Expected Output**: Browser redirects to a Facebook OAuth dialog URL, e.g.:
```
https://www.facebook.com/v19.0/dialog/oauth?client_id=your_app_id&redirect_uri=http://localhost:5000/facebook/callback&scope=pages_messaging,pages_show_list,pages_manage_metadata&response_type=code&state=1751277990:Mhg1D2nYmAE:xo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE=
```

The Facebook page displays:
```
Facebook
Reconnect to messenger-gpt-shopify?
This will re-establish your previous settings for this connection.
[Edit previous settings]
By continuing, messenger-gpt-shopify will receive ongoing access to the information you share and Meta will record when messenger-gpt-shopify accesses it. Learn more about this sharing and the settings you have.
[Cancel] [Continue]
```

**Screenshot Reference**: Facebook OAuth dialog with reconnect prompt.

**Why?**
- The `/facebook/login` endpoint (Subchapter 1.1) constructs the OAuth URL with `client_id`, `redirect_uri`, scopes (`pages_messaging`, `pages_show_list`, `pages_manage_metadata`), and a state token for CSRF protection.
- The redirect confirms authentication initiation.
- No session cookies are used yet, as session management is introduced in Chapter 3.

### Step 4: Authorize the App
**Action**: Click "Continue" (or “Reconnect”) on the Facebook OAuth dialog.

**Expected Output**: Browser redirects to:
- **Local**: `http://localhost:5000/facebook/callback?code=AQDqeAxEI53Puc9Sv31VbkK2JwbJRKDp9vDNG99cC9mSLVDot4ahBkGVMmRYwFhQ42VzO9kYlnrHbbOiz_o_odW6wOEY-rSoDObi0QJMu4NGJeBRDIIFdfvHEGXlbsRZ-eGWHu5hQt2h1xGpgMiwFNp4jCp7I_zsargoTNW3RBC2ueKPw694UOAUenRP7jszrjQgMID_2fhuZKi7uyh3M2pykWYS7i3K71nkAmU4kFawAOzvI3_jZtpoJA9DiaeXqtOQpzOIMG4w5-HNd-bMnvz_br10_Gon08Xh7vDiFr3Ug1owSiwphEZ-_wuEGZ2D694vvBBwWv2GzNa5IWl-79zzJME7slwQ0Hw9ob8dm1f33h-CsZnbUf4F3Kjma2qI8ZI&state=1751277990%3AMhg1D2nYmAE%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D#_=_`
- **GitHub Codespaces**: `https://your-codespace-id-5000.app.github.dev/facebook/callback?code=...&state=...`

Browser displays JSON response:
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

**Screenshot Reference**: Browser showing JSON response.

**Why?**
- Authorizing grants scopes, allowing access to Pages and Messenger APIs.
- The `/facebook/callback` endpoint (Subchapter 1.1) validates the state token, stores tokens in `os.environ`, and returns non-sensitive page data.
- No session management or UUIDs are included yet, as they are introduced in Chapter 3.

### Step 5: Verify the Integration
**Action**: Review the JSON response to ensure:
- `pages.data` includes non-sensitive fields (e.g., `id`, `name`, `category`).
- No sensitive tokens are present.
- No errors (e.g., HTTP 400 for invalid state or code) appear.

**Expected Outcome**:
- Response matches the example above.
- Server logs show HTTP 200 responses:
```
INFO:     127.0.0.1:12345 - "GET /facebook/login HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:12345 - "GET /facebook/callback?code=...&state=... HTTP/1.1" 200 OK
```

**Screenshot Reference**: Terminal logs showing successful request handling.

**Why?**
- Verifies secure authentication and data retrieval for the sales bot.
- Confirms tokens are stored in `os.environ` (persistent storage in Chapter 3).

### Step 6: Troubleshooting Common Issues
If issues arise, check:
- **“Missing code parameter”**: Ensure `FACEBOOK_REDIRECT_URI` in `.env` matches the app’s settings (Subchapter 1.2).
- **“Invalid state token”**: Verify `STATE_TOKEN_SECRET` in `.env` (Subchapter 1.1).
- **No pages in response**: Confirm user has admin access to a business page and app is in Development Mode (Subchapter 1.2).
- **404 or 500 errors**: Verify server is running and Codespaces URL is accessible.
- **“Invalid App ID”**: Check `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` in `.env` against portal values (Subchapter 1.2).
- **“Missing environment variables”**: Ensure all required variables are set in `.env` (Subchapter 1.1).

**Why?**
- Ensures a functional OAuth flow, addressing setup errors.

### Step 7: Example Sales Bot Context
The sales bot can use page data to personalize interactions, e.g.:
```
Customer: I’m looking for snowboards.
Bot: Welcome to Fast Online Store PH, your verified footwear store in Manila! Contact us at contact@faststoreph.com or +63 2 1234 5678!
```

**Why?**
- Demonstrates how page data supports bot functionality, with full integration in later chapters.

### Summary: Why This Subchapter Matters
- **Server Verification**: Confirms FastAPI setup and environment validation (Subchapter 1.1).
- **OAuth Flow**: Tests authentication with Facebook’s API using credentials from Subchapter 1.2.
- **Callback Success**: Verifies OAuth logic and non-sensitive page data retrieval.
- **Security**: Excludes tokens from responses, stores them in `os.environ` (persistent storage in Chapter 3).
- **Bot Readiness**: Prepares the bot for Messenger interactions, with further integrations in later chapters.

### Next Steps:
- Review Subchapter 1.1 or 1.2 if issues arise.
- Proceed to Chapter 2 for additional integrations.