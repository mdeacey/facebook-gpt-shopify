# Chapter 7: Data Backup and Recovery
## Subchapter 7.2: Testing Persistent Storage and Backups

### Introduction
This subchapter verifies the SQLite-based persistent storage (`tokens.db`, `sessions.db`) from Chapter 3 and the daily backup system to DigitalOcean Spaces from Subchapter 7.1. We test the storage by ensuring tokens, UUIDs, and session data are correctly saved and retrieved during OAuth flows (Chapters 1–2), and we validate the backup and restore process for `tokens.db` and `sessions.db` using the `aws` CLI. This ensures the GPT Messenger sales bot’s critical data is reliably stored and recoverable, maintaining data integrity in a production environment on a DigitalOcean Droplet.

### Prerequisites
- Completed Chapters 1–6 and Subchapter 7.1.
- FastAPI application running on a DigitalOcean Droplet or locally.
- SQLite databases (`tokens.db`, `sessions.db`) in a configurable path (`TOKEN_DB_PATH`, `SESSION_DB_PATH`, or `./data/`) (Chapter 3).
- Backup scripts (`backup_tokens_db.sh`, `backup_sessions_db.sh`) set up in `/app/scripts/` (Subchapter 7.1).
- DigitalOcean Spaces bucket and credentials configured (Subchapter 6.3).
- `aws` CLI installed on the Droplet (`sudo apt-get install awscli`).
- Cron jobs scheduled for backups (Subchapter 7.1).

---

### Step 1: Why Test Persistent Storage and Backups?
Testing ensures:
- `tokens.db` stores encrypted tokens and UUIDs for OAuth, webhooks, and polling (Chapters 1–5).
- `sessions.db` stores encrypted session IDs for multi-platform linking (Chapter 3).
- Backup scripts create date-stamped copies and upload to Spaces (`backups/tokens_YYYY-MM-DD.db`, `backups/sessions_YYYY-MM-DD.db`).
- Restore processes recover databases without data loss.

### Step 2: Test Persistent Storage
**Action**: Verify `tokens.db` and `sessions.db` functionality via OAuth flows.

**Instructions**:
1. Run the app:
   ```bash
   python app.py
   ```
2. Complete Shopify OAuth:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
3. Check the `/shopify/callback` response:
   ```json
   {
     "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
     "token_data": {
       "access_token": "shpua_9a72896d590dbff5d3cf818f49710f67",
       ...
     },
     ...
     "webhook_test": {"status": "success"},
     "polling_test": {"status": "success"}
   }
   ```
4. Verify `tokens.db` contains the token and UUID:
   ```bash
   sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"
   ```
   **Expected Output**:
   ```
   SHOPIFY_ACCESS_TOKEN_acme-7cu19ngr_myshopify_com
   USER_UUID_acme-7cu19ngr_myshopify_com
   ```
5. Verify `sessions.db` contains the session:
   ```bash
   sqlite3 "${SESSION_DB_PATH:-./data/sessions.db}" "SELECT session_id, created_at FROM sessions;"
   ```
   **Expected Output**:
   ```
   <session_id>|1698765432
   ```
6. Complete Facebook OAuth:
   ```
   http://localhost:5000/facebook/login
   ```
7. Check the `/facebook/callback` response:
   ```json
   {
     "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
     "pages": {...},
     "webhook_test": {"status": "success"},
     "polling_test": [{"page_id": "101368371725791", "result": {"status": "success"}}]
   }
   ```
8. Verify `tokens.db` contains additional tokens and UUIDs:
   ```bash
   sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"
   ```
   **Expected Output**:
   ```
   SHOPIFY_ACCESS_TOKEN_acme-7cu19ngr_myshopify_com
   USER_UUID_acme-7cu19ngr_myshopify_com
   FACEBOOK_USER_ACCESS_TOKEN
   FACEBOOK_ACCESS_TOKEN_101368371725791
   PAGE_UUID_101368371725791
   ```

**Why?**
- Confirms `TokenStorage` and `SessionStorage` (Chapter 3) store encrypted data.
- Ensures OAuth flows (Chapters 1–2) save tokens/UUIDs and sessions correctly.
- Verifies multi-platform UUID linking.
- **Note**: The database paths are configurable via `TOKEN_DB_PATH` and `SESSION_DB_PATH` environment variables, with fallbacks to `./data/tokens.db` and `./data/sessions.db`. Set these in `.env` for custom paths (e.g., `/var/app/data/` in production).

### Step 3: Test Backup Scripts
**Action**: Manually run backup scripts to verify database copying and Spaces uploads.

**Instructions**:
1. Run the backup scripts:
   ```bash
   /app/scripts/backup_tokens_db.sh
   /app/scripts/backup_sessions_db.sh
   ```
2. Check logs in `/app/backups/backup_tokens.log` and `/app/backups/backup_sessions.log`:
   **Expected Output**:
   ```
   Successfully uploaded tokens_2025-07-04.db to Spaces
   Successfully uploaded sessions_2025-07-04.db to Spaces
   ```
3. Verify backup files in `/app/backups/`:
   ```bash
   ls /app/backups/
   ```
   **Expected Output**:
   ```
   sessions_2025-07-04.db  tokens_2025-07-04.db
   ```
