Below is the subchapter for updating the Shopify routes file and creating the new DigitalOcean utils file, written to be consistent with the style and structure of Chapter 2 (Subchapter 2.1). It follows a clear, step-by-step tutorial format with explanations, code snippets, and a modular design, ensuring the chapters flow seamlessly.

---

### Chapter 3: DigitalOcean Integration

#### Subchapter 3.2: Initial Data Initialization with DigitalOcean Spaces

This subchapter integrates DigitalOcean Spaces into your FastAPI application to store initial Shopify data after a user authenticates via Shopify OAuth. We’ll update the Shopify callback route to fetch, preprocess, and upload this data to Spaces, ensuring your GPT Messenger sales bot has the foundational data it needs from the start. This builds on the Shopify OAuth setup from Subchapter 2.1 and assumes a Shopify development store and app credentials are configured (Subchapter 2.2). The focus here is on code implementation—DigitalOcean UI setup is covered in Subchapter 3.1, with webhook-based updates deferred to Subchapter 3.3.

---

##### Step 1: Why Store Initial Data in DigitalOcean Spaces?

The sales bot relies on Shopify data (shop details, products, discounts, and collections) to generate recommendations and promotions. Storing this data in DigitalOcean Spaces after OAuth:

- **Ensures Availability**: Provides a persistent, cloud-based store accessible to the bot.
- **Scales Efficiently**: Offloads storage from the app, supporting multiple shops.
- **Prepares for Updates**: Sets up a baseline for incremental updates via webhooks (Subchapter 3.3).

We’ll modify the callback route to upload preprocessed data immediately after authentication, leveraging Spaces’ S3-compatible API for simplicity and reliability.

---

##### Step 2: Project Structure

Building on Chapters 1 and 2, we introduce a `digitalocean_genai` module alongside `shopify_oauth`:

```
.
├── facebook_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── shopify_oauth/
│   ├── __init__.py
│   ├── routes.py
│   └── utils.py
├── digitalocean_genai/
│   ├── __init__.py
│   └── utils.py         # New file for Spaces utilities
├── shared/
│   └── utils.py         # Stateless CSRF helpers
├── .env
├── .env.example
├── app.py
└── requirements.txt
```

- **`digitalocean_genai/utils.py`**: Defines the upload logic for DigitalOcean Spaces.
- **`shopify_oauth/routes.py`**: Updated to integrate the upload functionality.
- **`.env.example`**: Extended with Spaces credentials (added in Step 5).

This modular structure mirrors Subchapter 2.1, keeping related functionality grouped and reusable.

---

##### Step 3: Update shopify_oauth/routes.py

**Action**: Modify the `/shopify/callback` endpoint to upload preprocessed Shopify data to DigitalOcean Spaces after authentication.

**Why?**  
The callback is triggered post-OAuth, making it the ideal point to initialize data storage without additional user interaction. Uploading here ensures the bot has immediate access to the data.

**Instructions**:  
Update `shopify_oauth/routes.py` as follows:

```python
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from .utils import exchange_code_for_token, get_shopify_data, preprocess_shopify_data
from shared.utils import generate_state_token, validate_state_token
from digitalocean_genai.utils import upload_to_spaces  # Add this import

router = APIRouter()

@router.get("/{shop_name}/login")
async def start_oauth(shop_name: str):
    client_id = os.getenv("SHOPIFY_API_KEY")
    redirect_uri = os.getenv("SHOPIFY_REDIRECT_URI")
    scope = "read_product_listings,read_inventory,read_discounts,read_locations,read_products"

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Shopify config missing")

    if not shop_name.endswith(".myshopify.com"):
        shop_name = f"{shop_name}.myshopify.com"

    state = generate_state_token()
    auth_url = (
        f"https://{shop_name}/admin/oauth/authorize?"
        f"client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&state={state}"
    )
    return RedirectResponse(auth_url)

@router.get("/callback")
async def oauth_callback(request: Request):
    code = request.query_params.get("code")
    shop = request.query_params.get("shop")
    state = request.query_params.get("state")

    if not code or not shop or not state:
        raise HTTPException(status_code=400, detail="Missing code/shop/state")

    validate_state_token(state)
    token_data = await exchange_code_for_token(code, shop)
    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    shopify_data = await get_shopify_data(token_data["access_token"], shop)
    preprocessed_data = preprocess_shopify_data(shopify_data)

    # Upload to DigitalOcean Spaces
    spaces_key = f"{shop}/preprocessed_data.json"
    try:
        upload_to_spaces(preprocessed_data, spaces_key)
        upload_status = "success"
    except Exception as e:
        print(f"Failed to upload to Spaces: {str(e)}")
        upload_status = "failed"

    return JSONResponse(content={
        "token_data": token_data,
        "preprocessed_data": preprocessed_data,
        "digitalocean_upload": upload_status
    })
```

**Why?**  
- **Import**: Adds `upload_to_spaces` from the new `digitalocean_genai.utils` module.
- **Upload Logic**: After preprocessing, uploads the data to Spaces with a shop-specific key (e.g., `acme-7cu19ngr.myshopify.com/preprocessed_data.json`).
- **Error Handling**: Wraps the upload in a try-except block, logging failures but allowing the callback to complete, consistent with Subchapter 2.1’s robust error handling.
- **Response**: Extends the JSON response with `digitalocean_upload` status, mirroring Subchapter 2.1’s detailed output.

---

