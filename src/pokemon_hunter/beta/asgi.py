"""Bound request bodies before Django spools them or dispatches a view."""

from django.conf import settings

from pokemon_hunter.security import BROWSER_HEADERS

SCAN_BODY_LIMIT = 16_100_000  # Two 8 MB photos plus multipart overhead.


class BoundedBodyApplication:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.application(scope, receive, send)

        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        if settings.B3_ENABLED and scope["path"] == "/api/scans/" and scope["method"] == "POST":
            limit = SCAN_BODY_LIMIT

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

    return BoundedBodyApplication(django_application())