4. Check the Spaces bucket (`gpt-messenger-data`) via the DigitalOcean control panel for:
   - `backups/tokens_2025-07-04.db`
   - `backups/sessions_2025-07-04.db`

**Why?**
- Confirms scripts copy databases and upload to Spaces.
- Ensures date-stamped versioning (`YYYY-MM-DD`).
- **Note**: Ensure the backup scripts reference the correct database paths (`$TOKEN_DB_PATH` or `./data/tokens.db`, `$SESSION_DB_PATH` or `./data/sessions.db`).

### Step 4: Test Restore Process
**Action**: Simulate database loss and restore from Spaces.

**Instructions**:
1. Stop the FastAPI app (`Ctrl+C`).
2. Simulate loss by moving databases:
   ```bash
   mv "${TOKEN_DB_PATH:-./data/tokens.db}" "${TOKEN_DB_PATH:-./data/tokens.db}.bak"
   mv "${SESSION_DB_PATH:-./data/sessions.db}" "${SESSION_DB_PATH:-./data/sessions.db}.bak"
   ```
3. Download backups from Spaces:
   ```bash
   aws --endpoint-url https://nyc3.digitaloceanspaces.com s3 cp s3://gpt-messenger-data/backups/tokens_2025-07-04.db "${TOKEN_DB_PATH:-./data/tokens.db}"
   aws --endpoint-url https://nyc3.digitaloceanspaces.com s3 cp s3://gpt-messenger-data/backups/sessions_2025-07-04.db "${SESSION_DB_PATH:-./data/sessions.db}"
   ```
4. Set permissions:
   ```bash
   chmod 600 "${TOKEN_DB_PATH:-./data/tokens.db}" "${SESSION_DB_PATH:-./data/sessions.db}"
   chown app_user:app_user "${TOKEN_DB_PATH:-./data/tokens.db}" "${SESSION_DB_PATH:-./data/sessions.db}"
   ```
5. Restart the app: `python app.py`.
6. Re-run Shopify and Facebook OAuth flows (Steps 2–3 in Step 2).
7. Verify the same `user_uuid` and tokens are retrieved, and webhook/polling tests succeed.

**Why?**
- Ensures backups are recoverable and functional.
- Confirms data integrity after restoration.
- **Note**: Use `TOKEN_DB_PATH` and `SESSION_DB_PATH` environment variables to specify database paths, with fallbacks to `./data/tokens.db` and `./data/sessions.db`. Adjust paths in backup scripts if customized.

### Step 5: Verify Cron Scheduling
**Action**: Check that cron jobs execute backups daily.

**Instructions**:
1. Verify crontab:
   ```bash
   crontab -l
   ```
   **Expected Output**:
   ```
   0 1 * * * /app/scripts/backup_tokens_db.sh >> /app/backups/backup_tokens.log 2>&1
   0 1 * * * /app/scripts/backup_sessions_db.sh >> /app/backups/backup_sessions.log 2>&1
   ```
2. Wait until 1 AM UTC or simulate by running:
   ```bash
   run-parts /etc/cron.daily
   ```
3. Check `/app/backups/backup_tokens.log` and `/app/backups/backup_sessions.log` for new entries.
4. Verify new backup files in the Spaces bucket.

**Why?**
- Confirms automated daily backups to Spaces.

### Step 6: Troubleshoot Issues
**Action**: Diagnose and fix issues if tests fail.

**Common Issues and Fixes**:
1. **Storage Failure**:
   - **Cause**: Tokens or sessions not saved.
   - **Fix**: Verify `tokens.db` and `sessions.db` with `sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"` and `sqlite3 "${SESSION_DB_PATH:-./data/sessions.db}" "SELECT session_id, created_at FROM sessions;"`, check OAuth logs for errors (Chapters 1–2).
2. **Backup Script Failure**:
   - **Cause**: Missing environment variables or permissions.
   - **Fix**: Ensure `/app/.env` includes Spaces credentials and `TOKEN_DB_PATH`, `SESSION_DB_PATH`, check permissions (`ls -l "${TOKEN_DB_PATH:-./data/tokens.db}" "${SESSION_DB_PATH:-./data/sessions.db}"`), and review logs in `/app/backups/`.
3. **Spaces Upload Failure**:
   - **Cause**: Invalid credentials or bucket settings.
   - **Fix**: Verify `SPACES_KEY`, `SPACES_SECRET`, `SPACES_REGION`, `SPACES_BUCKET`, `SPACES_ENDPOINT` in `.env`.
4. **Restore Failure**:
   - **Cause**: Corrupted backup or incorrect permissions.
   - **Fix**: Download and inspect backups, ensure `chmod 600` and `chown app_user:app_user` for restored files.
5. **Cron Failure**:
   - **Cause**: Cron not running or script errors.
   - **Fix**: Check `crontab -l`, verify script permissions (`chmod +x`), and review cron logs (`/var/log/syslog`).

**Why?**
- Uses logs and database queries to debug storage and backup issues.

### Summary: Why This Subchapter Matters
- **Data Integrity**: Verifies `tokens.db` and `sessions.db` store critical data.
- **Backup Reliability**: Confirms daily backups to Spaces.
- **Recovery**: Ensures data can be restored without loss.
- **Production Readiness**: Supports scalable, secure operation.

### Next Steps:
- Monitor backup logs and Spaces for ongoing reliability.
- Implement additional bot features as needed.