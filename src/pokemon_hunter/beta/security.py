from django.http import HttpResponseForbidden


class LocalOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.META.get("HTTP_HOST") != "127.0.0.1:8011"
            or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
            or any(
                k in request.META
                for k in (
                    "HTTP_FORWARDED",
                    "HTTP_X_FORWARDED_HOST",
                    "HTTP_X_FORWARDED_FOR",
                    "HTTP_X_FORWARDED_PROTO",
                )
            )
        ):
            return HttpResponseForbidden("B1 is loopback-only")
        origin = request.headers.get("Origin")
        if origin and origin != "http://127.0.0.1:8011":
            return HttpResponseForbidden("Foreign origin")
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "same-origin"
        response["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'"
        )
        return response


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
        if not trusted or request.META.get("HTTP_X_FORWARDED_PROTO") != "https":
            return HttpResponseForbidden("Trusted HTTPS proxy required")
        if request.get_host() != settings.PUBLIC_ORIGIN.removeprefix("https://"):
            return HttpResponseForbidden("Unexpected host")
        if request.headers.get("Origin") not in (None, settings.PUBLIC_ORIGIN):
            return HttpResponseForbidden("Foreign origin")
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'"
        )
        return response


def profile_context(request):
    from django.conf import settings

    return {"staging": getattr(settings, "STAGING", False)}
