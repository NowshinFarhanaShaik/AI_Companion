from .settings import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-that-is-longer-than-32-bytes"
AI_PROVIDER = "fake"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
TUTOR_MIN_SIMILARITY = 0.2
AI_BACKOFF_BASE_SECONDS = 0
AI_MAX_RETRIES = 2
EVAL_SLEEP_SECONDS = 0
