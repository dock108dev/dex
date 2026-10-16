"""Shared local eBay configuration and read-only availability; no acquisition."""

import os
from pathlib import Path

import yaml
from django.conf import settings

from pokemon_hunter import config

from .diagnostics import failure

ENV_KEYS = {"EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_DELIVERY_POSTAL_CODE"}


class LiveHuntError(Exception):
    def __init__(self, message, status=400):
        self.public_message = message
        self.status = status
        super().__init__(message)


def configuration_root():
    return Path(settings.PROJECT)


def configuration():
    """Reuse local eBay settings without importing unrelated watcher/provider secrets."""
    if getattr(settings, "STAGING", False):
        raise LiveHuntError("Live eBay search is available only in the local app.")
    values = {key: os.environ[key] for key in ENV_KEYS if os.environ.get(key)}
    root = configuration_root()
    try:
        for key, value in config.read_env(root / ".env", keys=ENV_KEYS).items():
            values.setdefault(key, value)
        provider = config.load_settings(root, environ=values, required=False)
    except (OSError, UnicodeError, ValueError, TypeError, yaml.YAMLError) as exc:
        failure("ebay_configuration_failed", exc)
        raise LiveHuntError("Check the local eBay settings before searching.") from None
    return provider, values


def status():
    if getattr(settings, "STAGING", False):
        return {
            "enabled": False,
            "configured": False,
            "environment": None,
            "note": "Live eBay search is available only in the local app.",
        }
    try:
        provider, values = configuration()
    except LiveHuntError as exc:
        return {"enabled": True, "configured": False, "environment": None, "note": exc.public_message}
    configured = bool(values.get("EBAY_CLIENT_ID") and values.get("EBAY_CLIENT_SECRET"))
    return {
        "enabled": True,
        "configured": configured,
        "environment": provider.environment,
        "note": "Live eBay searches run only when you request them. Results are snapshots, with seller-text evidence only."
        if configured
        else "Configure eBay credentials in the server environment or supported .env; restart after environment changes.",
    }
