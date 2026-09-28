"""Explicit loopback-only configuration. Hosting requires a separately qualified configuration."""

import os
from datetime import timedelta
from pathlib import Path

ROOT = Path(os.environ["DEX_B1_ROOT"]).resolve(strict=True)
PROJECT = Path(__file__).resolve().parents[3]
if ROOT.is_relative_to(PROJECT) or not (ROOT / "B1_ISOLATED").is_file():
    raise RuntimeError("B1 requires an initialized isolated directory outside the checkout")
if ROOT.stat().st_mode & 0o077:
    raise RuntimeError("B1 directory must be owner-only (chmod 700)")
for name in ("inventory.db", "secret.key"):
    if (ROOT / name).is_symlink() or (ROOT / name).stat().st_mode & 0o077:
        raise RuntimeError("B1 files must be private regular files")
SECRET_KEY = (ROOT / "secret.key").read_text().strip()
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1"]
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "axes"]
MIDDLEWARE = [
    "pokemon_hunter.beta.security.LocalOnlyMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ROOT / "inventory.db",
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
    }
}
ROOT_URLCONF = "pokemon_hunter.beta.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [Path(__file__).parent / "templates"],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ACCESS_FAILURE_LOG = False
AXES_VERBOSE = False
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "dex_b1_session"
CSRF_COOKIE_NAME = "dex_b1_csrf"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# HTTP is permitted only on the fixed loopback listener, never hosted.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PASSWORD_RESET_TIMEOUT = 1800
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
B2_ENABLED = (ROOT / "B2_ISOLATED").is_file()
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_000_000 if B2_ENABLED else 16384
SECURE_REFERRER_POLICY = "same-origin"
# URLs can contain bearer setup links. No request/access logging in this isolated profile.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {name: {"handlers": ["null"], "propagate": False} for name in ("django", "axes")},
}
