import os
import json
import boto3
import httpx
import time
from botocore.exceptions import ClientError
from fastapi import HTTPException
from shared.tokens import TokenStorage

token_storage = TokenStorage()

async def get_data_from_spaces(key: str, s3_client: boto3.client) -> dict:
    try:
        response = s3_client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=key)
        return json.loads(response["Body"].read().decode())
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return {}
        raise HTTPException(status_code=500, detail=f"Failed to fetch data from Spaces: {str(e)}")

async def generate_agent_response(page_id: str, sender_id: str, message_text: str, user_uuid: str) -> dict:
    print(f"Generating AI response for page {page_id}, sender {sender_id}, message: {message_text}")
    s3_client = boto3.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
        aws_access_key_id=os.getenv("SPACES_API_KEY"),
        aws_secret_access_key=os.getenv("SPACES_API_SECRET")
    )

    shopify_data_key = f"users/{user_uuid}/shopify/data.json"
    facebook_data_key = f"users/{user_uuid}/facebook/data.json"

    shopify_data = await get_data_from_spaces(shopify_data_key, s3_client)
    facebook_data = await get_data_from_spaces(facebook_data_key, s3_client)

    shopify_metadata = shopify_data.get("metadata", {})
    shopify_products = shopify_data.get("products", {})
    facebook_page_data = next((page for page in facebook_data.get("data", []) if page["id"] == page_id), {})
    conversation_history = [
        msg for msg in facebook_data.get("conversations", {}).get(sender_id, [])
        if msg.get("recipient", {}).get("id") == page_id
    ]

    if not facebook_page_data:
        print(f"No page data found for page_id {page_id} in user {user_uuid}")
    if not conversation_history:
        print(f"No conversation history found for sender {sender_id} on page {page_id}")

    try:
        with open("digitalocean_integration/prompt.txt", "r") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        print("Prompt file not found at digitalocean_integration/prompt.txt")
        raise HTTPException(status_code=500, detail="Prompt file not found")

    prompt = prompt_template.format(
        message_text=message_text,
        shopify_metadata=json.dumps(shopify_metadata, indent=2),
        shopify_products=json.dumps(shopify_products, indent=2),
        facebook_metadata=json.dumps(facebook_page_data, indent=2),
        conversation_history=json.dumps(conversation_history, indent=2)
    )

    headers = {
        "Authorization": f"Bearer {os.getenv('AGENT_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3.3-70b-instruct",
        "prompt": prompt,
        "max_tokens": 200
    }
    endpoint = os.getenv("AGENT_ENDPOINT", "https://et7wtbptiokv4v3rs2ucud4m.agents.do-ai.run")
    print(f"Sending request to GenAI API: {endpoint}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload
            )
            print(f"GenAI API response: {response.status_code}, {response.text}")
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"GenAI API error: {response.text}")
            return {
                "text": response.json().get("choices", [{}])[0].get("text", "").strip(),
                "message_id": f"agent_mid_{int(time.time())}"
            }
        except Exception as e:
            print(f"GenAI API request failed: {str(e)}")
            raise

async def send_facebook_message(page_id: str, recipient_id: str, message_text: str, access_token: str) -> str:
    print(f"Sending Facebook message to recipient {recipient_id} on page {page_id}")
    url = f"https://graph.facebook.com/v19.0/{page_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"Failed to send message to {recipient_id} on page {page_id}: {response.text}")
            raise HTTPException(status_code=500, detail=f"Message send failed: {response.text}")
        print(f"Message sent successfully: {response.json()}")
        return response.json().get("message_id", f"sent_mid_{int(time.time())}")