# Chapter 5: Shopify Data Sync
## Subchapter 5.3: Testing Shopify Webhooks and Polling

### Introduction
With Shopify webhooks and polling set up in Subchapters 5.1 and 5.2, this subchapter verifies their functionality through integrated tests within the OAuth flow. After successful authentication, the FastAPI application tests the webhook endpoint and polling mechanism for each authenticated shop, covering shop metadata (e.g., `name`, `primaryDomain`) and product data (products, discounts, collections), using the UUID from the SQLite-based session mechanism (Chapter 3). Data is stored in temporary files (`<shop_name>/shop_metadata.json` and `<shop_name>/shop_products.json`), and tests confirm correct data storage. The tests return consistent JSON results to ensure the GPT Messenger sales bot reliably processes and stores non-sensitive data, preparing for cloud storage in Chapter 6 (`users/<uuid>/shopify/<shop_name>/shop_metadata.json` and `users/<uuid>/shopify/<shop_name>/shop_products.json`).

### Prerequisites
- Completed Chapters 1–4 and Subchapters 5.1–5.2.
- FastAPI application running locally (e.g., `http://localhost:5000`) or in a production-like environment.
- Shopify API credentials (`SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_REDIRECT_URI`, `SHOPIFY_WEBHOOK_ADDRESS`) and `STATE_TOKEN_SECRET` set in `.env`.
- `session_id` cookie set by Shopify OAuth (Chapter 3).
- SQLite databases (`tokens.db`, `sessions.db`) set up (Chapter 3).
- Permissions `read_product_listings`, `read_inventory`, `read_discounts`, `read_locations`, `read_products` configured.

---

### Step 1: Test via OAuth Flow
The tests for webhooks and polling are executed during the OAuth callback, using the `session_id` cookie to retrieve the UUID.

**Instructions**:
1. Run the app:
   ```bash
   python app.py
   ```
2. Initiate Shopify OAuth:
   ```
   http://localhost:5000/shopify/acme-7cu19ngr/login
   ```
   or, for GitHub Codespaces:
   ```
   https://your-codespace-id-5000.app.github.dev/shopify/acme-7cu19ngr/login
   ```
3. Log in to your Shopify store and authorize the app, granting required permissions.

**Expected Output**:
- The browser redirects to the callback endpoint, e.g.:
  ```
  http://localhost:5000/shopify/callback?code=abc123&shop=acme-7cu19ngr.myshopify.com&state=1751277990%3AMhg1D2nYmAE%3A550e8400-e29b-41d4-a716-446655440000%3Axo_PXjcazb2NsA07TvOPB5kioTgIDLZypAV3MZjyKiE%3D
  ```
- The browser displays a JSON response:
  ```json
  {
    "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "token_data": {
      "access_token": "shpat_1234567890abcdef",
      "scope": "read_product_listings,read_inventory,read_discounts,read_locations,read_products"
    },
    "shopify_data": {
      "metadata": {
        "data": {
          "shop": {
            "name": "Acme Snowboards",
            "primaryDomain": {
              "url": "https://acme-7cu19ngr.myshopify.com"
            }
          }
        }
      },
      "products": {
        "data": {
          "products": {
            "edges": [
              {
                "node": {
                  "title": "Premium Snowboard",
                  "description": "High-quality snowboard for all levels",
                  "handle": "premium-snowboard",
                  "productType": "Snowboard",
                  "vendor": "Acme",
                  "tags": ["snowboard", "winter"],
                  "status": "ACTIVE",
                  "variants": {
                    "edges": [
                      {
                        "node": {
                          "title": "Default Title",
                          "price": "299.99",
                          "availableForSale": true,
                          "inventoryItem": {
                            "inventoryLevels": {
                              "edges": [
                                {
                                  "node": {
                                    "quantities": [
                                      {
                                        "name": "available",
                                        "quantity": 50
                                      }
                                    ],
                                    "location": {
                                      "name": "Main Warehouse"
                                    }
                                  }
                                }
                              ]
                            }
                          }
                        }
                      }
                    ]
                  },
                  "metafields": {
                    "edges": []
                  }
                }
              }
            ],
            "pageInfo": {
              "hasNextPage": false,
              "endCursor": null
            }
          },
          "codeDiscountNodes": {
            "edges": [
              {
                "node": {
                  "codeDiscount": {
                    "title": "WINTER10",
                    "codes": {
                      "edges": [
                        {
                          "node": {
                            "code": "WINTER10"
                          }
                        }
                      ]
                    },
                    "customerGets": {
                      "value": {
                        "percentage": 0.1
                      }
                    },
                    "startsAt": "2025-01-01T00:00:00Z",
                    "endsAt": "2025-03-31T23:59:59Z"
                  }
                }
              }
            ],
            "pageInfo": {
              "hasNextPage": false,
              "endCursor": null
            }
          },
          "collections": {
            "edges": [
              {
                "node": {
                  "title": "Winter Gear",
                  "handle": "winter-gear",
                  "products": {
                    "edges": [
                      {
                        "node": {
                          "title": "Premium Snowboard"
                        }
                      }
                    ]
                  }
                }
              }
            ],
            "pageInfo": {
              "hasNextPage": false,
              "endCursor": null
            }
          }
        }
      }
    },
    "webhook_test": {"status": "success"},
    "polling_test": {"status": "success"}
  }
  ```
