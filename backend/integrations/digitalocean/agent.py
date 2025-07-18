import logging
import os
import json
import time
from fastapi import HTTPException
from openai import AsyncOpenAI
from shared.tokens import TokenStorage
from shared.utils import check_endpoint_accessibility, save_local_data, load_local_data
from shared.config import config

logger = logging.getLogger(__name__)

token_storage = TokenStorage()
client = AsyncOpenAI(
    api_key=config.agent_api_key,
    base_url=config.agent_endpoint.rstrip("/") + "/api/v1"
)

async def generate_agent_response(page_id: str, sender_id: str, message_text: str, user_uuid: str) -> dict:
    logger.info(f"Generating AI response for page {page_id}, sender {sender_id}, message: {message_text}")
    
    base_endpoint = config.agent_endpoint
    health_endpoint = base_endpoint.rstrip("/") + "/health"
    api_key = config.agent_api_key
    
    if not base_endpoint.startswith("https://"):
        logger.error("Invalid AGENT_ENDPOINT format")
        raise HTTPException(status_code=500, detail="Invalid AGENT_ENDPOINT format")
    if not api_key:
        logger.error("AGENT_API_KEY is not set")
        raise HTTPException(status_code=500, detail="AGENT_API_KEY is not set")

    is_accessible, accessibility_message = await check_endpoint_accessibility(
        endpoint=health_endpoint,
        auth_key=api_key,
        endpoint_type="api",
        method="GET"
    )
    if not is_accessible:
        logger.error(f"GenAI API health check failed: {accessibility_message}")
        raise HTTPException(status_code=500, detail=accessibility_message)

    shopify_data_key = f"users/{user_uuid}/shopify/data.json"
    facebook_data_key = f"users/{user_uuid}/facebook/data.json"
    shopify_data = await load_local_data(shopify_data_key)
    facebook_data = await load_local_data(facebook_data_key)

    shopify_metadata = shopify_data.get("metadata", {})
    shopify_products = shopify_data.get("products", {})
    facebook_page_data = next((page for page in facebook_data.get("data", []) if page["id"] == page_id), {})
    conversation_history = [
        msg for msg in facebook_data.get("conversations", {}).get(sender_id, [])
        if msg.get("recipient", {}).get("id") == page_id
    ]

    if not facebook_page_data:
        logger.warning(f"No page data found for page_id {page_id} in user {user_uuid}")
    if not conversation_history:
        logger.info(f"No conversation history found for sender {sender_id} on page {page_id}")

    try:
        with open("digitalocean_integration/prompt.txt", "r") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error("Prompt file not found at digitalocean_integration/prompt.txt")
        raise HTTPException(status_code=500, detail="Prompt file not found")

    prompt = prompt_template.format(
        message_text=message_text,
        shopify_metadata=json.dumps(shopify_metadata, indent=2),
        shopify_products=json.dumps(shopify_products, indent=2),
        facebook_metadata=json.dumps(facebook_page_data, indent=2),
        conversation_history=json.dumps(conversation_history, indent=2)
    )

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100,
            extra_body={"include_retrieval_info": True, "retrieval_method": "rewrite", "k": 5}
        )
        logger.info(f"GenAI API response: {response.choices[0].message.content}")
        return {
            "text": response.choices[0].message.content.strip(),
            "message_id": f"agent_mid_{int(time.time())}"
        }
    except Exception as e:
        logger.error(f"GenAI API request failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GenAI API request failed: {str(e)}")