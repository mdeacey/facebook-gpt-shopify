import os
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from shopify_oauth.utils import get_shopify_data, preprocess_shopify_data
from .utils import upload_to_spaces, reindex_knowledge_base, verify_shopify_webhook

router = APIRouter()

@router.post("/webhook")
async def webhook_handler(request: Request, verified: bool = Depends(verify_shopify_webhook)):
    if not verified:
        raise HTTPException(status_code=401, detail="Invalid webhook HMAC")

    # Get raw body and headers
    raw_body = await request.body()
    shop_domain = request.headers.get("X-Shopify-Shop-Domain")
    topic = request.headers.get("X-Shopify-Topic")
    webhook_id = request.headers.get("X-Shopify-Webhook-Id")

    if not shop_domain or not topic:
        raise HTTPException(status_code=400, detail="Missing shop domain or topic")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Fetch access token (assumes stored in environment or secure storage)
    access_token = os.getenv(f"SHOPIFY_ACCESS_TOKEN_{shop_domain.replace('.', '_')}")
    if not access_token:
        raise HTTPException(status_code=500, detail="Access token not found for shop")

    # Fetch updated data using existing GraphQL query
    shopify_data = await get_shopify_data(access_token, shop_domain)
    preprocessed_data = preprocess_shopify_data(shopify_data)

    # Upload preprocessed data to Spaces
    spaces_key = f"{shop_domain}/preprocessed_data.json"
    upload_to_spaces(preprocessed_data, spaces_key)

    # Re-index knowledge base
    knowledge_base_id = os.getenv(f"KNOWLEDGE_BASE_ID_{shop_domain.replace('.', '_')}")
    if not knowledge_base_id:
        raise HTTPException(status_code=500, detail="Knowledge base ID not found for shop")
    await reindex_knowledge_base(knowledge_base_id, spaces_key)

    return JSONResponse(content={"status": "success", "webhook_id": webhook_id})