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
