"""Bound request bodies before Django spools them or dispatches a view."""

from django.conf import settings

from pokemon_hunter.security import BROWSER_HEADERS

from .security import local_ingress_allowed

BULK_BODY_LIMIT = 32_000_000  # JSON expansion of at most 2,000 independently validated manual rows.
SCAN_BODY_LIMIT = 16_100_000  # Two 8 MB photos plus multipart overhead.


class BoundedBodyApplication:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.application(scope, receive, send)

        if not getattr(settings, "STAGING", False):
            # Django's middleware runs after body spooling. Reject foreign and
            # ambiguous local requests here before reading any upload bytes.
            headers = [(key.lower(), value) for key, value in scope.get("headers", [])]
            hosts = [value.decode("latin-1") for key, value in headers if key == b"host"]
            origins = [value.decode("latin-1") for key, value in headers if key == b"origin"]
            peer = (scope.get("client") or (None,))[0]
            if (
                len(hosts) != 1
                or len(origins) > 1
                or not local_ingress_allowed(
                    hosts[0],
                    peer,
                    origins[0] if origins else None,
                    forwarded=any(
                        key == b"forwarded" or key.startswith(b"x-forwarded-") for key, _ in headers
                    ),
                )
            ):
                return await self.refuse(send, 403, b'{"error":"Local app is loopback-only"}')

        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        if settings.B3_ENABLED and scope["path"] == "/api/scans/" and scope["method"] == "POST":
            limit = SCAN_BODY_LIMIT

        if (
            getattr(settings, "B2_ENABLED", False)
            and scope["path"] in {"/api/bulk/save/", "/api/bulk/parse/"}
            and scope["method"] == "POST"
        ):
            limit = BULK_BODY_LIMIT

        if (
            getattr(settings, "B3_ENABLED", False)
            and scope["path"].startswith("/api/photo-batches/")
            and scope["path"].endswith(("/upload/", "/retake/"))
            and scope["method"] == "POST"
        ):
            limit = 8_100_000

        lengths = [value for key, value in scope.get("headers", []) if key.lower() == b"content-length"]
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit() or len(lengths[0]) > 20:
                return await self.refuse(send, 400, b'{"error":"Invalid request length"}')
            if int(lengths[0]) > limit:
                return await self.refuse(send, 413, b'{"error":"Request body exceeds its size limit"}')

        received = 0
        exceeded = False

        async def bounded_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    # Django closes its spool and aborts before middleware/views
                    # on disconnect. Never pass the oversized chunk to its spool.
                    return {"type": "http.disconnect"}
            return message

        await self.application(scope, bounded_receive, send)
        if exceeded:
            await self.refuse(send, 413, b'{"error":"Request body exceeds its size limit"}')

    @staticmethod
    async def refuse(send, status, body):
        headers = [(k.lower().encode("ascii"), v.encode("ascii")) for k, v in BROWSER_HEADERS.items()]
        headers.extend([(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())])
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


def get_asgi_application():
    from django.core.asgi import get_asgi_application as django_application

    application = django_application()
    if getattr(settings, "STAGING", False):
        # Preserve the separately qualified hosted serving/heartbeat contract.
        return BoundedBodyApplication(application)
    from .readiness import startup

    startup()
    from .serving import LimitedApplication

    return LimitedApplication(BoundedBodyApplication(application))
