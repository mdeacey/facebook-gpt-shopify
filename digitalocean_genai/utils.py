# digitalocean_genai/utils.py

import os
import boto3
import json
import httpx
import hmac
import hashlib
import base64
from fastapi import HTTPException, Request, Depends

async def verify_shopify_webhook(request: Request) -> bool:
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if not hmac_header:
        return False

    raw_body = await request.body()
    shopify_api_secret = os.getenv("SHOPIFY_API_SECRET")
    if not shopify_api_secret:
        raise HTTPException(status_code=500, detail="Shopify API secret missing")

    expected_hmac = hmac.new(
        shopify_api_secret.encode(),
        raw_body,
        hashlib.sha256
    ).digest()
    expected_hmac_b64 = base64.b64encode(expected_hmac).decode()

    return hmac.compare_digest(hmac_header, expected_hmac_b64)

def upload_to_spaces(data: dict, key: str):
    spaces_access_key = os.getenv("SPACES_ACCESS_KEY")
    spaces_secret_key = os.getenv("SPACES_SECRET_KEY")
    spaces_bucket = os.getenv("SPACES_BUCKET")
    spaces_region = os.getenv("SPACES_REGION", "nyc3")

    if not all([spaces_access_key, spaces_secret_key, spaces_bucket]):
        raise HTTPException(status_code=500, detail="Spaces configuration missing")

    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=spaces_region,
        endpoint_url=f"https://{spaces_region}.digitaloceanspaces.com",
        aws_access_key_id=spaces_access_key,
        aws_secret_access_key=spaces_secret_key
    )

    try:
        s3_client.put_object(
            Bucket=spaces_bucket,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
            ACL="private"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")

async def reindex_knowledge_base(knowledge_base_id: str, spaces_key: str):
    access_token = os.getenv("DIGITALOCEAN_ACCESS_TOKEN")
    if not access_token:
        raise HTTPException(status_code=500, detail="DigitalOcean access token missing")

    url = f"https://api.digitalocean.com/v2/genai/knowledge_bases/{knowledge_base_id}/reindex"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "source": {
            "type": "spaces",
            "bucket": os.getenv("SPACES_BUCKET"),
            "key": spaces_key,
            "region": os.getenv("SPACES_REGION", "nyc3")
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=500, detail=f"Knowledge base reindex failed: {str(e)}")