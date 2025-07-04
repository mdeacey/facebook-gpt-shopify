# Chapter 7: Data Backup and Recovery
## Subchapter 7.1: Daily Backups to DigitalOcean Spaces

### Introduction
To ensure data reliability for the GPT Messenger sales bot, this subchapter implements daily backups of the SQLite databases (`tokens.db` and `sessions.db`) introduced in Chapter 3. These databases store access tokens and session data critical for OAuth, webhooks, and polling (Chapters 1–5). We create shell scripts (`backup_tokens_db.sh` and `backup_sessions_db.sh`) to copy the databases and upload them to DigitalOcean Spaces (`backups/tokens_YYYY-MM-DD.db`, `backups/sessions_YYYY-MM-DD.db`) using the `aws` CLI for S3-compatible storage. The scripts are scheduled with cron jobs on the DigitalOcean Droplet, ensuring automated, secure backups that leverage the Spaces bucket from Chapter 6.

### Prerequisites
- Completed Chapters 1–6 (OAuth, Persistent Storage, Data Sync, Spaces Integration).
- FastAPI application running on a DigitalOcean Droplet.
- SQLite databases (`tokens.db`, `sessions.db`) set up in a configurable path (`TOKEN_DB_PATH`, `SESSION_DB_PATH`, or `./data/`) (Chapter 3).
- DigitalOcean Spaces bucket and credentials configured (`SPACES_API_KEY`, `SPACES_API_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`, `SPACES_ENDPOINT`) from Subchapter 6.3.
- `aws` CLI installed on the Droplet (`sudo apt-get install awscli`).

---

### Step 1: Why Daily Backups?
Backups protect against data loss due to:
- Hardware failures or Droplet issues.
- Database corruption or accidental deletion.
- Application errors affecting `tokens.db` (tokens, UUIDs) or `sessions.db` (session IDs).
Daily uploads to Spaces ensure offsite storage, leveraging the bucket from Chapter 6, with date-stamped files for versioning.

### Step 2: Update Project Structure
Add backup scripts to the project:
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
├── shared/
│   ├── __init__.py
│   ├── sessions.py
│   ├── tokens.py
│   └── utils.py
├── scripts/
│   ├── backup_tokens_db.sh
│   └── backup_sessions_db.sh
├── .env
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

**Why?**
- `scripts/backup_tokens_db.sh` and `scripts/backup_sessions_db.sh` handle database backups.
- Builds on Spaces integration from Chapter 6.
- Maintains modularity for production deployment.

### Step 3: Create Backup Script for `tokens.db`
Create `scripts/backup_tokens_db.sh` to copy and upload `tokens.db`.

```bash
#!/bin/bash

# Load environment variables
source /app/.env

# Exit if required variables are not set
if [ -z "$SPACES_API_KEY" ] || [ -z "$SPACES_API_SECRET" ] || [ -z "$SPACES_REGION" ] || [ -z "$SPACES_BUCKET" ] || [ -z "$SPACES_ENDPOINT" ]; then
    echo "Error: Missing required environment variables for Spaces"
    exit 1
fi

# Set variables
DATE=$(date +%Y-%m-%d)
DB_PATH="${TOKEN_DB_PATH:-./data/tokens.db}"
BACKUP_DIR="/app/backups"
BACKUP_FILE="$BACKUP_DIR/tokens_$DATE.db"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Copy the database to backup directory
if ! cp "$DB_PATH" "$BACKUP_FILE"; then
    echo "Error: Failed to copy tokens.db to backup directory"
    exit 1
fi

# Configure AWS CLI for Spaces
export AWS_ACCESS_KEY_ID="$SPACES_API_KEY"
export AWS_SECRET_ACCESS_KEY="$SPACES_API_SECRET"
export AWS_DEFAULT_REGION="$SPACES_REGION"

# Upload to Spaces
aws --endpoint-url "$SPACES_ENDPOINT" s3 cp "$BACKUP_FILE" "s3://$SPACES_BUCKET/backups/tokens_$DATE.db"
if [ $? -eq 0 ]; then
    echo "Successfully uploaded tokens_$DATE.db to Spaces"
else
    echo "Error: Failed to upload tokens_$DATE.db to Spaces"
    exit 1
fi
```

**Why?**
- **Environment Variables**: Sources `.env` for Spaces credentials and `TOKEN_DB_PATH`.
- **Date-Stamped Backup**: Copies `tokens.db` to `/app/backups/tokens_YYYY-MM-DD.db`.
- **Spaces Upload**: Uses `aws` CLI to upload to `backups/tokens_YYYY-MM-DD.db`.
- **Error Handling**: Exits on failure for debugging.
- **Configurable Path**: Uses `TOKEN_DB_PATH` with a fallback to `./data/tokens.db` for compatibility with `TokenStorage` (Chapter 3).
- **Production Note**: Ensure `TOKEN_DB_PATH` matches `TokenStorage` configuration, and set secure permissions (`chmod 600`, `chown app_user:app_user`) for `/app/.env` and `DB_PATH`.

### Step 4: Create Backup Script for `sessions.db`
Create `scripts/backup_sessions_db.sh` to copy and upload `sessions.db`.

