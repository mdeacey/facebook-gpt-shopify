## 8.3 Updating the Facebook Webhook for Responses

This subchapter details updating the `/facebook/webhook` endpoint in `facebook_integration/routes.py` to process incoming Facebook messages, invoke the GenAI agent, store messages and responses in DigitalOcean Spaces, and configure required environment variables in `app.py`. The webhook ensures messages are stored in a conversation file, AI responses are generated and sent, and responses are formatted to match the Facebook Messenger payload structure.

### Overview
The `/facebook/webhook` endpoint handles incoming messages by:
- Validating and storing messages in `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`.
- Invoking `generate_agent_response` to generate an AI response.
- Sending the response via `send_facebook_message`.
- Formatting and appending the response to the conversation file.
- Environment variables (`GENAI_API_KEY`, `GENAI_ENDPOINT`) are added to `app.py` to support the GenAI integration.

New conversations create a new JSON file, while existing conversations append to the existing file.

### Implementation Details
Update the `messaging` block in `facebook_integration/routes.py` to integrate the GenAI agent:

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

Update `app.py` to include `GENAI_API_KEY` in the `required_env_vars` list:

**Updated `app.py`**:
```python
from dotenv import load_dotenv

load_dotenv()

import os
from fastapi import FastAPI
from facebook_integration.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from shopify_integration.utils import daily_poll as shopify_daily_poll
from facebook_integration.utils import daily_poll as facebook_daily_poll
import atexit

required_env_vars = [
    "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET", "FACEBOOK_REDIRECT_URI",
    "FACEBOOK_WEBHOOK_ADDRESS", "FACEBOOK_VERIFY_TOKEN",
    "SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_REDIRECT_URI",
    "SHOPIFY_WEBHOOK_ADDRESS", "SPACES_API_KEY", "SPACES_API_SECRET",
    "SPACES_BUCKET", "SPACES_REGION", "STATE_TOKEN_SECRET",
    "GENAI_API_KEY"
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")
app.include_router(shopify_oauth_router, prefix="/shopify")

@app.get("/")
async def root():
    return {"status": "ok"}

scheduler = BackgroundScheduler()
scheduler.add_job(shopify_daily_poll, CronTrigger(hour=0, minute=0))
scheduler.add_job(facebook_daily_poll, CronTrigger(hour=0, minute=0))
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
```

Add to the `.env` file:
```
GENAI_API_KEY=your_genai_api_key
GENAI_ENDPOINT=https://api.genai.digitalocean.com/v1/llama3.3-70b-instruct
```

### Testing
1. **Test Webhook Processing**: Send a test message via the Facebook Messenger API and verify it is stored in `users/<uuid>/facebook/<page_id>/conversations/<sender_id>.json`.
2. **Test AI Response**: Confirm the AI response is generated, sent to the user, and appended to the conversation file with the correct payload format (`sender`, `recipient`, `timestamp`, `message`).
3. **Test Environment Variables**: Start the application with and without `GENAI_API_KEY` to ensure it fails gracefully if missing.
4. **Expected Outcome**: Messages are stored, AI responses are sent and stored correctly, and the application validates environment variables at startup.

### Notes
- **Prerequisites**: Complete Subchapters 8.1 and 8.2 to ensure `prompt.txt` and `agent.py` are implemented.
- **Error Handling**: The webhook handles missing conversation files and API failures with appropriate logging and HTTP 500 errors.
- The environment variable configuration ensures the GenAI integration is properly set up before the application starts.