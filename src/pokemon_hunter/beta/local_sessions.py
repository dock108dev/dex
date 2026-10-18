"""Bounded rolling local authentication; no provider or temporary-work authority."""

from django.conf import settings
from django.utils import timezone

RENEWAL_SECONDS = 3600
MARKER = "_dex_local_renewed_at"


class LocalSessionRenewalMiddleware:
    """Save at most hourly for ordinary authenticated reads, using Django expiry.

    Login/password changes retain Django's fixation/revocation behavior. Renewal
    changes only the existing session's expiry and internal timestamp. The hour
    bound avoids writing SQLite for every image/API read; idle expiry is between
    29 days 23 hours and 30 days after the last authenticated visit.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not settings.STAGING and response.status_code < 500 and request.user.is_authenticated:
            now = int(timezone.now().timestamp())
            previous = request.session.get(MARKER)
            if type(previous) is not int or previous > now or now - previous >= RENEWAL_SECONDS:
                request.session[MARKER] = now
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return response
