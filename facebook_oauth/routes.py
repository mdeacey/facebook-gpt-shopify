import os
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_user_pages

router = APIRouter()

@router.get("/login")
async def start_oauth():
    client_id = os.getenv("FACEBOOK_APP_ID")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
    scope = "pages_messaging,pages_show_list"

    print(f"FACEBOOK_APP_ID: {client_id}, REDIRECT_URI: {redirect_uri}")  # Debug log

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Facebook app config missing")
    
    # Validate client_id format (numeric string, 15–20 digits)
    if not re.match(r'^\d{15,20}$', client_id):
        raise HTTPException(status_code=500, detail="Invalid FACEBOOK_APP_ID format")

    auth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"
    )

    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")

    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")

    token_data = await exchange_code_for_token(code)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    pages = await get_user_pages(token_data["access_token"])
    
    return JSONResponse(content={"token_data": token_data, "pages": pages})