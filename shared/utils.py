# shared/utils.py

import os
import time
import hmac
import hashlib
import base64
import secrets
from fastapi import HTTPException

STATE_TOKEN_SECRET = os.getenv("STATE_TOKEN_SECRET", "changeme-in-prod")

def generate_state_token(expiry_seconds: int = 300) -> str:
    timestamp = int(time.time())
    nonce = secrets.token_urlsafe(8)
    payload = f"{timestamp}:{nonce}"
    signature = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode()
    return f"{timestamp}:{nonce}:{encoded_sig}"

def validate_state_token(state_token: str, max_age: int = 300):
    try:
        timestamp_str, nonce, provided_sig = state_token.split(":")
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed state token")

    if abs(time.time() - timestamp) > max_age:
        raise HTTPException(status_code=400, detail="Expired state token")

    expected_sig = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        f"{timestamp}:{nonce}".encode(),
        hashlib.sha256
    ).digest()
    expected_sig_encoded = base64.urlsafe_b64encode(expected_sig).decode()

    if not hmac.compare_digest(provided_sig, expected_sig_encoded):
        raise HTTPException(status_code=400, detail="Invalid state token")
