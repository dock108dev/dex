"""Fail-closed HTTPS staging configuration, independent from loopback development."""

import os
from urllib.parse import unquote, urlsplit


def profile(env=None):
    """One runtime profile contract, checked before local initialization or serving."""
    env = os.environ if env is None else env
    value = env.get("DEX_PROFILE", "local")
    if not isinstance(value, str) or value not in {"local", "staging"}:
        raise RuntimeError("Unknown DEX_PROFILE; use local or staging")
    return value


def configuration(env=None):
    env = os.environ if env is None else env
    required = ("DATABASE_URL", "DEX_SECRET_KEY", "DEX_PUBLIC_ORIGIN")
    if any(not env.get(k) for k in required):
        raise RuntimeError("Staging requires DATABASE_URL, DEX_SECRET_KEY and DEX_PUBLIC_ORIGIN")
    origin = urlsplit(env["DEX_PUBLIC_ORIGIN"])
    if (
        origin.scheme != "https"
        or not origin.hostname
        or origin.path
        or origin.query
        or origin.fragment
        or origin.username
    ):
        raise RuntimeError("DEX_PUBLIC_ORIGIN must be an HTTPS origin without a path")
    if len(env["DEX_SECRET_KEY"]) < 50:
        raise RuntimeError("Staging secret must contain at least 50 characters")
    import ipaddress

    ingress = env.get("DEX_INGRESS", "proxy")
    networks = []
    if ingress == "render":
        if (
            env.get("RENDER") != "true"
            or not env.get("RENDER_SERVICE_ID")
            or env.get("RENDER_SERVICE_TYPE") not in {"web", "worker"}
        ):
            raise RuntimeError("Render ingress requires the provider service environment")
        if env["RENDER_SERVICE_TYPE"] == "web" and env.get("RENDER_EXTERNAL_HOSTNAME") != origin.hostname:
            raise RuntimeError("Qualification uses the exact Render service hostname")
        if env.get("DEX_PROXY_NETWORKS"):
            raise RuntimeError("Do not invent Render proxy CIDRs")
    elif ingress == "proxy":
        if not env.get("DEX_PROXY_NETWORKS"):
            raise RuntimeError("Proxy ingress requires DEX_PROXY_NETWORKS")
        networks = [ipaddress.ip_network(n.strip()) for n in env["DEX_PROXY_NETWORKS"].split(",")]
        if any(n.prefixlen == 0 for n in networks):
            raise RuntimeError("Trust only the verified proxy network, never every address")
    else:
        raise RuntimeError("Unknown ingress profile")
    url = urlsplit(env["DATABASE_URL"])
    if url.scheme not in ("postgres", "postgresql") or not url.hostname or not url.path.strip("/"):
        raise RuntimeError("A PostgreSQL database URL is required")
    sslmode = env.get("DEX_DATABASE_SSLMODE", "require")
    if sslmode not in ("require", "verify-full"):
        if not (sslmode == "disable" and url.hostname in ("127.0.0.1", "localhost")):
            raise RuntimeError("Database TLS can only be disabled on loopback")
    return {
        "SECRET_KEY": env["DEX_SECRET_KEY"],
        "ALLOWED_HOSTS": [origin.hostname],
        "PUBLIC_ORIGIN": env["DEX_PUBLIC_ORIGIN"],
        "PROXY_NETWORKS": networks,
        "INGRESS": ingress,
        "SECURE_REDIRECT_EXEMPT": [r"^healthz/$"] if ingress == "render" else [],
        "CSRF_TRUSTED_ORIGINS": [env["DEX_PUBLIC_ORIGIN"]],
        "SESSION_COOKIE_NAME": "__Host-dex_session",
        "CSRF_COOKIE_NAME": "__Host-dex_csrf",
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 3600,
        "DATABASES": {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": unquote(url.path[1:]),
                "HOST": url.hostname,
                "PORT": url.port or 5432,
                "USER": unquote(url.username or ""),
                "PASSWORD": unquote(url.password or ""),
                "CONN_MAX_AGE": 0,
                "OPTIONS": {"sslmode": sslmode, "connect_timeout": 10},
            }
        },
    }
