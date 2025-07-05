# Chapter 7: Data Backup and Recovery
## Subchapter 7.2: Testing Persistent Storage and Backups

### Introduction
This subchapter verifies the persistent storage and backup mechanisms for the GPT Messenger sales bot, focusing on the SQLite databases (`tokens.db` and `sessions.db` from Chapter 3) and their backups, which store OAuth tokens and session data. While the subchapter does not directly test DigitalOcean Spaces data, it relies on the data sync functionality from Chapter 6 to ensure the bot’s data (stored in `users/<uuid>/facebook/<page_id>/page_metadata.json`, `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`, `users/<uuid>/shopify/<shop_name>/shop_metadata.json`, and `users/<uuid>/shopify/<shop_name>/shop_products.json`) is accessible after database restoration. Tests simulate database loss and recovery, confirming that webhook and polling mechanisms can still access and sync data using restored tokens and UUIDs.

### Prerequisites
- Completed Chapters 1–6.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- DigitalOcean Spaces credentials (`SPACES_KEY`, `SPACES_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`) set in `.env` (Subchapter 6.1).
- Facebook and Shopify API credentials set in `.env` (Chapters 1–2, Subchapters 4.1, 5.1).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Backup system for SQLite databases configured (Subchapter 7.1).

---

### Step 1: Understand the Testing Scope
**Purpose**:
- Verify that `tokens.db` and `sessions.db` can be restored from backups.
- Ensure restored databases allow access to Spaces data (`users/<uuid>/facebook/...` and `users/<uuid>/shopify/...`).
- Confirm webhook and polling mechanisms (Chapters 4–6) function post-recovery using restored tokens and UUIDs.

**Note**: This subchapter focuses on database backups, but the data sync tests rely on the Spaces paths established in Chapter 6:
- Facebook: `users/<uuid>/facebook/<page_id>/page_metadata.json`, `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`
- Shopify: `users/<uuid>/shopify/<shop_name>/shop_metadata.json`, `users/<uuid>/shopify/<shop_name>/shop_products.json`

**Why?**
- Ensures the bot can recover from database loss without losing access to cloud-stored data.
- Validates UUID-based organization in Spaces for multi-user support.
- Confirms the renamed `facebook` directory and split Shopify files are accessible post-recovery.

### Step 2: Testing Preparation
**Action**: Simulate database loss and restore from backups, then test OAuth flows and data access.

**Instructions**:
1. **Backup Databases** (from Subchapter 7.1):
   - Ensure `tokens.db` and `sessions.db` are backed up (e.g., to `backups/tokens.db.bak` and `backups/sessions.db.bak`).
2. **Simulate Database Loss**:
   - Delete or rename `tokens.db` and `sessions.db`:
     ```bash
     mv data/tokens.db data/tokens.db.test
     mv data/sessions.db data/sessions.db.test
     ```
3. **Restore Databases**:
   - Copy backups to restore the databases:
     ```bash
     cp backups/tokens.db.bak data/tokens.db
     cp backups/sessions.db.bak data/sessions.db
     ```
4. Run the app:
   ```bash
   python app.py
   ```
5. **Run OAuth Flows**:
   - Shopify OAuth:
     ```
     http://localhost:5000/shopify/acme-7cu19ngr/login
     ```
   - Facebook OAuth:
     ```
     http://localhost:5000/facebook/login
     ```
6. **Trigger Webhooks**:
   - For Facebook: Update a page’s `name` or send a test message via Messenger.
   - For Shopify: Update a product in Shopify Admin (e.g., change “Premium Snowboard” to “Premium Snowboard Pro”).
7. **Trigger Polling**:
   - Temporarily modify `app.py` to run `facebook_daily_poll` and `shopify_daily_poll`:
     ```python
     from facebook_integration.utils import daily_poll as facebook_daily_poll
     from shopify_integration.utils import daily_poll as shopify_daily_poll
     facebook_daily_poll()
     shopify_daily_poll()
     ```
   - Run: `python app.py`.

**Why?**
- Simulates a recovery scenario to verify database restoration.
- Tests data sync using restored tokens and UUIDs, ensuring access to Spaces data.

### Step 3: Verify OAuth Flow Outputs
**Action**: Check JSON responses and logs from OAuth flows to confirm token and UUID restoration.

