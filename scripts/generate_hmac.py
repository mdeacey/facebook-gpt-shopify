import os
import hmac
import hashlib
import json
from dotenv import load_dotenv

load_dotenv()

# Payload must match the curl command exactly
payload = {
    "object": "page",
    "entry": [{"id": "test_page_id", "changes": [{"field": "name", "value": "Test Page"}]}]
}
secret = os.getenv("FACEBOOK_APP_SECRET")
if not secret:
    print("Error: FACEBOOK_APP_SECRET not set")
    exit(1)

# Compute HMAC signature
serialized = json.dumps(payload, separators=(',', ':'))
hmac_obj = hmac.new(secret.encode(), serialized.encode(), hashlib.sha1)
signature = f"sha1={hmac_obj.hexdigest()}"
print(f"HMAC Signature: {signature}")