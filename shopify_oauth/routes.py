import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_price_rules,read_discounts,read_content,read_locations,read_marketing_events,read_shipping,read_gift_cards,read_products,read_publications"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify app config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&response_type=code"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")

    if not code or not shop:
        raise HTTPException(status_code=400, detail="Missing code or shop parameter")

    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    # Fetch Shopify data
    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    
    # Extract data from the GraphQL response
    data = shopify_data.get("data", {})
    shop_info = data.get("shop", {})
    products = [edge["node"] for edge in data.get("products", {}).get("edges", [])]
    price_rules = [edge["node"] for edge in data.get("codeDiscountNodes", {}).get("edges", [])]
    discount_codes = [edge["node"] for edge in data.get("codeDiscountNodes", {}).get("edges", [])]
    marketing_events = [edge["node"] for edge in data.get("marketingEvents", {}).get("edges", [])]
    collections = [edge["node"] for edge in data.get("collections", {}).get("edges", [])]
    articles = [edge["node"] for edge in data.get("articles", {}).get("edges", [])]
    blogs = [edge["node"] for edge in data.get("blogs", {}).get("edges", [])]
    pages = [edge["node"] for edge in data.get("pages", {}).get("edges", [])]
    inventory_items = [edge["node"] for edge in data.get("inventoryItems", {}).get("edges", [])]
    product_tags = [edge["node"] for edge in data.get("productTags", {}).get("edges", [])]
    product_types = [edge["node"] for edge in data.get("productTypes", {}).get("edges", [])]
    product_variants = [edge["node"] for edge in data.get("productVariants", {}).get("edges", [])]

    return JSONResponse(content={
        "token_data": token_data,
        "shop_info": shop_info,
        "products": products,
        "price_rules": price_rules,
        "discount_codes": discount_codes,
        "marketing_events": marketing_events,
        "collections": collections,
        "articles": articles,
        "blogs": blogs,
        "pages": pages,
        "inventory_items": inventory_items,
        "product_tags": product_tags,
        "product_types": product_types,
        "product_variants": product_variants
    })