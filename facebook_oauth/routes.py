from flask import Blueprint, request, jsonify, redirect
import os
from .utils import exchange_code_for_token, get_user_pages

facebook_oauth_blueprint = Blueprint('facebook_oauth', __name__)

@facebook_oauth_blueprint.route('/start')
def start_oauth():
    client_id = os.getenv("FACEBOOK_APP_ID")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
    scope = "pages_show_list,ads_management,business_management"

    auth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"
    )
    return redirect(auth_url)

@facebook_oauth_blueprint.route('/callback')
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing code"}), 400

    token_data = exchange_code_for_token(code)
    if "access_token" not in token_data:
        return jsonify({"error": "Token exchange failed", "details": token_data}), 400

    pages = get_user_pages(token_data["access_token"])
    return jsonify({"token_data": token_data, "pages": pages})
