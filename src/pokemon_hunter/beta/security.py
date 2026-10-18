from django.http import HttpResponseForbidden

from pokemon_hunter.security import BROWSER_HEADERS


def local_ingress_allowed(host, peer, origin, *, forwarded=False):
    """Shared local boundary, also checked by ASGI before Django buffers a body."""
    return (
        host == "127.0.0.1:8011"
        and peer in {"127.0.0.1", "::1"}
        and origin in (None, "http://127.0.0.1:8011")
        and not forwarded
    )


def secure_response(response):
    private_cache = "private" in {
        value.strip().lower() for value in response.get("Cache-Control", "").split(",")
    }
    for key, value in BROWSER_HEADERS.items():
        response[key] = value
    if private_cache:
        response["Cache-Control"] = "private, no-store"
    if getattr(response, "_dex_owned_artwork", False):
        response["Content-Security-Policy"] += (
            "; img-src 'self' https://assets.tcgdex.net https://raw.githubusercontent.com"
        )
    return response


def forbidden(message):
    return secure_response(HttpResponseForbidden(message))


class LocalOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not local_ingress_allowed(
            request.META.get("HTTP_HOST"),
            request.META.get("REMOTE_ADDR"),
            request.headers.get("Origin"),
            forwarded=any(k == "HTTP_FORWARDED" or k.startswith("HTTP_X_FORWARDED_") for k in request.META),
        ):
            return forbidden("Local app is loopback-only")
        response = self.get_response(request)
        return secure_response(response)


class StagingMiddleware:
    """Only an explicitly trusted TLS-terminating proxy may reach staging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import ipaddress

        from django.conf import settings

        try:
            peer = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
            trusted = any(peer in network for network in settings.PROXY_NETWORKS)
        except ValueError:
            trusted = False
        render = getattr(settings, "INGRESS", "proxy") == "render"
        health = render and request.path == "/healthz/" and request.method in {"GET", "HEAD"}
        if not health and (not (trusted or render) or request.META.get("HTTP_X_FORWARDED_PROTO") != "https"):
            return forbidden("Trusted HTTPS proxy required")
        if request.get_host() != settings.PUBLIC_ORIGIN.removeprefix("https://"):
            return forbidden("Unexpected host")
        if request.headers.get("Origin") not in (None, settings.PUBLIC_ORIGIN):
            return forbidden("Foreign origin")
        response = self.get_response(request)
        return secure_response(response)


def profile_context(request):
    from django.conf import settings

    return {
        "staging": getattr(settings, "STAGING", False),
        "parity": settings.PARITY_ENABLED,
        "collection_enabled": settings.B2_ENABLED,
        "scans": settings.B3_ENABLED,
        "expansion": settings.B4_ENABLED,
    }
