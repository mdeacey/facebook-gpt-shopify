## 8.1 Handling Incoming Facebook Messages with GenAI Responses

This subchapter details the integration of the DigitalOcean GenAI agent into the GPT Messenger sales bot to process incoming Facebook messages and generate automated, context-aware responses. The agent leverages Shopify store metadata, Shopify product data, Facebook page metadata, and conversation history to craft replies that align with the business’s branding and product offerings. Responses are formatted to match the Facebook Messenger payload structure and appended to the conversation file in DigitalOcean Spaces. New conversations create a new JSON file, while existing conversations append messages to the existing file. To ensure maintainability, the AI prompt is stored in a separate text file, allowing updates without modifying the codebase.

### Overview

The system handles incoming Facebook messages through the following workflow:
1. **Receive Message**: The `/facebook/webhook` endpoint processes incoming messages from Facebook’s webhook.
2. **Fetch Data**: The system retrieves:
   - Shopify store metadata (`users/<uuid>/shopify/shop_metadata.json`).
   - Shopify product data (`users/<uuid>/shopify/shop_products.json`).
   - Facebook page metadata (`users/<uuid>/facebook/<page_id>/page_metadata.json`).
   - Conversation history (`users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`).
3. **Load Prompt**: The AI prompt is loaded from `digitalocean_integration/prompt.txt` and formatted with the fetched data.
4. **Generate Response**: The DigitalOcean GenAI API generates a response based on the prompt.
5. **Send Response**: The response is sent to the user via the Facebook Messenger API.
6. **Store Response**: The response is formatted as a Facebook Messenger payload and appended to the conversation file in Spaces.

This implementation ensures seamless integration with the existing Facebook and Shopify data pipelines, maintaining consistency with platform-specific naming conventions (`facebook/` and `shopify/` directories) for future extensibility.

### Implementation Details

The functionality is implemented by updating the `/facebook/webhook` endpoint in `facebook_integration/routes.py` and introducing a new `digitalocean_integration/agent.py` module. A `prompt.txt` file is added to store the AI prompt. The implementation leverages existing utilities for data storage (`digitalocean_integration/utils.py`) and token management (`shared/tokens.py`).

#### AI Prompt Configuration

To facilitate prompt updates without code changes, the AI prompt is stored in `digitalocean_integration/prompt.txt`. The prompt uses placeholders to inject dynamic data, ensuring the GenAI agent generates responses tailored to the business context.

**File: `digitalocean_integration/prompt.txt`**
```plaintext
You are a sales assistant for a business managing a Facebook page and a Shopify store. Respond to the customer's message based on the provided data.

Customer Message: {message_text}

Shopify Store Metadata: {shopify_metadata}

Shopify Products: {shopify_products}

Facebook Page Metadata: {facebook_metadata}

Conversation History: {conversation_history}

Generate a concise, friendly response that matches the style of the page and uses relevant Shopify product data. Return only the response text suitable for a Facebook Messenger reply.
```

The placeholders (`{message_text}`, `{shopify_metadata}`, `{shopify_products}`, `{facebook_metadata}`, `{conversation_history}`) are replaced with JSON-formatted data during processing, ensuring the GenAI agent has comprehensive context.

#### GenAI Agent Logic

The `digitalocean_integration/agent.py` module encapsulates the logic for data retrieval, prompt formatting, GenAI API interaction, and message sending. Key functions include:

- **get_data_from_spaces**: Retrieves data from DigitalOcean Spaces, returning an empty list for non-existent conversation files to simplify appending.
- **generate_agent_response**: Fetches Shopify metadata, products, Facebook page metadata, and conversation history, formats the prompt, and calls the GenAI API.
- **send_facebook_message**: Sends the AI-generated response to the user via the Facebook Messenger API.

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
        "Authorization": f"Bearer {os.getenv('AGENT_API_KEY')}",
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

#### Webhook Endpoint Modifications

The `/facebook/webhook` endpoint in `facebook_integration/routes.py` is updated to integrate the GenAI agent. The `messaging` block is modified to:
- Validate and store incoming messages in `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`.
- Invoke `generate_agent_response` to generate an AI response.
- Send the response using `send_facebook_message`.
- Format the AI response as a Facebook Messenger payload and append it to the conversation file.

