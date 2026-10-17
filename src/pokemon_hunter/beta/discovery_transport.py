"""One-send eBay transport for explicit Shopping discovery actions.

HTTPX phase limits are supplemented by the caller's asyncio wall deadline. No
cookies, environment proxies, redirects, retries or paging. Explicit Browse,
detail and resolution operations share the same finite transport.
"""

import base64
import json
from urllib.parse import quote

import httpx


class ProviderFailure(Exception):
    def __init__(self, stage, status=None, uncertain=False):
        self.stage, self.status, self.uncertain = stage, status, uncertain
        super().__init__(f"eBay {stage} did not complete")


class Transport:
    def __init__(self, *, transport=None):
        self.client = httpx.AsyncClient(
            transport=transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False),
            auth=None,
            trust_env=False,
            follow_redirects=False,
        )

    async def request(
        self,
        stage,
        *,
        timeout,
        credentials=None,
        token=None,
        query=None,
        identifier=None,
        search_options=None,
    ):
        headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
        if stage == "oauth":
            pair = ":".join(credentials).encode()
            headers["Authorization"] = "Basic " + base64.b64encode(pair).decode()
            method, path = "POST", "/identity/v1/oauth2/token"
            params = None
            data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
            limit = 32 * 1024
        elif stage in {"browse", "detail", "resolution"}:
            headers.update(Authorization="Bearer " + token, **{"X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})
            method, path, data = "GET", "/buy/browse/v1/item_summary/search", None
            params = {
                "q": query,
                "filter": "buyingOptions:{FIXED_PRICE|AUCTION},deliveryCountry:US,itemLocationCountry:US",
                "limit": 20,
                "offset": 0,
                "fieldgroups": "EXTENDED",
            }
            if stage == "browse":
                options = search_options or {}
                if not isinstance(options, dict):
                    raise ValueError("Choose supported provider search options")
                if "hunter" in options:
                    from .hunter_query import checked_params

                    if set(options) != {"hunter"} or query is not None:
                        raise ValueError("Hunter requires its separate checked request")
                    params = checked_params(options["hunter"])
                elif set(options) - {"sort"} or options.get("sort", "ending_soonest") not in {
                    "best_match",
                    "ending_soonest",
                }:
                    raise ValueError("Choose supported provider search options")
                elif options.get("sort", "ending_soonest") == "ending_soonest":
                    params["sort"] = "endingSoonest"
            if stage != "browse":
                from .listing_details import parse_identifier

                checked = parse_identifier(identifier)
                headers["X-EBAY-C-ENDUSERCTX"] = "contextualLocation=country%3DUS"
                if stage == "detail" and checked["rest"]:
                    path = "/buy/browse/v1/item/" + quote(checked["rest"], safe="")
                    params = {"quantity_for_shipping_estimate": "1"}
                elif stage == "resolution" and not checked["rest"]:
                    path = "/buy/browse/v1/item/get_item_by_legacy_id"
                    params = {"legacy_item_id": checked["legacy"], "quantity_for_shipping_estimate": "1"}
                    if checked["variation"] != "0":
                        params["legacy_variation_id"] = checked["variation"]
                else:
                    raise ValueError("Unsupported detail operation")
            limit = 2 * 1024 * 1024
        else:
            raise ValueError("Unsupported provider operation")
        wire = httpx.Request(
            method,
            "https://api.ebay.com" + path,
            headers=headers,
            params=params,
            data=data,
            extensions={"timeout": {key: timeout for key in ("connect", "read", "write", "pool")}},
        )
        try:
            response = await self.client.send(wire, stream=True, auth=None, follow_redirects=False)
            try:
                if response.status_code != 200:
                    raise ProviderFailure(stage, response.status_code)
                # Identity was requested. Reject unsolicited compressed bodies so
                # decompression cannot bypass the finite byte boundary.
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ProviderFailure(stage)
                raw = bytearray()
                async for block in response.aiter_raw():
                    if len(raw) + len(block) > limit:
                        raise ProviderFailure(stage)
                    raw.extend(block)
                try:
                    value = json.loads(raw)
                except (ValueError, UnicodeError):
                    raise ProviderFailure(stage) from None
                if not isinstance(value, dict) or value.get("errors"):
                    raise ProviderFailure(stage)
                if stage == "browse" and search_options and "hunter" in search_options:
                    rows = value.get("itemSummaries", [])
                    if (
                        not isinstance(rows, list)
                        or len(rows) > params["limit"]
                        or not all(isinstance(row, dict) for row in rows)
                    ):
                        raise ProviderFailure(stage)
                return value
            finally:
                await response.aclose()
        except httpx.TransportError:
            raise ProviderFailure(stage, uncertain=True) from None

    async def close(self):
        await self.client.aclose()
