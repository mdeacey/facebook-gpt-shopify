from msgspec import Struct

class FacebookWebhookPayload(Struct):
    object: str
    entry: list[dict]

class ShopifyWebhookPayload(Struct):
    product: dict = {}

class SpacesData(Struct):
    metadata: dict = {}
    products: dict = {}
    data: list = []
    conversations: dict = {}
    paging: dict = {}