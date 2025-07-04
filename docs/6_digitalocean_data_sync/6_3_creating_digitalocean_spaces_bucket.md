# Chapter 6: DigitalOcean Integration
## Subchapter 6.3: Creating a DigitalOcean Spaces Bucket

### Introduction
This subchapter guides you through creating a DigitalOcean Spaces bucket to store Facebook and Shopify data for the GPT Messenger sales bot. The bucket provides S3-compatible storage for persistent, scalable data management, replacing temporary file storage from Chapters 4–5. We configure the bucket and generate API credentials (`SPACES_API_KEY`, `SPACES_API_SECRET`) for use in Subchapters 6.1–6.2, organizing data by UUID (`users/<uuid>/...`) from `TokenStorage` (Chapter 3). The process is performed in the DigitalOcean control panel, ensuring compatibility with the FastAPI application running on a Droplet.

### Prerequisites
- Completed Chapters 1–5 and Subchapters 6.1–6.2.
- DigitalOcean account with access to the control panel.
- FastAPI application running on a DigitalOcean Droplet or locally.
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).

---

### Step 1: Access the DigitalOcean Control Panel
**Action**: Log into the DigitalOcean control panel at [cloud.digitalocean.com](https://cloud.digitalocean.com).

**Screenshot Reference**: Shows the DigitalOcean dashboard.

**Why?**
- The control panel manages Spaces, Droplets, and API credentials.
- Ensures you have access to create a bucket for the sales bot.

### Step 2: Navigate to Spaces
**Action**: In the left sidebar, click “Spaces” under “Manage”. If no Spaces exist, you’ll see a prompt to create one.

**Screenshot Reference**: Shows the “Spaces” section with a “Create Spaces” button.

**Why?**
- The “Spaces” section manages S3-compatible storage buckets.
- Creating a bucket enables persistent storage for Facebook and Shopify data.

### Step 3: Create a New Space
**Action**: Click the “Create Spaces” button. Configure the following:
- **Datacenter region**: Select `NYC3` (New York) or a region close to your Droplet for low latency.
- **Enable CDN**: Disable for simplicity (enable in production for performance).
- **Unique name**: Enter a unique name, e.g., `gpt-messenger-data`.
- **Project**: Select your Droplet’s project or “Default Project”.

Click “Create a Space”.

**Screenshot Reference**: Shows the Spaces creation form with region, name, and project fields.

**Why?**
- **Region**: Minimizes latency for Droplet access.
- **CDN**: Disabled for testing; enable in production for faster access.
- **Unique name**: Identifies the bucket (e.g., `gpt-messenger-data`).
- **Project**: Organizes resources within your DigitalOcean account.

### Step 4: Configure Bucket Settings
**Action**: After creation, navigate to the bucket’s “Settings” tab:
- **File listing**: Disable to prevent public directory browsing.
- **CORS Configurations**: Add a configuration to allow your app’s origin, e.g.:
  - **Origin**: `http://localhost:5000` (or your Droplet’s domain, e.g., `https://your-app.com`).
  - **Allowed Methods**: `GET`, `POST`, `PUT`.
  - **Allowed Headers**: `*`.

Click “Save”.

**Screenshot Reference**: Shows the bucket settings with file listing disabled and CORS configured.

**Why?**
- **File listing**: Disabling enhances security by preventing public access.
- **CORS**: Allows the FastAPI app to interact with Spaces, matching the CORS settings in `app.py` (Chapter 1).
- **Production Note**: Use HTTPS origins in production.

### Step 5: Generate API Credentials
**Action**: In the DigitalOcean control panel, navigate to “API” in the left sidebar. Under “Spaces keys”, click “Generate New Key”. Configure:
- **Name**: Enter `gpt-messenger-key`.
- **Expiration**: Select “No expiry” for simplicity (set an expiration in production).

Click “Generate Key”. Copy the `Key` and `Secret` displayed.

**Screenshot Reference**: Shows the API section with the generated Spaces key.

**Why?**
- Provides `SPACES_API_KEY` and `SPACES_API_SECRET` for `boto3` authentication in Subchapters 6.1–6.2.
- **Production Note**: Rotate keys regularly and set expirations.

### Step 6: Update Environment Variables
Add Spaces credentials to your `.env` file.

```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
FACEBOOK_WEBHOOK_ADDRESS=https://your-app.com/facebook/webhook
FACEBOOK_VERIFY_TOKEN=your_verify_token
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
SHOPIFY_WEBHOOK_ADDRESS=https://your-app.com/shopify/webhook
# DigitalOcean Spaces credentials
SPACES_API_KEY=your_spaces_key
SPACES_API_SECRET=your_spaces_secret
SPACES_REGION=nyc3
SPACES_BUCKET=gpt-messenger-data
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
```

**Why?**
- Enables `boto3` to authenticate with Spaces.
- Matches bucket settings from Step 3.

### Step 7: Update `.gitignore`
Ensure SQLite databases are excluded.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
```

**Why?**
- Excludes `tokens.db` and `sessions.db` to prevent committing sensitive data.

### Step 8: Update `requirements.txt`
Ensure `boto3` is included.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
cryptography
apscheduler
boto3
```

**Why?**
- `boto3` enables Spaces integration.
- Other dependencies support OAuth, webhooks, and polling.

### Step 9: Testing Preparation
To verify bucket setup:
1. Update `.env` with Spaces credentials.
2. Install dependencies: `pip install -r requirements.txt`.
3. Verify bucket access in the DigitalOcean control panel.
4. Testing details are in Subchapter 6.4.

### Summary: Why This Subchapter Matters
- **Persistent Storage**: Creates a Spaces bucket for scalable data storage.
- **Security**: Configures private access and CORS for the FastAPI app.
- **Bot Readiness**: Prepares for storing Facebook and Shopify data (Subchapters 6.1–6.2).

### Next Steps:
- Complete Facebook data sync (Subchapter 6.1, already done).
- Complete Shopify data sync (Subchapter 6.2, already done).
- Test Spaces integration (Subchapter 6.4).