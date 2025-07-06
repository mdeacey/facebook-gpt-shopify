### Subchapter 3.2: SQLite-Based Token Management

This subchapter introduces SQLite-based token management to store access tokens and UUIDs for the GPT Messenger sales bot, replacing the temporary use of environment variables from Chapters 1–2. The `TokenStorage` class in `shared/tokens.py` uses a SQLite database (`tokens.db`) with encryption (`cryptography`) and Write-Ahead Logging (WAL) for secure, concurrent access. This supports flexible OAuth flows (Shopify or Facebook first) by storing tokens and UUIDs persistently, ensuring compatibility with Subchapter 3.1’s session management.

#### Step 1: Why SQLite-Based Token Management?
Tokens and UUIDs (e.g., `FACEBOOK_ACCESS_TOKEN_{page_id}`, `SHOPIFY_ACCESS_TOKEN_{shop_key}`, `PAGE_UUID_{page_id}`, `USER_UUID_{shop_key}`) are critical for accessing platform APIs and linking user data. Using `os.environ` is not persistent and unsuitable for production. The SQLite-based approach:
- Stores tokens in `tokens.db`, persisting across restarts.
- Encrypts sensitive data using `cryptography` with `STATE_TOKEN_SECRET`.
- Uses WAL for concurrent access.
- Supports multiple users with secure, isolated storage.

#### Step 2: Update `shared/tokens.py`
This module implements a SQLite-based token store with encryption and WAL.

```python
import sqlite3
import os
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from typing import Optional, Dict
from fastapi import HTTPException

def get_fernet_key() -> Fernet:
    secret = os.getenv("STATE_TOKEN_SECRET").encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'salt_',
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key)

class TokenStorage:
    def __init__(self, db_path: str = os.getenv("TOKEN_DB_PATH", "./data/tokens.db")):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.fernet = get_fernet_key()
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tokens (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        type TEXT NOT NULL
                    )
                """)
                conn.commit()
        except sqlite3.OperationalError as e:
            raise HTTPException(status_code=500, detail=f"Database initialization failed: {str(e)}")

    def store_token(self, key: str, value: str, type: str = "token") -> None:
        encrypted_value = self.fernet.encrypt(value.encode()).decode()
        for _ in range(3):
            try:
                with sqlite3.connect(self.db_path, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO tokens (key, value, type) VALUES (?, ?, ?)",
                        (key, encrypted_value, type)
                    )
                    conn.commit()
                    return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(0.1)
                else:
                    raise
        raise HTTPException(status_code=500, detail="Database write failed after retries")

    def get_token(self, key: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM tokens WHERE key = ?", (key,))
                result = cursor.fetchone()
                if result:
                    return self.fernet.decrypt(result[0].encode()).decode()
                return None
        except sqlite3.OperationalError as e:
            raise HTTPException(status_code=500, detail=f"Database read failed: {str(e)}")

    def get_all_tokens_by_type(self, type: str) -> Dict[str, str]:
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM tokens WHERE type = ?", (type,))
                results = cursor.fetchall()
                return {
                    key: self.fernet.decrypt(value.encode()).decode()
                    for key, value in results
                }
        except sqlite3.OperationalError as e:
            raise HTTPException(status_code=500, detail=f"Database read failed: {str(e)}")

    def delete_token(self, key: str) -> None:
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM tokens WHERE key = ?", (key,))
                conn.commit()
        except sqlite3.OperationalError as e:
            raise HTTPException(status_code=500, detail=f"Database delete failed: {str(e)}")
```

**Why?**
- **SQLite Storage**: Stores tokens in `tokens.db`, persisting across restarts.
- **Encryption**: Uses `cryptography` with `STATE_TOKEN_SECRET` to secure tokens and UUIDs.
- **WAL**: Enables concurrent access for production.
- **Type Field**: Distinguishes tokens (`token`) from UUIDs (`uuid`) for future use (Chapter 4).
- **Production Note**: Set `TOKEN_DB_PATH` to a secure, writable directory (e.g., `/var/app/data/tokens.db`) with secure permissions (`chmod 600`, `chown app_user:app_user`).

#### Step 3: Update `facebook_integration/routes.py`
Already updated in Subchapter 3.1 (Step 5), using `TokenStorage` for tokens and UUIDs.

#### Step 4: Update `shopify_integration/routes.py`
Already updated in Subchapter 3.1 (Step 4), using `TokenStorage` for tokens and UUIDs.

#### Step 5: Update `.env.example`
Already includes `TOKEN_DB_PATH` and `SESSION_DB_PATH` from Subchapter 3.1.

```plaintext
# Facebook OAuth credentials
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
# For GitHub Codespaces
# FACEBOOK_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/facebook/callback
# Shopify OAuth credentials
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
# For GitHub Codespaces
# SHOPIFY_REDIRECT_URI=https://your-codespace-id-5000.app.github.dev/shopify/callback
# Shared secret for state token CSRF protection
STATE_TOKEN_SECRET=replace_with_secure_token
# Database paths for SQLite storage
SESSION_DB_PATH=./data/sessions.db
TOKEN_DB_PATH=./data/tokens.db
```

**Why?**
- Supports session and token storage for both OAuth flows.
- Excludes future variables (e.g., webhook or Spaces settings).

#### Step 6: Testing Preparation
Verify token and session management:
- Run: `python app.py`.
- Test Shopify OAuth first:
  - Navigate to `/shopify/acme-7cu19ngr/login`, complete OAuth, and check `tokens.db` for `SHOPIFY_ACCESS_TOKEN_{shop_key}` and `USER_UUID_{shop_key}`.
  - Navigate to `/facebook/login`, verify it uses the same UUID and stores tokens in `tokens.db`.
- Test Facebook OAuth first:
  - Navigate to `/facebook/login`, complete OAuth, and check `tokens.db` for `FACEBOOK_USER_ACCESS_TOKEN` and `PAGE_UUID_{page_id}`.
  - Navigate to `/shopify/acme-7cu19ngr/login`, verify it uses the same UUID.
- Check `tokens.db` using `sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"`.

**Why?**
- Ensures token storage and UUID consistency across both OAuth flows.

#### Summary: Why This Subchapter Matters
- **Persistent Tokens**: SQLite-based `TokenStorage` ensures tokens persist across restarts.
- **Multi-Platform Linking**: UUIDs in `tokens.db` link Shopify and Facebook data.
- **Security**: Encrypts tokens and uses WAL for concurrency.
- **Compatibility**: Works with flexible OAuth flows from Subchapter 3.1.

#### Next Steps:
- Proceed to Chapter 4 for Facebook data synchronization.