- Server logs show:
  ```
  INFO:     127.0.0.1:0 - "GET /shopify/acme-7cu19ngr/login HTTP/1.1" 307 Temporary Redirect
  Webhook registered for acme-7cu19ngr.myshopify.com: products/update
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Test Product'}}
  Wrote metadata to acme-7cu19ngr.myshopify.com/shop_metadata.json and products to acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  Webhook test result for acme-7cu19ngr.myshopify.com: {'status': 'success'}
  Polling test result for acme-7cu19ngr.myshopify.com: Success
  INFO:     127.0.0.1:0 - "GET /shopify/callback?code=...&shop=...&state=... HTTP/1.1" 200 OK
  ```

**What to Look For**:
- **Webhook Success**: `webhook_test: {"status": "success"}` confirms the webhook endpoint works.
- **Polling Success**: `polling_test: {"status": "success"}` confirms polling functionality.
- **UUID**: `user_uuid` matches the Shopify OAuth response.
- **Shopify Data**: `shopify_data.metadata` contains `shop` fields; `shopify_data.products` contains `products`, `codeDiscountNodes`, and `collections`.
- **Errors**: If `webhook_test` or `polling_test` shows `{"status": "failed", "message": "..."}`, check the `message` for details.

**Screenshot Reference**: Browser showing JSON response; terminal showing logs.

**Why?**
- Confirms webhook and polling functionality for shop and product data using `TokenStorage` and `SessionStorage`.
- Verifies split storage in `shop_metadata.json` and `shop_products.json`.
- Ensures non-sensitive data for the sales bot, preparing for Spaces in Chapter 6.

### Step 2: Verify Webhook Functionality
**Action**: Simulate a product update event to test the webhook endpoint.

**Instructions**:
1. Log into your Shopify Admin.
2. Update a product (e.g., change the title of “Premium Snowboard” to “Premium Snowboard Pro”).
3. Check server logs for webhook event processing.