##### Step 4: Create digitalocean_genai/utils.py

**Action**: Define the `upload_to_spaces` function to handle data uploads to DigitalOcean Spaces.

**Why?**  
This utility encapsulates the upload logic, keeping `routes.py` focused on routing. It uses `boto3` to interact with Spaces’ S3-compatible API, ensuring compatibility and ease of use.

**Instructions**:  
Create `digitalocean_genai/utils.py` with:

```python
import os
import boto3
import json
from fastapi import HTTPException

def upload_to_spaces(data: dict, key: str):
    """Upload preprocessed Shopify data to DigitalOcean Spaces."""
    spaces_access_key = os.getenv("SPACES_ACCESS_KEY")
    spaces_secret_key = os.getenv("SPACES_SECRET_KEY")
    spaces_bucket = os.getenv("SPACES_BUCKET")
    spaces_region = os.getenv("SPACES_REGION", "nyc3")

    if not all([spaces_access_key, spaces_secret_key, spaces_bucket]):
        raise HTTPException(status_code=500, detail="Spaces configuration missing")

    session = boto3.session.Session()
    s3_client = session.client(
        "s3",
        region_name=spaces_region,
        endpoint_url=f"https://{spaces_region}.digitaloceanspaces.com",
        aws_access_key_id=spaces_access_key,
        aws_secret_access_key=spaces_secret_key
    )

    try:
        s3_client.put_object(
            Bucket=spaces_bucket,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
            ACL="private"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spaces upload failed: {str(e)}")
```

**Why?**  
- **Credentials**: Retrieved from environment variables, consistent with Subchapter 2.1’s use of `.env`.
- **Boto3 Configuration**: Sets up an S3 client for Spaces, using the region-specific endpoint (e.g., `nyc3`).
- **Upload**: Serializes the data to JSON and uploads it with private access, aligning with security best practices.
- **Error Handling**: Raises HTTP exceptions for failures, mirroring Subchapter 2.1’s approach.

---

##### Step 5: Configure Environment Variables

**Action**: Add DigitalOcean Spaces credentials to your `.env` file.

**Why?**  
These variables authenticate the upload function, keeping sensitive data out of the codebase—consistent with Subchapter 2.1’s security practices.

**Instructions**:  
Update `.env` and `.env.example` with:

**.env.example**:
```plaintext
# Existing credentials from Chapters 1 and 2
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_REDIRECT_URI=http://localhost:5000/facebook/callback
SHOPIFY_API_KEY=your_shopify_api_key
SHOPIFY_API_SECRET=your_shopify_api_secret
SHOPIFY_REDIRECT_URI=http://localhost:5000/shopify/callback
STATE_TOKEN_SECRET=replace_with_secure_token

# DigitalOcean Spaces credentials (from Subchapter 3.1)
SPACES_ACCESS_KEY=your_access_key
SPACES_SECRET_KEY=your_secret_key
SPACES_BUCKET=your_bucket_name
SPACES_REGION=nyc3  # Optional, defaults to "nyc3"
```

Replace placeholders in `.env` with values from your DigitalOcean dashboard (set up in Subchapter 3.1).

**Why?**  
- **New Variables**: Add Spaces-specific keys, bucket, and region.
- **Consistency**: Extends the `.env` approach from Subchapter 2.1, ensuring all credentials are centralized.

---

##### Step 6: Update requirements.txt

**Action**: Add `boto3` to support DigitalOcean Spaces integration.

**Instructions**:  
Update `requirements.txt`:

```
fastapi
uvicorn
httpx
python-dotenv
boto3
```

**Why?**  
- **Boto3**: Required for S3-compatible interactions with Spaces, building on Subchapter 2.1’s dependency list.

---

##### Step 7: Testing Preparation

**Action**: Verify the integration by running the app and checking the upload.

**Instructions**:  
1. Install dependencies: `pip install -r requirements.txt`.
2. Start the server: `uvicorn app:app --host 0.0.0.0 --port 5000 --reload`.
3. Initiate OAuth: Visit `http://localhost:5000/shopify/yourshop/login`.
4. After callback, check the response for `"digitalocean_upload": "success"`.
5. Log in to DigitalOcean Spaces and confirm `yourshop.myshopify.com/preprocessed_data.json` exists in your bucket.

**Why?**  
- **End-to-End Test**: Ensures the OAuth flow triggers a successful upload, consistent with Subchapter 2.1’s testing prep.
- **Deferred Details**: Full testing is covered in Subchapter 3.3, mirroring Subchapter 2.1’s structure.

---

##### Summary: Why This Subchapter Matters

- **Cloud Integration**: Adds DigitalOcean Spaces for scalable, persistent data storage.
- **Seamless Flow**: Updates the Shopify callback to handle uploads post-OAuth, building on Chapter 2.
- **Modular Design**: Introduces `digitalocean_genai/utils.py`, maintaining consistency with Subchapter 2.1’s structure.
- **Bot Readiness**: Stores initial data, preparing for webhook updates in Subchapter 3.3.

**Next Steps**:  
- Configure DigitalOcean Spaces UI and obtain credentials (Subchapter 3.1).  
- Test the full integration (Subchapter 3.3).  
- Implement webhook updates for real-time data sync (Subchapter 3.3).

---

This subchapter aligns with Chapter 2’s tutorial style, using clear steps, code blocks, and detailed explanations to ensure a cohesive learning experience. Let me know if you’d like any refinements!