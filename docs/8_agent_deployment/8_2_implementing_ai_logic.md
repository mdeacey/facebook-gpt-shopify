## 8.2 Implementing the AI Agent Logic

This subchapter covers the implementation of `digitalocean_integration/agent.py`, which handles data retrieval from DigitalOcean Spaces, formats the AI prompt, calls the DigitalOcean GenAI API, and sends responses via the Facebook Messenger API. This module is the core of the AI response generation process.

### Overview
The agent fetches Shopify store metadata, Shopify product data, Facebook page metadata, and conversation history from Spaces, formats the prompt with this data, generates a response using the GenAI API, and sends it to the user. The implementation includes three key functions: `get_data_from_spaces`, `generate_agent_response`, and `send_facebook_message`.

### Implementation Details
Create `digitalocean_integration/agent.py` with the following content:

**File: `digitalocean_integration/agent.py`**
```python
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
            return []  # Return empty list for conversations to simplify appending
        raise HTTPException(status_code=500, detail=f"Failed to fetch data from Spaces: {str(e)}")

async def generate_agent_response(page_id: str, sender_id: str, message_text: str, user_uuid: str) -> dict:
    s3_client = boto3.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
        aws_access_key_id=os.getenv("SPACES_API_KEY"),
        aws_secret_access_key=os.getenv("SPACES_API_SECRET")
    )

    # Fetch relevant data
    shopify_metadata_key = f"users/{user_uuid}/shopify/shop_metadata.json"
    shopify_products_key = f"users/{user_uuid}/shopify/shop_products.json"
    facebook_metadata_key = f"users/{user_uuid}/facebook/{page_id}/page_metadata.json"
    conversation_key = f"users/{user_uuid}/facebook/{page_id}/conversations/{sender_id}.json"

    shopify_metadata = await get_data_from_spaces(shopify_metadata_key, s3_client)
    shopify_products = await get_data_from_spaces(shopify_products_key, s3_client)
    facebook_metadata = await get_data_from_spaces(facebook_metadata_key, s3_client)
    conversation_history = await get_data_from_spaces(conversation_key, s3_client)

    # Load prompt from file
    try:
        with open("digitalocean_integration/prompt.txt", "r") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Prompt file not found")

    # Format prompt with data
    prompt = prompt_template.format(
        message_text=message_text,
        shopify_metadata=json.dumps(shopify_metadata, indent=2),
        shopify_products=json.dumps(shopify_products, indent=2),
        facebook_metadata=json.dumps(facebook_metadata, indent=2),
        conversation_history=json.dumps(conversation_history, indent=2)
    )

    # Call GenAI agent
    headers = {
        "Authorization": f"Bearer {os.getenv('GENAI_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3.3-70b-instruct",
        "prompt": prompt,
        "max_tokens": 200
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            os.getenv("GENAI_ENDPOINT", "https://api.genai.digitalocean.com/v1/llama3.3-70b-instruct"),
            headers=headers,
            json=payload
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"GenAI API error: {response.text}")
        return {
            "text": response.json().get("choices", [{}])[0].get("text", "").strip(),
            "message_id": f"agent_mid_{int(time.time())}"
        }

async def send_facebook_message(page_id: str, recipient_id: str, message_text: str, access_token: str) -> str:
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
        return response.json().get("message_id", f"sent_mid_{int(time.time())}")
```

### Testing
1. **Test Data Retrieval**: Use mock data to call `get_data_from_spaces` and verify it retrieves data or returns an empty list for non-existent files.
2. **Test Prompt Formatting**: Pass a sample `message_text` and mock data to `generate_agent_response` to ensure the prompt is correctly formatted.
3. **Test GenAI API Call**: Simulate a GenAI API call with a test prompt to verify response generation.
4. **Test Message Sending**: Use a mock access token to test `send_facebook_message` and confirm it sends messages correctly.
5. **Expected Outcome**: The functions should retrieve data, format the prompt, generate a response, and send it without errors.

### Notes
- **Prerequisite**: Complete Subchapter 8.1 to ensure `prompt.txt` exists.
- **Error Handling**: The module handles missing files and API failures with appropriate HTTP 500 errors.
- This subchapter prepares the agent logic for integration with the webhook in Subchapter 8.3.