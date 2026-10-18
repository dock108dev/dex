"""Content-free failure diagnostics; never format exception messages or locals."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

logger = logging.getLogger("dex.failures")


@contextmanager
def closing(resource, event):
    """Always close owned resources; preserve an active failure over cleanup errors."""
    try:
        yield resource
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            resource.close()
        except Exception as exc:
            failure(event, exc)
            if not failed:
                raise


@asynccontextmanager
async def async_closing(resource, event, *, close_method="close", timeout=0.5):
    """Bound cleanup; log failures without replacing an active error or cancellation."""
    try:
        yield resource
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            await asyncio.wait_for(getattr(resource, close_method)(), timeout=timeout)
        except Exception as exc:
            failure(event, exc)
            if not failed:
                raise


def failure(event, error):
    # Keep code locations for debugging without source lines, absolute paths,
    # exception text/chains, request objects, provider output or local variables.
    frames = []
    tb = error.__traceback__
    while tb is not None:
        code = tb.tb_frame.f_code
        frames.append(f"{Path(code.co_filename).name}:{tb.tb_lineno}:{code.co_name}")
        tb = tb.tb_next
    logger.error("%s type=%s frames=%s", event, type(error).__name__, " > ".join(frames))


class FailureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.core.exceptions import PermissionDenied, SuspiciousOperation
        from django.http import Http404

        if not isinstance(exception, (Http404, PermissionDenied, SuspiciousOperation)):
            failure("request_failed", exception)
        # Django retains its normal safe error response and status.
        return None
