import os
import httpx
from fastapi import HTTPException

async def exchange_code_for_token(code: str, shop: str):
    url = f"https://{shop}/admin/oauth/access_token"
    data = {
        "client_id": os.getenv("SHOPIFY_API_KEY"),
        "client_secret": os.getenv("SHOPIFY_API_SECRET"),
        "code": code
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        return response.json()

async def get_shopify_data(access_token: str, shop: str):
    url = f"https://{shop}/admin/api/2025-04/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    query = """
    query SalesBotQuery {
      shop {
        id
        name
        description
        primaryDomain {
          url
        }
      }
      currentAppInstallation {
        id
        accessScopes {
          handle
        }
      }
      publications(first: 1) {
        edges {
          node {
            id
            name
          }
        }
      }
      products(first: 10, sortKey: RELEVANCE) {
        edges {
          node {
            id
            title
            description
            handle
            productType
            vendor
            tags
            variants(first: 5) {
              edges {
                node {
                  id
                  title
                  price
                  availableForSale
                  inventoryItem {
                    id
                    inventoryLevels(first: 5) {
                      edges {
                        node {
                          id
                          quantities(names: ["available"]) {
                            name
                            quantity
                          }
                          location {
                            id
                            name
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            metafields(first: 5) {
              edges {
                node {
                  id
                  key
                  namespace
                  value
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      collections(first: 5, sortKey: TITLE) {
        edges {
          node {
            id
            title
            handle
            description
            products(first: 5) {
              edges {
                node {
                  id
                  title
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      codeDiscountNodes(first: 5, sortKey: TITLE) {
        edges {
          node {
            id
            codeDiscount {
              ... on DiscountCodeBasic {
                title
                codes(first: 5) {
                  edges {
                    node {
                      code
                    }
                  }
                }
                customerGets {
                  value {
                    ... on DiscountAmount {
                      amount {
                        amount
                        currencyCode
                      }
                    }
                    ... on DiscountPercentage {
                      percentage
                    }
                  }
                }
                startsAt
                endsAt
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      locations(first: 5) {
        edges {
          node {
            id
            name
            address {
              city
              country
              zip
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
      marketingEvents(first: 5) {
        edges {
          node {
            id
            description
            type
            startedAt
            endedAt
          }
        }
      }
      articles(first: 5) {
        edges {
          node {
            id
            title
            handle
            publishedAt
          }
        }
      }
      blogs(first: 5) {
        edges {
          node {
            id
            title
            handle
          }
        }
      }
      pages(first: 5) {
        edges {
          node {
            id
            title
            handle
            createdAt
          }
        }
      }
      inventoryItems(first: 5) {
        edges {
          node {
            id
            sku
            createdAt
            inventoryLevels(first: 5) {
              edges {
                node {
                  id
                  quantities(names: ["available"]) {
                    name
                    quantity
                  }
                }
              }
            }
          }
        }
      }
      productTags(first: 5) {
        edges {
          node
        }
      }
      productTypes(first: 5) {
        edges {
          node
        }
      }
      productVariants(first: 5) {
        edges {
          node {
            id
            title
            price
            product {
              id
              title
            }
          }
        }
      }
    }
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"query": query})
        response.raise_for_status()
        response_data = response.json()

        if "errors" in response_data:
            error_message = "; ".join([error["message"] for error in response_data["errors"]])
            raise HTTPException(status_code=400, detail=f"GraphQL query failed: {error_message}")

        return response_data