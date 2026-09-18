import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me-before-deploying")
if not DEBUG and SECRET_KEY.startswith("dev-insecure"):
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = ["corsheaders", "ninja_jwt"]
LOCAL_APPS = [
    "common",
    "accounts",
    "workspace",
    "ai",
    "events",
    "materials",
    "tutor",
    "learning",
    "assessment",
    "insights",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default="postgres://localhost:5432/studycompanion",
        conn_max_age=60,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
 
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
 
if STORAGE_BACKEND == "s3":
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }
    AWS_ACCESS_KEY_ID = os.environ["S3_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = os.environ["S3_SECRET_ACCESS_KEY"]
    AWS_STORAGE_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
    AWS_S3_ENDPOINT_URL = os.environ["S3_ENDPOINT_URL"]
    AWS_S3_REGION_NAME = os.environ.get("S3_REGION_NAME", "us-west-004")
    AWS_S3_ADDRESSING_STYLE = "virtual"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }

# Postgres-backed, so rate-limit counters are shared by every web worker. Needs `manage.py createcachetable`.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 10000},
    }
}
# Requests per user (per client IP for sign-in and sign-up) on endpoints that spend AI quota or invite abuse.
NINJA_DEFAULT_THROTTLE_RATES = {
    "sign_in": "10/m",
    "sign_up": "10/h",
    "tutor": "10/m",
    "quiz": "30/m",
    "upload": "20/h",
}
# Proxies in front of the app that append to X-Forwarded-For; 0 trusts only the socket address.
NINJA_NUM_PROXIES = int(os.environ.get("NUM_PROXIES", "0"))

NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_PAGES = 200
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
OCR_MIN_CHARS = 50
MAX_OCR_PAGES = 30
MAX_CONCEPTS_PER_MATERIAL = 15

EMBEDDING_DIM = 768
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# The free tier allows about 500 requests a day on Flash-Lite and about 20 on Flash, so both tiers
# default to Flash-Lite. With a paid key, point AI_MODEL_STRONG at a larger model.
AI_MODELS = {
    "fast": os.environ.get("AI_MODEL_FAST", "gemini-3.5-flash-lite"),
    "strong": os.environ.get("AI_MODEL_STRONG", "gemini-3.5-flash-lite"),
    "embed": os.environ.get("AI_MODEL_EMBED", "gemini-embedding-001"),
}
AI_TIMEOUT_SECONDS = int(os.environ.get("AI_TIMEOUT_SECONDS", "30"))
AI_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", "3"))
AI_BACKOFF_BASE_SECONDS = float(os.environ.get("AI_BACKOFF_BASE_SECONDS", "2"))
AI_EMBED_BATCH_SIZE = 50
# USD per 1M tokens (input, output). Estimates only: the free tier charges nothing.
AI_PRICES = {
    "gemini-3.5-flash-lite": (0.10, 0.40),
    "gemini-embedding-001": (0.15, 0.0),
}
TUTOR_MIN_SIMILARITY = float(os.environ.get("TUTOR_MIN_SIMILARITY", "0.55"))
TUTOR_TOOLS_ENABLED = env_bool("TUTOR_TOOLS_ENABLED", True)

# Minimum metric values for `manage.py run_evals`; a suite below any of them fails the run.
EVAL_THRESHOLDS = {
    "recall_at_6": 0.75,
    "answer_rate": 0.75,
    "citation_hit_rate": 0.7,
    "refusal_accuracy": 0.8,
    "grading_agreement": 0.6,
    "schema_validity": 0.9,
    "recommendation_rules": 1.0,
}
EVAL_SLEEP_SECONDS = float(os.environ.get("EVAL_SLEEP_SECONDS", "4"))
EVAL_QUIZ_GENERATIONS = int(os.environ.get("EVAL_QUIZ_GENERATIONS", "5"))

JOB_BACKOFF_BASE_SECONDS = 30
JOB_STUCK_AFTER_SECONDS = 600
JOB_POLL_SECONDS = 2

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    # Both libraries log every request; google_genai also warns about a feature this project never uses.
    "loggers": {"httpx": {"level": "WARNING"}, "google_genai": {"level": "ERROR"}},
}

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.0, send_default_pii=False)