**Expected Output**:
- Shopify OAuth response (same as Subchapter 5.3, with `user_uuid` matching pre-loss value).
- Facebook OAuth response (same as Subchapter 4.4, with `user_uuid` matching pre-loss value).
- Server logs:
  ```
  Webhook registered for acme-7cu19ngr.myshopify.com: products/update
  Uploaded data to users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json and users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  Webhook subscription for 'name,category,messages' already exists for page 101368371725791
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json to Spaces
  ```

**Why?**
- Confirms restored `tokens.db` and `sessions.db` provide correct tokens and UUIDs.
- Verifies Spaces uploads use the correct paths (`users/<uuid>/facebook/...` and `users/<uuid>/shopify/...`).

### Step 4: Verify Webhook Functionality
**Action**: Check webhook processing post-recovery.

**Expected Output**:
- Facebook metadata webhook:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'changes': [{'field': 'name', 'value': 'New Store Name'}]}
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json to Spaces
  ```
- Facebook message webhook:
  ```
  Received webhook event for page 101368371725791: {'id': '101368371725791', 'messaging': [...]}
  New conversation started for sender 123456789 on page 101368371725791
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json to Spaces
  ```
- Shopify webhook:
  ```
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Premium Snowboard Pro'}}
  Uploaded data to users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json and users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Confirms webhooks use restored tokens to upload data to Spaces.
- Verifies the renamed `facebook` directory and split Shopify files.

### Step 5: Verify Polling Functionality
**Action**: Check polling post-recovery.

**Expected Output**:
- Facebook polling:
  ```
  Polled metadata for page 101368371725791: Success
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json to Spaces
  Polled conversations for page 101368371725791: Success
  Uploaded users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json to Spaces
  ```
- Shopify polling:
  ```
  Uploaded data to users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json and users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Confirms polling uses restored tokens to upload data to Spaces.
- Ensures correct path structure and data formats.

### Step 6: Verify Spaces Storage
**Action**: Check Spaces for uploaded files post-recovery.

**Instructions**:
1. Log into DigitalOcean and navigate to the bucket specified in `SPACES_BUCKET`.
2. Verify the presence and contents of:
   - `users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/page_metadata.json`
   - `users/550e8400-e29b-41d4-a716-446655440000/facebook/101368371725791/conversations/123456789.json`
   - `users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_metadata.json`
   - `users/550e8400-e29b-41d4-a716-446655440000/shopify/acme-7cu19ngr.myshopify.com/shop_products.json`

**Expected Content**:
- Same as Subchapter 6.4, with metadata, conversations, and split Shopify data.

**Why?**
- Confirms data is accessible in Spaces after database restoration.
- Verifies the updated path structure and file naming.

### Step 7: Troubleshoot Issues
**Action**: If tests fail, diagnose and fix issues.

**Common Issues and Fixes**:
1. **OAuth Failure**:
   - **Cause**: Restored database missing tokens or UUIDs.
   - **Fix**: Verify backup integrity using `sqlite3 backups/tokens.db.bak "SELECT key FROM tokens;"`. Re-run OAuth flows if necessary.
2. **Webhook or Polling Failure**:
   - **Cause**: Invalid tokens or Spaces misconfiguration.
   - **Fix**: Check logs for API or `boto3` errors. Verify `SPACES_KEY`, `SPACES_SECRET`, and `SPACES_BUCKET`.
3. **Missing Spaces Files**:
   - **Cause**: Uploads failed.
   - **Fix**: Check logs for `boto3` errors. Ensure bucket permissions allow write access.

**Why?**
- Ensures robust recovery and data access.
- Validates Spaces paths and data integrity.

### Summary: Why This Subchapter Matters
- **Recovery Verification**: Confirms database restoration allows continued data sync to Spaces.
- **Path Consistency**: Ensures `users/<uuid>/facebook/...` and `users/<uuid>/shopify/...` paths work post-recovery, with renamed `facebook` directory and split Shopify files.
- **Bot Reliability**: Guarantees the bot can access cloud data after a failure.
- **Security**: Maintains secure token storage and private ACL.

### Next Steps:
- Deploy the bot for advanced functionality (Chapter 8).
- Monitor logs for ongoing backup and sync success.