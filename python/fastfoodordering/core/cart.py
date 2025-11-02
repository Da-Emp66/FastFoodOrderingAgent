import requests
import json

class Cart:
    """
    Cart class to fetch and parse cart contents from supported online stores.
    """

    def __init__(self, url, headers=None, cookies=None):
        
        self.keywords = {
            "mcdonalds": ["mcdonald"]
            # "burgerking": [""]
            # "subway": ["subway"]
            # "tacobell": ["tacobell"]
        }

        self.url = url
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.payload = None
        self.cart_data = None
        self.items = []

        self.site = self.supported_site(url)

    def supported_site(self, url):
        for key, words in self.keywords.items():
            if any(sub in url for sub in words):
                return key

    def build_payload(self, order_cart_id):
        """Build a GraphQL request payload for supported sites."""
        if self.site == "mcdonalds":
            self.payload = {
                "operationName":"listCarts",
                "variables":{"input":{"cartContextFilter":{"experienceCase":"MULTI_CART_EXPERIENCE_CONTEXT","multiCartExperienceContext":{"storeId":"2473308"}},
                "cartFilter":{"shouldIncludeSubmitted":True}}},
                "query":"query listCarts($input: ListCartsInput!) {\n  listCarts(input: $input) {\n    ...ConsumerOrderCartFragment\n    __typename\n  }\n}\n\nfragment ConsumerOrderCartFragment on OrderCart {\n  id\n  hasError\n  isConsumerPickup\n  isConvenienceCart\n  isMerchantShipping\n  offersDelivery\n  offersPickup\n  subtotal\n  urlCode\n  groupCart\n  groupCartPollInterval\n  isCatering\n  isBundle\n  cateringInfo {\n    cateringVersion\n    minOrderSize\n    maxOrderSize\n    orderInAdvanceInSeconds\n    cancelOrderInAdvanceInSeconds\n    __typename\n  }\n  shortenedUrl\n  maxIndividualCost\n  serviceRateMessage\n  isOutsideDeliveryRegion\n  currencyCode\n  menu {\n    id\n    hoursToOrderInAdvance\n    name\n    minOrderSize\n    isCatering\n    __typename\n  }\n  creator {\n    id\n    firstName\n    lastName\n    localizedNames {\n      informalName\n      formalName\n      formalNameAbbreviated\n      __typename\n    }\n    __typename\n  }\n  deliveries {\n    id\n    quotedDeliveryTime\n    __typename\n  }\n  submittedAt\n  restaurant {\n    id\n    name\n    maxOrderSize\n    coverImgUrl\n    slug\n    address {\n      printableAddress\n      street\n      lat\n      lng\n      __typename\n    }\n    business {\n      id\n      name\n      __typename\n    }\n    __typename\n  }\n  storeDisclaimers {\n    id\n    disclaimerDetailsLink\n    disclaimerLinkSubstring\n    disclaimerText\n    displayTreatment\n    __typename\n  }\n  orders {\n    ...ConsumerOrdersFragment\n    __typename\n  }\n  teamAccount {\n    id\n    name\n    __typename\n  }\n  ...InvalidItemsFragment\n  ...ConsumerOrderCartDomainFragment\n  __typename\n}\n\nfragment InvalidItemsFragment on OrderCart {\n  invalidItems {\n    itemId\n    storeId\n    itemQuantityInfo {\n      discreteQuantity {\n        quantity\n        unit\n        __typename\n      }\n      continuousQuantity {\n        quantity\n        unit\n        __typename\n      }\n      __typename\n    }\n    name\n    itemExtrasList\n    menuId\n    __typename\n  }\n  __typename\n}\n\nfragment ConsumerOrdersFragment on Order {\n  id\n  consumer {\n    firstName\n    lastName\n    id\n    localizedNames {\n      informalName\n      formalName\n      formalNameAbbreviated\n      __typename\n    }\n    __typename\n  }\n  isSubCartFinalized\n  orderItems {\n    id\n    options {\n      id\n      name\n      quantity\n      nestedOptions\n      __typename\n    }\n    nestedOptions\n    specialInstructions\n    substitutionPreference\n    quantity\n    singlePrice\n    priceOfTotalQuantity\n    continuousQuantity\n    unit\n    purchaseType\n    estimatedPricingDescription\n    item {\n      id\n      imageUrl\n      name\n      price\n      minAgeRequirement\n      category {\n        title\n        __typename\n      }\n      extras {\n        id\n        title\n        description\n        __typename\n      }\n      __typename\n    }\n    bundleStore {\n      id\n      name\n      isPrimary\n      __typename\n    }\n    __typename\n  }\n  paymentCard {\n    id\n    stripeId\n    __typename\n  }\n  paymentLineItems {\n    subtotal\n    taxAmount\n    subtotalTaxAmount\n    feesTaxAmount\n    serviceFee\n    __typename\n  }\n  __typename\n}\n\nfragment ConsumerOrderCartDomainFragment on OrderCart {\n  domain {\n    giftInfo {\n      recipientName\n      recipientGivenName\n      recipientFamilyName\n      recipientPhone\n      recipientEmail\n      cardMessage\n      cardId\n      shouldNotifyTrackingToRecipientOnDasherAssign\n      shouldNotifyRecipientForDasherQuestions\n      senderName\n      shouldRecipientScheduleGift\n      hasGiftIntent\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n"
            }
        else:
            raise ValueError(f"Unsupported site for URL: {self.url}")

    def fetch(self):
        if not self.payload:
            raise ValueError("Payload not set. Call build_payload() first.")

        response = requests.post(
            self.url,
            headers=self.headers,
            cookies=self.cookies,
            json=self.payload
        )
        response.raise_for_status()
        self.cart_data = response.json()
        return self.cart_data

    def parse_mcdonalds_items(self):
        if not self.cart_data:
            raise ValueError("Cart data not loaded. Call fetch() first.")

        carts = self.cart_data.get("data", {}).get("listCarts", [])
        if not carts:
            print("No carts found in response")
            return []

        cart = carts[0]
        self.items = []

        for order in cart.get("orders", []):
            for item in order.get("orderItems", []):
                quantity = item.get("quantity", 1)
                total_price_cents = item.get("priceOfTotalQuantity", 0)
                unit_price_dollars = (total_price_cents / quantity) / 100 if quantity else 0

                self.items.append({
                    "name": item["item"]["name"],
                    "price_each": round(unit_price_dollars, 2),
                    "quantity": quantity,
                    "total_price": round(total_price_cents / 100, 2)
                })

        return self.items

    def to_json(self):
        return json.dumps(self.items, indent=2)


