import os
import boto3
import json
from fastapi import HTTPException
from botocore.exceptions import ClientError
from shared.utils import compute_data_hash

def has_data_changed(data: dict, key: str, s3_client: boto3.client) -> bool:
    new_hash = compute_data_hash(data)
    try:
        response = s3_client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=key)
        existing_data = response["Body"].read().decode()
        existing_hash = compute_data_hash(json.loads(existing_data))
        return existing_hash != new_hash
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return True
        raise HTTPException(status_code=500, detail=f"Failed to fetch existing data: {str(e)}")

def upload_to_spaces(data: dict, key: str, s3_client: boto3.client):
    try:
        s3_client.put_object(
            Bucket=os.getenv("SPACES_BUCKET"),
            Key=key,
            Body=json.dumps(data, ensure_ascii=False),
            ContentType="application/json",
            ACL="private"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")