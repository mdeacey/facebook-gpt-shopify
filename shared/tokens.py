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