**Expected Output**:
- Logs show:
  ```
  Received products/update event from acme-7cu19ngr.myshopify.com: {'product': {'id': 12345, 'title': 'Premium Snowboard Pro'}}
  Wrote metadata to acme-7cu19ngr.myshopify.com/shop_metadata.json and products to acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Verifies the `/shopify/webhook` endpoint processes `products/update` events using `TokenStorage`.
- Confirms data is stored in split temporary files.

### Step 3: Verify Polling Functionality
**Action**: Manually trigger the daily polling function to test data retrieval.

**Instructions**:
1. Modify `app.py` to run `daily_poll` immediately (temporary):
   ```python
   from shopify_integration.utils import daily_poll
   daily_poll()  # Add this line
   ```
2. Run: `python app.py`.
3. Check logs for polling results.

**Expected Output**:
- Logs show:
  ```
  Polled and wrote data to acme-7cu19ngr.myshopify.com/shop_metadata.json and acme-7cu19ngr.myshopify.com/shop_products.json for acme-7cu19ngr.myshopify.com
  ```

**Why?**
- Confirms `daily_poll` retrieves shop and product data, storing in split files.
- Verifies `TokenStorage` usage for token/UUID retrieval.

### Step 4: Verify Temporary File Storage
**Action**: Check the temporary file storage for shop and product data.

**Instructions**:
1. Verify files exist:
   - Metadata: `acme-7cu19ngr.myshopify.com/shop_metadata.json`
   - Products: `acme-7cu19ngr.myshopify.com/shop_products.json`
2. Open the files and confirm their contents.

**Expected Content**:
- Metadata (`acme-7cu19ngr.myshopify.com/shop_metadata.json`):
  ```json
  {
    "data": {
      "shop": {
        "name": "Acme Snowboards",
        "primaryDomain": {
          "url": "https://acme-7cu19ngr.myshopify.com"
        }
      }
    }
  }
  ```
- Products (`acme-7cu19ngr.myshopify.com/shop_products.json`):
  ```json
  {
    "data": {
      "products": {
        "edges": [
          {
            "node": {
              "title": "Premium Snowboard",
              "description": "High-quality snowboard for all levels",
              ...
            }
          }
        ],
        "pageInfo": {
          "hasNextPage": false,
          "endCursor": null
        }
      },
      "codeDiscountNodes": {
        "edges": [
          {
            "node": {
              "codeDiscount": {
                "title": "WINTER10",
                ...
              }
            }
          }
        ],
        "pageInfo": {
          "hasNextPage": false,
          "endCursor": null
        }
      },
      "collections": {
        "edges": [
          {
            "node": {
              "title": "Winter Gear",
              ...
            }
          }
        ],
        "pageInfo": {
          "hasNextPage": false,
          "endCursor": null
        }
      }
    }
  }
  ```

**Why?**
- Confirms data is stored correctly in split temporary files, consistent with Subchapters 5.1–5.2.
- Verifies `shop_metadata.json` contains `shop` fields and `shop_products.json` contains `products`, `codeDiscountNodes`, and `collections`, preparing for Spaces in Chapter 6.

### Step 5: Troubleshoot Issues
**Action**: If the JSON response or logs show failures, diagnose and fix issues.

**Common Issues and Fixes**:
1. **Webhook Test Failure (`webhook_test: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Webhook registration or verification failed.
   - **Fix**: Check the `message` (e.g., HTTP 401 for HMAC issues). Verify `SHOPIFY_API_SECRET` and `SHOPIFY_WEBHOOK_ADDRESS` in `.env`. Ensure the webhook address is accessible.
2. **Polling Test Failure (`polling_test: {"status": "failed", "message": "..."}`)**:
   - **Cause**: Failed to fetch data.
   - **Fix**: Check the `message`. Verify tokens in `tokens.db` using `sqlite3 "${TOKEN_DB_PATH:-./data/tokens.db}" "SELECT key FROM tokens;"`. Check logs for API errors (e.g., HTTP 429).
3. **Missing `session_id` Cookie**:
   - **Cause**: OAuth not completed.
   - **Fix**: Re-run `/shopify/acme-7cu19ngr/login`.
4. **Empty `shopify_data` Fields**:
   - **Cause**: No products or permissions issue.
   - **Fix**: Ensure `read_products`, `read_inventory`, etc., are granted. Verify the store has products.
5. **Missing Files**:
   - **Cause**: File writing failed.
   - **Fix**: Check write permissions and logs for errors.

**Why?**
- Uses JSON responses and logs to debug webhook, polling, or session issues.
- Ensures split file storage is verified.

### Summary: Why This Subchapter Matters
- **Functionality Verification**: Tests confirm webhook and polling systems work for shop and product data.
- **Modularity**: Verifies split storage in `shop_metadata.json` and `shop_products.json`.
- **Security**: Excludes sensitive tokens and uses encrypted storage.
- **Bot Readiness**: Ensures up-to-date data for customer interactions, preparing for Spaces in Chapter 6.

### Next Steps:
- Proceed to Chapter 6 for cloud storage integration.
- Monitor logs to ensure ongoing test success.