**Updated `messaging` Block in `facebook_integration/routes.py`**:
```python
@router.post("/webhook")
async def facebook_webhook(request: Request):
    if not await verify_webhook(request):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    payload = await request.json()
    if payload.get("object") != "page":
        raise HTTPException(status_code=400, detail="Invalid webhook object")

    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=os.getenv("SPACES_REGION", "nyc3"),
        endpoint_url=os.getenv("SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"),
        aws_access_key_id=os.getenv("SPACES_API_KEY"),
        aws_secret_access_key=os.getenv("SPACES_API_SECRET")
    )

    for entry in payload.get("entry", []):
        page_id = entry.get("id")
        if not page_id:
            continue

        access_token = token_storage.get_token(f"FACEBOOK_ACCESS_TOKEN_{page_id}")
        if not access_token:
            print(f"Access token not found for page {page_id}")
            continue

        user_uuid = token_storage.get_token(f"PAGE_UUID_{page_id}")
        if not user_uuid:
            print(f"User UUID not found for page {page_id}")
            continue

        print(f"Received webhook event for page {page_id}: {entry}")

        if "messaging" in entry:
            for message_event in entry.get("messaging", []):
                sender_id = message_event.get("sender", {}).get("id")
                recipient_id = message_event.get("recipient", {}).get("id")
                if not sender_id or not recipient_id or sender_id == page_id:
                    continue

                message_text = message_event.get("message", {}).get("text")
                if not message_text:
                    continue

                spaces_key = f"users/{user_uuid}/facebook/{page_id}/conversations/{sender_id}.json"
                conversation = []
                is_new_conversation = False
                try:
                    response = s3_client.get_object(Bucket=os.getenv("SPACES_BUCKET"), Key=spaces_key)
                    conversation = json.loads(response["Body"].read().decode())
                    print(f"Continuing conversation for sender {sender_id} on page {page_id}")
                except s3_client.exceptions.NoSuchKey:
                    is_new_conversation = True
                    print(f"New conversation started for sender {sender_id} on page {page_id}")

                conversation.append(message_event)
                if has_data_changed(conversation, spaces_key, s3_client):
                    upload_to_spaces(conversation, spaces_key, s3_client)
                    print(f"Uploaded conversation payload to Spaces: {spaces_key} (new: {is_new_conversation})")

                # Generate and send AI response
                try:
                    agent_response = await generate_agent_response(page_id, sender_id, message_text, user_uuid)
                    response_text = agent_response["text"]
                    sent_message_id = await send_facebook_message(page_id, sender_id, response_text, access_token)

                    # Format AI response to match Facebook Messenger payload
                    agent_payload = {
                        "sender": {"id": page_id},
                        "recipient": {"id": sender_id},
                        "timestamp": int(time.time() * 1000),
                        "message": {"mid": sent_message_id, "text": response_text}
                    }
                    conversation.append(agent_payload)
                    if has_data_changed(conversation, spaces_key, s3_client):
                        upload_to_spaces(conversation, spaces_key, s3_client)
                        print(f"Uploaded AI response to Spaces: {spaces_key}")
                except Exception as e:
                    print(f"Failed to generate or send AI response for sender {sender_id} on page {page_id}: {str(e)}")

        if "changes" in entry:
            try:
                page_data = await get_facebook_data(access_token)
                spaces_key = f"users/{user_uuid}/facebook/{page_id}/page_metadata.json"
                if has_data_changed(page_data, spaces_key, s3_client):
                    upload_to_spaces(page_data, spaces_key, s3_client)
                    print(f"Uploaded metadata to Spaces for page {page_id}")
            except Exception as e:
                print(f"Failed to upload metadata for page {page_id}: {str(e)}")

    return {"status": "success"}
```

### Environment Variables

The following environment variables are required for the GenAI integration:
- `AGENT_API_KEY`: The API key for accessing the DigitalOcean GenAI API.
- `GENAI_ENDPOINT` (optional): The endpoint for the GenAI API, defaulting to `https://api.genai.digitalocean.com/v1/llama3.3-70b-instruct`.

Ensure these are set in the `.env` file or environment configuration, alongside existing variables like `SPACES_API_KEY` and `FACEBOOK_APP_SECRET`.

### Error Handling

The implementation includes robust error handling:
- **Spaces Access**: If a conversation file does not exist, an empty list is returned to initialize a new conversation.
- **Prompt File**: A `FileNotFoundError` raises an HTTP 500 error if `prompt.txt` is missing.
- **GenAI API**: Non-200 responses from the GenAI API raise an HTTP 500 error with details.
- **Facebook API**: Failed message sends are logged and raise an HTTP 500 error.

Future subchapters (e.g., 8.3) may expand on fallback mechanisms, such as default responses or retry logic.

### Testing Considerations

To test this integration:
1. Send a test message to a connected Facebook page via the Messenger API.
2. Verify the message is stored in `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`.
3. Confirm the AI response is sent to the user and appended to the conversation file with the correct payload format.
4. Check logs for errors in data retrieval, API calls, or Spaces uploads.

A dedicated subchapter (e.g., 8.4) may formalize testing procedures.

### Future Extensibility

The use of platform-specific directories (`facebook/`, `shopify/`) and files (`page_metadata.json`, `shop_products.json`) ensures compatibility with future integrations (e.g., Instagram messaging). The separate `prompt.txt` file allows rapid iteration on the AI’s behavior without code changes.

This implementation completes the core GenAI response functionality, building on the existing data pipelines and setting the stage for further enhancements in subsequent subchapters.