# Example usage: Network request info needs to be fetched from stagehand
#   sometimes a refresh is necessary for it to be visible in my local browser
def example():
    url = "https://mcdonalds.order.online/graphql/detailedCartItems?operation=detailedCartItems"

    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://mcdonalds.order.online",
        "referer": "https://mcdonalds.order.online/",
        "x-channel-id": "marketplace",
        "x-experience-id": "storefront",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    cookies = {
        "dd_device_session_id": "c16fa556-d42d-470a-8ad5-a2864cc41954",
        "dd_delivery_correlation_id": "3b9af589-bbbc-4e95-873d-b752fc06e67c",
        "dd_session_id": "sx_567e0dbd28654ba4b3e295194ceeec56",
        "rskxRunCookie": "0",
        "rCookie": "qc4lguh9biqh94m5tlbl2mhh8axwd",
        "__ssid": "02f5c1010a15fd50a3f5e59a9a5dd95",
        "ajs_anonymous_id": "182c3319-9516-47e9-b585-ee62630c4ee9",
        "__cf_bm": "QvdNtl9L9U.oALxCarO8w4PIzJoi8rNldbeZ4_yJQsQ-1762117419-1.0.1.1-TBTiSf0v7csaTcCzEXjAKuJo4jqM0x1hA.TupLtC17Y8jbDRJF7307oVYfF7hxOz9Ger4Tz6eRXnrPXyS2kkmQ7geGpDywjhp6TzgoKL_gU",
        "_cfuvid": "mmdNREgG0sOAfINaYK8_Bf621AAs0z6vsD20GBn1Bm0-1762117419461-0.0.1.1-604800000",
        "amplitude_idundefinedorder.online": "eyJvcHRPdXQiOmZhbHNlLCJzZXNzaW9uSWQiOm51bGwsImxhc3RFdmVudFRpbWUiOm51bGwsImV2ZW50SWQiOjAsImlkZW50aWZ5SWQiOjAsInNlcXVlbmNlTnVtYmVyIjowfQ",
        "dd_market_id": "38",
        "dd_market_id": "38",
        "ddweb_session_id": "eba4cf9a-9c62-435f-9534-f0012b96d07f:0:019a42e3-4312-72fc-b4a5-3d69e3844cb9",
        "ddweb_token": "eyJhbGciOiJIUzI1NiJ9.eyJvcmlnX2lhdCI6MTc2MjExNzQ0NiwicGVkcmVnYWwiOnsiaWQiOiI2OTViYTIzOC1lMjg0LTRjNzItODY1MC04YTQwZDNmN2M3ZDgifSwiZXhwIjoxNzYyMzc2NjQ2LCJ1c2VyIjp7ImF1dGhfdmVyc2lvbiI6MSwiaXNfc3RhZmYiOmZhbHNlLCJpZCI6MTEyNTkwMDQxMTk2MTU2NCwiZW1haWwiOiI4MWM0ZmJlZC05YzczLTQ4N2QtOTkyZS04MWY4MzVmMmRkZWVAZ3Vlc3QuZG9vcmRhc2guY29tIn0sImNpZCI6MTY3MTAzNTM5MzY1MDUzODU2OH0.YB37y2vQ-Gb-oo0eJWZoZhx37AIRr8OgGTa6gLhJ08E:",
        "lastRskxRun": "1762117780971",
        "amplitude_id_bf1b161b213fd0b483bb77e6e31ce20corder.online": "eyJkZXZpY2VJZCI6IjJjNzM2N2I3LWQyZGItNDViMy1iYmYzLTEzNzYzYWNiNWRlZFIiLCJ1c2VySWQiOm51bGwsIm9wdE91dCI6ZmFsc2UsInNlc3Npb25JZCI6MTc2MjExNzQyMjExOCwibGFzdEV2ZW50VGltZSI6MTc2MjExNzg3OTQ3MSwiZXZlbnRJZCI6MTg2LCJpZGVudGlmeUlkIjo0LCJzZXF1ZW5jZU51bWJlciI6MTkwfQ",
        "dd_device_id": "dx_9021f54d4184427b971799ac060e3840",
        "authState": "2de04de4-c14d-499c-85e7-4e330377b49b"
        # "cf_clearance": "ujzpxr2Oazzs8bvyinqqMwfk4JZK50h6fKmhj5jBdN8-1762118208-1.2.1.1-f38ROA4RUfgSZc_8BcuqakdLu3G95XJQtd7CHZGM2dAUPI7NOogugXC3f8yK3KrCaLSckgUJqc2dXVoBIzs2Mo4gU5lxSsVu4oadfemmMxdwV7EKuMOlQFLVxN_G6ABOIJhEwcHE0nim3t_oYPi26XAcRFdqQyjFcH4LOxbtW8Xyn1Wvl0rm9GDzMAD2D6eLuuKmpg3.zCkfCbzWL5tERg9p6TxNw4O8FPSFiGSYBtg' \"
    }

    cart = Cart(url, headers=headers, cookies=cookies)
    cart.build_payload(order_cart_id="a29d5d9e-3bba-435f-a7af-2cc15e0c2e32")
    cart.fetch()
    cart.parse_mcdonalds_items()
    print(cart.to_json())

if __name__=="__main__":
    example()
