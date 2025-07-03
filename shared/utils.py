# shared/utils.py

import os
import time
import hmac
import hashlib
import base64
import secrets
from fastapi import HTTPException

STATE_TOKEN_SECRET = os.getenv("STATE_TOKEN_SECRET", "changeme-in-prod")

def generate_state_token(expiry_seconds: int = 300, extra_data: str = None) -> str:
    timestamp = int(time.time())
    nonce = secrets.token_urlsafe(8)
    payload = f"{timestamp}:{nonce}"
    if extra_data:
        payload += f":{extra_data}"
    signature = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode()
    return f"{timestamp}:{nonce}:{encoded_sig}" if not extra_data else f"{timestamp}:{nonce}:{extra_data}:{encoded_sig}"

def validate_state_token(state_token: str, max_age: int = 300):
    try:
        parts = state_token.split(":")
        if len(parts) == 3:
            timestamp_str, nonce, provided_sig = parts
            extra_data = None
        elif len(parts) == 4:
            timestamp_str, nonce, extra_data, provided_sig = parts
        else:
            raise HTTPException(status_code=400, detail="Malformed state token")
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed state token")

    if abs(time.time() - timestamp) > max_age:
        raise HTTPException(status_code=400, detail="Expired state token")

    payload = f"{timestamp}:{nonce}" if not extra_data else f"{timestamp}:{nonce}:{extra_data}"
    expected_sig = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    expected_sig_encoded = base64.urlsafe_b64encode(expected_sig).decode()

    if not hmac.compare_digest(provided_sig, expected_sig_encoded):
        raise HTTPException(status_code=400, detail="Invalid state token")

    return extra_data