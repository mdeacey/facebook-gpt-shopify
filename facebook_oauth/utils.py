import os
import requests

def exchange_code_for_token(code: str):
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "client_id": os.getenv("FACEBOOK_APP_ID"),
        "redirect_uri": os.getenv("FACEBOOK_REDIRECT_URI"),
        "client_secret": os.getenv("FACEBOOK_APP_SECRET"),
        "code": code
    }
    response = requests.get(url, params=params)
    return response.json()

def get_user_pages(access_token: str):
    url = "https://graph.facebook.com/v19.0/me/accounts"
    response = requests.get(url, params={"access_token": access_token})
    return response.json()
