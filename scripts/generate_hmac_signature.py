from dotenv import load_dotenv
import hmac
import hashlib
import base64
import os

load_dotenv()

secret = os.getenv("SHOPIFY_API_SECRET")
if not secret:
    raise ValueError("SHOPIFY_API_SECRET not found in environment variables")

payload = b'{"product": {"id": 12345, "title": "Test Product"}}'
hmac_signature = base64.b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()
print(hmac_signature)