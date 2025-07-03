# Chapter 6: DigitalOcean Integration
## Subchapter 6.3: Creating DigitalOcean Spaces Bucket

### Introduction
DigitalOcean Spaces provides a scalable, S3-compatible object storage service to store data for the GPT Messenger sales bot. This subchapter guides you through creating a Spaces bucket and generating API keys to enable secure data storage for the application’s integrations. The bucket will store data in a structured format, ensuring accessibility and scalability for the bot’s operations.

### Prerequisites
- A DigitalOcean account.
- Completed Chapters 1–5 (Facebook OAuth, Shopify OAuth, UUID/session management, Facebook data sync, Shopify data sync).
- FastAPI application running locally or in a production-like environment.

---

### Step 1: Create a DigitalOcean Spaces Bucket
**Action**: Set up a Spaces bucket in the DigitalOcean Control Panel.
1. Log into your DigitalOcean account at `cloud.digitalocean.com`.
2. Navigate to **Create > Spaces**.
3. Choose a datacenter region (e.g., `nyc3` for New York).
4. Enable or disable CDN based on your needs (disable for simplicity during testing).
5. Set a unique bucket name (e.g., `gpt-messenger-bot-data`).
6. Select **File access: Restricted** to ensure secure access via API keys.
7. Click **Create a Space**.

**Expected Output**: The bucket appears in the DigitalOcean Control Panel under **Spaces**.

**Screenshot Reference**: DigitalOcean Control Panel showing the created bucket.
**Why?**
- The bucket provides a storage location for bot data.
- Restricted access ensures security through API key authentication.

### Step 2: Generate API Keys
**Action**: Create API keys for programmatic access to the bucket.
1. In the DigitalOcean Control Panel, navigate to **API > Spaces Keys**.
2. Click **Generate New Key**.
3. Enter a name for the key (e.g., `gpt-messenger-bot-key`).
4. Click **Generate Key**.
5. Copy the **Access Key** and **Secret Key** displayed.

**Expected Output**: You receive an Access Key (e.g., `DO00...`) and a Secret Key (e.g., `abc123...`).

**Screenshot Reference**: API section showing the generated keys.
**Why?**
- API keys enable secure interactions with Spaces via `boto3`.
- The keys will be used in `.env` for Subchapters 6.1, 6.2, and 6.4.

### Step 3: Configure Environment Variables
Add Spaces credentials to the `.env` file.

**Updated `.env.example`**:
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
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# DigitalOcean Spaces credentials
SPACES_ACCESS_KEY=your_access_key
SPACES_SECRET_KEY=your_secret_key
SPACES_BUCKET=your_bucket_name
SPACES_REGION=nyc3
```

**Notes**:
- Replace `SPACES_ACCESS_KEY`, `SPACES_SECRET_KEY`, and `SPACES_BUCKET` with values from Steps 1 and 2.
- `SPACES_REGION` matches the bucket’s region (e.g., `nyc3`).
- **Production Note**: Store keys securely and restrict permissions to read/write operations.

**Why?**
- Configures the application to access the Spaces bucket securely.

### Step 4: Project Structure
The project structure includes `digitalocean_integration/` from Subchapter 6.1:
```
.
├── app.py
├── facebook_integration/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shopify_integration/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── digitalocean_integration/
│   ├── __init__.py
│   └── utils.py
├── shared/
│   ├── __init__.py
│   ├── session.py
│   └── utils.py
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `digitalocean_integration/utils.py` supports Spaces operations.
- Consistent with previous chapters.

### Step 5: Update `requirements.txt`
Ensure `boto3` is included.

```plaintext
fastapi
uvicorn
httpx
python-dotenv
apscheduler
boto3
```

**Why?**
- `boto3` enables Spaces API interactions.

### Step 6: Testing Preparation
To verify bucket setup:
1. Update `.env` with `SPACES_*` variables.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run the app: `python app.py`.
4. Testing is covered in Subchapter 6.4.

### Summary: Why This Subchapter Matters
- **Scalable Storage**: Sets up a Spaces bucket for bot data.
- **Security**: Uses restricted access and API keys.
- **Integration Readiness**: Prepares for data sync in Subchapters 6.1 and 6.2.
- **Scalability**: Supports production environments.

### Next Steps:
- Test Spaces integration (Subchapter 6.4).