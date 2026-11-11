"""Grading is opt-in, including in standalone service consumers."""

import os

from django.conf import settings


def grading_enabled():
    # Some isolated service consumers have no Django settings at all.  If a
    # settings module is configured, let Django load it and surface its errors.
    if not settings.configured and not os.environ.get("DJANGO_SETTINGS_MODULE"):
        return False
    return getattr(settings, "GRADING_ENABLED", False)
