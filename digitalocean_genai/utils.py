import os
import boto3
import json
from fastapi import HTTPException

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