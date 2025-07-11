import os
import time
import hmac
import hashlib
import base64
import secrets
import json
import boto3
from fastapi import HTTPException

STATE_TOKEN_SECRET = os.getenv("STATE_TOKEN_SECRET", "changeme-in-prod")

def compute_data_hash(data: dict) -> str:
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()

def generate_state_token(expiry_seconds: int = 300, extra_data: str = None) -> str:
    timestamp = int(time.time())
    expires_at = timestamp + expiry_seconds
    nonce = secrets.token_urlsafe(8)
    payload = f"{timestamp}:{expires_at}:{nonce}"
    if extra_data:
        payload += f":{extra_data}"
    signature = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode()
    return f"{timestamp}:{expires_at}:{nonce}:{encoded_sig}" if not extra_data else f"{timestamp}:{expires_at}:{nonce}:{extra_data}:{encoded_sig}"

def validate_state_token(state_token: str, max_age: int = 300):
    try:
        parts = state_token.split(":")
        if len(parts) == 4:
            timestamp_str, expires_at_str, nonce, provided_sig = parts
            extra_data = None
        elif len(parts) == 5:
            timestamp_str, expires_at_str, nonce, extra_data, provided_sig = parts
        else:
            raise HTTPException(status_code=400, detail="Malformed state token")
        timestamp = int(timestamp_str)
        expires_at = int(expires_at_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed state token")

    current_time = int(time.time())
    if current_time > expires_at:
        raise HTTPException(status_code=400, detail="Expired state token")
    if abs(current_time - timestamp) > max_age:
        raise HTTPException(status_code=400, detail="Token age exceeds maximum allowed")

    payload = f"{timestamp}:{expires_at}:{nonce}" if not extra_data else f"{timestamp}:{expires_at}:{nonce}:{extra_data}"
    expected_sig = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    expected_sig_encoded = base64.urlsafe_b64encode(expected_sig).decode()

    if not hmac.compare_digest(provided_sig, expected_sig_encoded):
        raise HTTPException(status_code=400, detail="Invalid state token")

    return extra_data

def get_previous_hash(s3_client: boto3.client, bucket: str, key: str) -> str | None:
    try:
        head_response = s3_client.head_object(Bucket=bucket, Key=key)
        return head_response["ETag"].strip('"')
    except Exception:
        return None