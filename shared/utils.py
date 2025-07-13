import logging
import os
import time
import hmac
import hashlib
import base64
import secrets
import json
import boto3
import httpx
import uuid
from fastapi import HTTPException, Request
from typing import Optional, Literal, Callable
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

STATE_TOKEN_SECRET = os.getenv("STATE_TOKEN_SECRET", "changeme-in-prod")

def retry_async(func: Callable) -> Callable:
    return retry(
        stop=stop_after_attempt(1),  # Reduced to 1 attempt for webhook tests to avoid duplicates
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, boto3.exceptions.Boto3Error)),
        before_sleep=lambda retry_state: logger.info(
            f"{func.__name__} failed (attempt {retry_state.attempt_number}/1): {str(retry_state.outcome.exception())}. "
            f"Retrying in {retry_state.next_action.sleep}s..."
        )
    )(func)

async def check_endpoint_accessibility(
    endpoint: str,
    auth_key: Optional[str] = None,
    endpoint_type: Literal["api", "webhook"] = "api",
    method: Literal["GET", "HEAD", "POST"] = "GET",
    expected_status: Optional[int] = None
) -> tuple[bool, str]:
    request_id = str(uuid.uuid4())
    headers = {"Content-Type": "application/json"}
    if auth_key:
        headers["Authorization"] = f"Bearer {auth_key}"

    @retry_async
    async def make_request(client, endpoint, headers, method):
        request_method = {
            "GET": client.get,
            "HEAD": client.head,
            "POST": client.post
        }[method]
        kwargs = {"headers": headers, "timeout": 10}
        if method == "POST":
            kwargs["json"] = {}
        logger.info(f"[{request_id}] Sending {method} request to {endpoint} with headers {headers}")
        return await request_method(endpoint, **kwargs)

    async with httpx.AsyncClient() as client:
        try:
            response = await make_request(client, endpoint, headers, method)
            logger.info(f"[{request_id}] Received response from {endpoint}: status {response.status_code}")
            if expected_status and response.status_code == expected_status:
                return True, f"{endpoint_type.capitalize()} endpoint is accessible as expected (status {response.status_code})"
            if response.status_code == 200:
                return True, f"{endpoint_type.capitalize()} endpoint is accessible"
            elif response.status_code == 401:
                return False, f"{endpoint_type.capitalize()} endpoint returned 401 - authentication may be required or endpoint is restricted"
            elif response.status_code == 403:
                return False, f"{endpoint_type.capitalize()} endpoint access forbidden or restricted"
            elif response.status_code == 404:
                return False, f"{endpoint_type.capitalize()} endpoint returned 404 - endpoint may be private or misconfigured"
            else:
                return False, f"{endpoint_type.capitalize()} endpoint check failed with status {response.status_code}: {response.text}"
        except Exception as e:
            logger.error(f"[{request_id}] Failed to access {endpoint}: {str(e)}")
            return False, f"{endpoint_type.capitalize()} endpoint inaccessible - may be private, restricted, or network issue: {str(e)}"

@retry_async
async def exchange_code_for_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    token_url: str,
    method: Literal["GET", "POST"] = "GET"
):
    request_id = str(uuid.uuid4())
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code
    }
    async with httpx.AsyncClient() as client:
        try:
            if method == "POST":
                logger.info(f"[{request_id}] Sending POST request to {token_url} with body {json.dumps(params)}")
                response = await client.post(token_url, json=params)
            else:
                logger.info(f"[{request_id}] Sending GET request to {token_url} with params {params}")
                response = await client.get(token_url, params=params)
            logger.info(f"[{request_id}] Token exchange response: {response.status_code}, {response.text}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Token exchange failed: Invalid client_id or client_secret")
            elif response.status_code == 403:
                raise HTTPException(status_code=403, detail="Token exchange failed: Redirect URI not authorized")
            elif response.status_code == 400:
                raise HTTPException(status_code=400, detail=f"Token exchange failed: Invalid or expired code - {response.text}")
            raise

async def verify_hmac(
    request: Request,
    secret: str,
    signature_header: str,
    hash_algorithm: Callable = hashlib.sha256
) -> bool:
    request_id = str(uuid.uuid4())
    signature = request.headers.get(signature_header)
    if not signature:
        logger.error(f"[{request_id}] No signature provided in {signature_header}")
        return False
    body = await request.body()
    if signature.startswith("sha1="):
        signature = signature[5:]
        expected_hmac = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    else:
        expected_hmac = base64.b64encode(
            hmac.new(secret.encode(), body, hash_algorithm).digest()
        ).decode()
    result = hmac.compare_digest(signature, expected_hmac)
    logger.info(f"[{request_id}] HMAC verification: {'success' if result else 'failed'}")
    return result

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
    request_id = str(uuid.uuid4())
    try:
        parts = state_token.split(":")
        if len(parts) == 4:
            timestamp_str, expires_at_str, nonce, provided_sig = parts
            extra_data = None
        elif len(parts) == 5:
            timestamp_str, expires_at_str, nonce, extra_data, provided_sig = parts
        else:
            logger.error(f"[{request_id}] Malformed state token: {state_token}")
            raise HTTPException(status_code=400, detail="Malformed state token")
        timestamp = int(timestamp_str)
        expires_at = int(expires_at_str)
    except ValueError:
        logger.error(f"[{request_id}] Malformed state token: {state_token}")
        raise HTTPException(status_code=400, detail="Malformed state token")

    current_time = int(time.time())
    if current_time > expires_at:
        logger.error(f"[{request_id}] Expired state token: {state_token}")
        raise HTTPException(status_code=400, detail="Expired state token")
    if abs(current_time - timestamp) > max_age:
        logger.error(f"[{request_id}] Token age exceeds maximum allowed: {state_token}")
        raise HTTPException(status_code=400, detail="Token age exceeds maximum allowed")

    payload = f"{timestamp}:{expires_at}:{nonce}" if not extra_data else f"{timestamp}:{expires_at}:{nonce}:{extra_data}"
    expected_sig = hmac.new(
        STATE_TOKEN_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).digest()
    expected_sig_encoded = base64.urlsafe_b64encode(expected_sig).decode()

    if not hmac.compare_digest(provided_sig, expected_sig_encoded):
        logger.error(f"[{request_id}] Invalid state token: {state_token}")
        raise HTTPException(status_code=400, detail="Invalid state token")

    logger.info(f"[{request_id}] State token validated successfully")
    return extra_data

def get_previous_hash(s3_client: boto3.client, bucket: str, key: str) -> str | None:
    request_id = str(uuid.uuid4())
    @retry_async
    def head_object():
        return s3_client.head_object(Bucket=bucket, Key=key)

    try:
        head_response = head_object()
        logger.info(f"[{request_id}] Retrieved previous hash for {bucket}/{key}: {head_response['ETag'].strip('"')}")
        return head_response["ETag"].strip('"')
    except Exception as e:
        logger.info(f"[{request_id}] No previous hash found for {bucket}/{key}: {str(e)}")
        return None