```bash
#!/bin/bash

# Load environment variables
source /app/.env

# Exit if required variables are not set
if [ -z "$SPACES_API_KEY" ] || [ -z "$SPACES_API_SECRET" ] || [ -z "$SPACES_REGION" ] || [ -z "$SPACES_BUCKET" ] || [ -z "$SPACES_ENDPOINT" ]; then
    echo "Error: Missing required environment variables for Spaces"
    exit 1
fi

# Set variables
DATE=$(date +%Y-%m-%d)
DB_PATH="${SESSION_DB_PATH:-./data/sessions.db}"
BACKUP_DIR="/app/backups"
BACKUP_FILE="$BACKUP_DIR/sessions_$DATE.db"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Copy the database to backup directory
if ! cp "$DB_PATH" "$BACKUP_FILE"; then
    echo "Error: Failed to copy sessions.db to backup directory"
    exit 1
fi

# Configure AWS CLI for Spaces
export AWS_ACCESS_KEY_ID="$SPACES_API_KEY"
export AWS_SECRET_ACCESS_KEY="$SPACES_API_SECRET"
export AWS_DEFAULT_REGION="$SPACES_REGION"

# Upload to Spaces
aws --endpoint-url "$SPACES_ENDPOINT" s3 cp "$BACKUP_FILE" "s3://$SPACES_BUCKET/backups/sessions_$DATE.db"
if [ $? -eq 0 ]; then
    echo "Successfully uploaded sessions_$DATE.db to Spaces"
else
    echo "Error: Failed to upload sessions_$DATE.db to Spaces"
    exit 1
fi
```

**Why?**
- **Similar Structure**: Mirrors `backup_tokens_db.sh` for consistency.
- **Date-Stamped Backup**: Copies `sessions.db` to `/app/backups/sessions_YYYY-MM-DD.db`.
- **Spaces Upload**: Uploads to `backups/sessions_YYYY-MM-DD.db`.
- **Configurable Path**: Uses `SESSION_DB_PATH` with a fallback to `./data/sessions.db` for compatibility with `SessionStorage` (Chapter 3).
- **Error Handling**: Ensures reliable backup execution.

### Step 5: Make Scripts Executable
**Action**: Set executable permissions for the scripts.

```bash
chmod +x /app/scripts/backup_tokens_db.sh
chmod +x /app/scripts/backup_sessions_db.sh
```

**Why?**
- Ensures scripts can be run by cron.
- **Production Note**: Run as a non-root user (e.g., `app_user`) with access to `/app/.env` and `DB_PATH`.

### Step 6: Schedule Backups with Cron
**Action**: Schedule daily backups at 1 AM UTC.

```bash
crontab -e
```

Add to crontab:
```plaintext
0 1 * * * /app/scripts/backup_tokens_db.sh >> /app/backups/backup_tokens.log 2>&1
0 1 * * * /app/scripts/backup_sessions_db.sh >> /app/backups/backup_sessions.log 2>&1
```

**Why?**
- Runs backups daily at 1 AM UTC, logging output for debugging.
- Separates logs (`backup_tokens.log`, `backup_sessions.log`) for monitoring.
- **Production Note**: Ensure cron runs as `app_user` with access to `/app/.env` and `DB_PATH`.

### Step 7: Update `.gitignore`
Add backup directory and scripts to prevent committing sensitive data.

```plaintext
__pycache__/
*.pyc
.env
.DS_Store
*.db
/app/backups/
/app/scripts/backup_tokens_db.sh
/app/scripts/backup_sessions_db.sh
```

**Why?**
- Excludes `tokens.db`, `sessions.db`, backup files, and scripts.
- Builds on Chapters 3–6 `.gitignore`.

### Step 8: Update Environment Variables
Update `.env.example` to include database paths.

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
# Database paths for SQLite storage
TOKEN_DB_PATH=./data/tokens.db
SESSION_DB_PATH=./data/sessions.db
```

**Why?**
- Provides Spaces credentials and database paths for backup scripts.
- Matches `TokenStorage` and `SessionStorage` configurations (Chapter 3).

### Step 9: Install AWS CLI on the Droplet
**Action**: Install the `aws` CLI for Spaces uploads.

```bash
sudo apt-get update
sudo apt-get install awscli
aws configure
```

Enter:
- **AWS Access Key ID**: `SPACES_API_KEY`
- **AWS Secret Access Key**: `SPACES_API_SECRET`
- **Default region name**: `SPACES_REGION` (e.g., `nyc3`)
- **Default output format**: `json`

**Why?**
- Configures `aws` CLI for S3-compatible Spaces uploads.
- **Production Note**: Store credentials securely in `.env`, not `~/.aws/`.

### Step 10: Testing Preparation
To verify backup setup:
1. Ensure `/app/.env` includes Spaces credentials and `TOKEN_DB_PATH`, `SESSION_DB_PATH`.
2. Run scripts manually:
   ```bash
   /app/scripts/backup_tokens_db.sh
   /app/scripts/backup_sessions_db.sh
   ```
3. Check `/app/backups/` for `tokens_YYYY-MM-DD.db` and `sessions_YYYY-MM-DD.db`.
4. Verify uploads in the Spaces bucket (`backups/`) via the DigitalOcean control panel.
5. Testing details are in Subchapter 7.2.

### Summary: Why This Subchapter Matters
- **Data Protection**: Ensures `tokens.db` and `sessions.db` are backed up daily.
- **Scalability**: Uses Spaces for offsite storage.
- **Automation**: Cron jobs streamline backup processes.
- **Security**: Leverages encrypted databases and secure credentials.
- **Configurability**: Uses `TOKEN_DB_PATH` and `SESSION_DB_PATH` for flexible database paths.

### Next Steps:
- Test persistent storage and backups (Subchapter 7.2).