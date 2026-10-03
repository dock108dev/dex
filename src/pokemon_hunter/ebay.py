import os
import time
from urllib.parse import quote

import httpx

from .models import Settings


class EbayError(RuntimeError):
    pass


class EbayHTTPError(EbayError):
    """Retain only bounded, non-sensitive provider failure fields."""

    def __init__(self, stage, status, response):
        self.stage = stage if stage in {"OAuth", "Browse"} else "Provider"
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        self.code = None
        if self.stage == "OAuth":
            try:
                payload = response.json()
                code = payload.get("error") if isinstance(payload, dict) else None
                if code in (
                    "invalid_client",
                    "invalid_request",
                    "invalid_scope",
                    "unauthorized_client",
                    "unsupported_grant_type",
                ):
                    self.code = code
            except ValueError:
                pass
        super().__init__(f"eBay {self.stage} returned HTTP {self.status}")


class EbayClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        sleep=time.sleep,
        credentials=None,
        extended=False,
    ):
        self.settings = settings
        self.base = (
            "https://api.ebay.com" if settings.environment == "production" else "https://api.sandbox.ebay.com"
        )
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.sleep = sleep
        self.token = None
        self.expires = 0
        self.warnings: list[str] = []
        self.credentials = credentials
        self.extended = extended

    def close(self):
        self.client.close()

    def _request(self, method, path, **kwargs):
        for attempt in range(3):
            try:
                response = self.client.request(method, self.base + path, **kwargs)
            except httpx.TransportError:
                if attempt == 2:
                    raise EbayError("eBay connection failed after three attempts") from None
                self.sleep(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    try:
                        delay = float(response.headers.get("Retry-After", 2**attempt))
                    except ValueError:
                        delay = 2**attempt
                    self.sleep(min(30, max(0, delay)))
                    continue
            return response
        raise EbayError("eBay request failed")

    def access_token(self):
        if self.token and time.monotonic() < self.expires:
            return self.token
        key, secret = (
            self.credentials
            if self.credentials is not None
            else (os.getenv("EBAY_CLIENT_ID"), os.getenv("EBAY_CLIENT_SECRET"))
        )
        if not key or not secret:
            raise EbayError("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in the local .env file")
        response = self._request(
            "POST",
            "/identity/v1/oauth2/token",
            auth=(key, secret),
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
        )
        if response.status_code != 200:
            raise EbayHTTPError("OAuth", response.status_code, response)
        try:
            data = response.json()
            token = data["access_token"]
            lifetime = data["expires_in"]
            if not isinstance(token, str) or not token.strip() or type(lifetime) is not int or lifetime <= 0:
                raise ValueError("Invalid OAuth fields")
            expires = time.monotonic() + max(0, lifetime - 60)
        except (ValueError, KeyError, TypeError, OverflowError):
            raise EbayError("Malformed eBay OAuth response") from None
        # Do not cache any part of an invalid response, including after a 401 refresh.
        self.token, self.expires = token, expires
        return self.token

    def get(self, path, params=None):
        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {self.access_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.settings.marketplace,
            }
            if self.settings.delivery_postal_code:
                location = (
                    f"country={self.settings.delivery_country},zip={self.settings.delivery_postal_code}"
                )
                headers["X-EBAY-C-ENDUSERCTX"] = "contextualLocation=" + quote(location, safe="")
            response = self._request("GET", path, headers=headers, params=params)
            if response.status_code == 401 and attempt == 0:
                self.token = None
                continue
            if response.status_code != 200:
                raise EbayHTTPError("Browse", response.status_code, response)
            try:
                data = response.json()
            except ValueError:
                raise EbayError("eBay returned invalid JSON") from None
            if not isinstance(data, dict) or data.get("errors"):
                raise EbayError("eBay returned an invalid response or API error")
            if data.get("warnings"):
                self.warnings.append("eBay returned API warnings; inspect saved run coverage")
            return data
        raise EbayError("eBay authentication failed")

    def search(self, query: str, buying_option: str):
        limit = self.settings.search.page_size
        for page in range(self.settings.search.max_pages):
            filters = f"buyingOptions:{{{buying_option}}},deliveryCountry:{self.settings.delivery_country}"
            if self.settings.delivery_postal_code:
                filters += f",deliveryPostalCode:{self.settings.delivery_postal_code}"
            data = self.get(
                "/buy/browse/v1/item_summary/search",
                {
                    "q": query,
                    "filter": filters,
                    "limit": limit,
                    "offset": page * limit,
                    "sort": "newlyListed",
                    **({"fieldgroups": "EXTENDED"} if self.extended else {}),
                },
            )
            for item in data.get("itemSummaries", []):
                yield item
            if not data.get("next"):
                return
            if page == self.settings.search.max_pages - 1:
                self.warnings.append(f"Search page cap reached: {buying_option} / {query}")

    def detail(self, item_id: str):
        return self.get("/buy/browse/v1/item/" + quote(item_id, safe=""))


def discover(client: EbayClient, queries: list[str]) -> list[dict]:
    items: dict[str, dict] = {}
    for option in ("AUCTION", "FIXED_PRICE"):
        for query in queries:
            for raw in client.search(query, option):
                item_id = raw.get("itemId")
                if not item_id:
                    continue
                if item_id not in items:
                    items[item_id] = {**raw, "_queries": []}
                else:
                    # Do not infer set composition from search keywords. Preserve
                    # actual API buying options across overlapping query passes.
                    old = items[item_id]
                    options = sorted(set(old.get("buyingOptions", [])) | set(raw.get("buyingOptions", [])))
                    old.update(raw)
                    old["buyingOptions"] = options
                if query not in items[item_id]["_queries"]:
                    items[item_id]["_queries"].append(query)
    return list(items.values())
