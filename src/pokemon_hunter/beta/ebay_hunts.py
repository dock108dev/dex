"""Explicit local eBay searches; configuration and provider errors stay server-side."""

import os
from pathlib import Path

import yaml
from django.conf import settings

from pokemon_hunter import ebay
from pokemon_hunter.models import Settings

from .diagnostics import failure

MAX_QUERIES = 8
MAX_PAGES = 2
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
    path = configuration_root() / ".env"
    try:
        if path.is_file():
            for line in path.read_text().splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and key.strip() in ENV_KEYS:
                    values.setdefault(key.strip(), value.strip().strip("\"'"))
        path = configuration_root() / "config/settings.yaml"
        raw = yaml.safe_load(path.read_text()) if path.is_file() else {}
        if "EBAY_DELIVERY_POSTAL_CODE" in values:
            raw = {**raw, "delivery_postal_code": values["EBAY_DELIVERY_POSTAL_CODE"]}
        provider = Settings.model_validate(raw)
        provider.search.max_pages = min(provider.search.max_pages, MAX_PAGES)
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
        else "Add your eBay application credentials to the local .env or server environment, then reload this page.",
    }


def search(queries):
    provider, values = configuration()
    if not values.get("EBAY_CLIENT_ID") or not values.get("EBAY_CLIENT_SECRET"):
        raise LiveHuntError("Add your eBay application credentials to the local .env or server environment.")
    if not queries:
        return [], {"limited": False, "environment": provider.environment}
    client = None
    try:
        client = ebay.EbayClient(
            provider, credentials=(values["EBAY_CLIENT_ID"], values["EBAY_CLIENT_SECRET"]), extended=True
        )
        raw = ebay.discover(client, queries)
        if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
            raise ValueError("Invalid provider result")
        return raw, {
            "limited": bool(client.warnings),
            "environment": provider.environment,
        }
    except Exception as exc:
        failure("ebay_search_failed", exc)
        if isinstance(exc, ebay.EbayHTTPError):
            code = f" ({exc.code})" if exc.code else ""
            action = (
                "Verify the active application keyset and credentials for the selected environment."
                if exc.stage == "OAuth"
                else "Verify Browse API access for the application and selected environment."
            )
            raise LiveHuntError(
                f"eBay {exc.stage} returned HTTP {exc.status}{code}. {action} Retry explicitly after resolving it.",
                status=502,
            ) from None
        raise LiveHuntError(
            "eBay search could not complete. Check credentials, API access and connection, then retry explicitly.",
            status=502,
        ) from None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                failure("ebay_client_close_failed", exc)
