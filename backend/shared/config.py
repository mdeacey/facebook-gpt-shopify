from environs import Env

env = Env()
env.read_env()

class Config:
    facebook_app_id = env.str("FACEBOOK_APP_ID")
    facebook_app_secret = env.str("FACEBOOK_APP_SECRET")
    facebook_redirect_uri = env.str("FACEBOOK_REDIRECT_URI")
    facebook_webhook_address = env.str("FACEBOOK_WEBHOOK_ADDRESS")
    facebook_verify_token = env.str("FACEBOOK_VERIFY_TOKEN")
    shopify_api_key = env.str("SHOPIFY_API_KEY")
    shopify_api_secret = env.str("SHOPIFY_API_SECRET")
    shopify_redirect_uri = env.str("SHOPIFY_REDIRECT_URI")
    shopify_webhook_address = env.str("SHOPIFY_WEBHOOK_ADDRESS")
    shopify_app_name = env.str("SHOPIFY_APP_NAME")
    state_token_secret = env.str("STATE_TOKEN_SECRET")
    agent_api_key = env.str("AGENT_API_KEY")
    agent_endpoint = env.str("AGENT_ENDPOINT")

config = Config()