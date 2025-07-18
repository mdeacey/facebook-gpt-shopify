import sqlite3
import os
import time
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from typing import Optional, Tuple
import uuid
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

class SessionStorage:
    def __init__(self, db_path: str = os.getenv("SESSION_DB_PATH", "./data/sessions.db")):
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
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        uuid TEXT NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                """)
                conn.commit()
        except sqlite3.OperationalError as e:
            raise Exception(f"Session database initialization failed: {str(e)}")

    def generate_session_id(self) -> str:
        return secrets.token_urlsafe(32)

    def store_uuid(self, session_id: str, uuid: str) -> None:
        encrypted_uuid = self.fernet.encrypt(uuid.encode()).decode()
        created_at = int(time.time())
        for _ in range(3):
            try:
                with sqlite3.connect(self.db_path, timeout=10) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO sessions (session_id, uuid, created_at) VALUES (?, ?, ?)",
                        (session_id, encrypted_uuid, created_at)
                    )
                    conn.commit()
                    return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(0.1)
                else:
                    raise
        raise Exception("Session database write failed after retries")

    def get_uuid(self, session_id: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT uuid FROM sessions WHERE session_id = ?", (session_id,))
                result = cursor.fetchone()
                if result:
                    return self.fernet.decrypt(result[0].encode()).decode()
                return None
        except sqlite3.OperationalError as e:
            raise Exception(f"Session database read failed: {str(e)}")

    def clear_session(self, session_id: str) -> None:
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
        except sqlite3.OperationalError as e:
            raise Exception(f"Session database delete failed: {str(e)}")

    def get_or_create_session(self, session_id: Optional[str]) -> Tuple[str, str]:
        user_uuid = None
        if session_id:
            user_uuid = self.get_uuid(session_id)

        if user_uuid:
            self.clear_session(session_id)
            new_session_id = self.generate_session_id()
            self.store_uuid(new_session_id, user_uuid)
        else:
            new_session_id = self.generate_session_id()
            user_uuid = str(uuid.uuid4())
            self.store_uuid(new_session_id, user_uuid)

        return new_session_id, user_uuid

    def verify_session(self, session_id: Optional[str], expected_uuid: Optional[str] = None) -> str:
        if not session_id:
            raise HTTPException(status_code=400, detail="Missing session_id cookie")

        user_uuid = self.get_uuid(session_id)
        if not user_uuid:
            raise HTTPException(status_code=400, detail="Invalid or expired session")

        if expected_uuid and user_uuid != expected_uuid:
            raise HTTPException(status_code=400, detail="Mismatched session UUID")

        return user_uuid