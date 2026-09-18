# Phase 1 — Foundation (Tasks 1–5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running Django API and React app where a user can register, sign in, and create Spaces and Projects that no other user can see.

**Spec:** `docs/superpowers/specs/2026-09-17-ai-study-companion-design.md`
**Contract:** `00-overview.md` (sections C1, C2, C3, C7, C8)
**Depends on:** nothing.

---

### Task 1: Backend scaffold

**Files:**
- Create: `backend/requirements.txt`, `backend/pytest.ini`, `backend/manage.py`, `backend/config/{__init__,settings,settings_test,urls,api,wsgi,asgi}.py`
- Create: `backend/common/{__init__,apps,models,scoping,errors}.py`, `backend/common/tests/{__init__,test_health}.py`
- Create: `.env.example`, `.env`

**Interfaces:**
- Produces: `common.models.BaseModel`, `common.scoping.OwnedQuerySet`, `common.scoping.get_owned_or_404`, `common.errors.ServiceError`, `config.api.api`, `GET /api/health`, settings names `LOCAL_APPS`, `EMBEDDING_DIM`, `AI_PROVIDER`, `AI_MODELS`, `TUTOR_MIN_SIMILARITY`, `TUTOR_TOOLS_ENABLED`.

- [ ] **Step 1: Create the database**

```bash
createdb studycompanion
psql -d studycompanion -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -d studycompanion -Atc "SELECT extversion FROM pg_extension WHERE extname='vector';"
```
Expected: a version number such as `0.8.0`.

- [ ] **Step 2: Create the virtual environment and install dependencies**

`backend/requirements.txt`:
```
Django>=5.1,<5.3
django-ninja>=1.3,<2
django-ninja-jwt>=5.3,<6
psycopg[binary]>=3.2,<4
pgvector>=0.3,<1
dj-database-url>=2.2,<3
django-cors-headers>=4.4,<5
python-dotenv>=1.0,<2
pymupdf>=1.24,<2
google-genai>=1.0
pydantic>=2.7,<3
django-storages[s3]>=1.14,<2
gunicorn>=22
whitenoise>=6.7,<7
sentry-sdk>=2.0
pytest>=8
pytest-django>=4.8
```

```bash
mkdir -p backend && cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
django-admin startproject config .
python manage.py startapp common
rm common/tests.py common/views.py common/admin.py && mkdir common/tests && touch common/tests/__init__.py
```

- [ ] **Step 3: Write the failing test**

`backend/pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings_test
python_files = test_*.py
addopts = -ra --strict-markers
```

`backend/common/tests/test_health.py`:
```python
from django.test import Client


def test_health_endpoint_is_public():
    response = Client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_route_returns_json_404():
    response = Client().get("/api/does-not-exist")
    assert response.status_code == 404
```

- [ ] **Step 4: Run it to see it fail**

Run: `pytest common/tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config.settings_test'`.

- [ ] **Step 5: Write settings**

Replace `backend/config/settings.py`:
```python
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
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
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
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# Uploads
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_PAGES = 200
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024

# AI
EMBEDDING_DIM = 768
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# The free tier allows about 500 requests a day on Flash-Lite and about 20 on Flash, so both tiers
# default to Flash-Lite. With a paid key, point AI_MODEL_STRONG at a larger model.
AI_MODELS = {
    "fast": os.environ.get("AI_MODEL_FAST", "gemini-3.1-flash-lite"),
    "strong": os.environ.get("AI_MODEL_STRONG", "gemini-3.1-flash-lite"),
    "embed": os.environ.get("AI_MODEL_EMBED", "gemini-embedding-001"),
}
AI_TIMEOUT_SECONDS = int(os.environ.get("AI_TIMEOUT_SECONDS", "30"))
AI_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", "3"))
TUTOR_MIN_SIMILARITY = float(os.environ.get("TUTOR_MIN_SIMILARITY", "0.55"))
TUTOR_TOOLS_ENABLED = env_bool("TUTOR_TOOLS_ENABLED", True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.0, send_default_pii=False)
```

`backend/config/settings_test.py`:
```python
from .settings import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key"
AI_PROVIDER = "fake"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
TUTOR_MIN_SIMILARITY = 0.2
```

- [ ] **Step 6: Write the common module**

`backend/common/apps.py`:
```python
from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "common"
```

`backend/common/models.py`:
```python
import uuid

from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

`backend/common/scoping.py`:
```python
from django.db import models
from django.http import Http404


class OwnedQuerySet(models.QuerySet):
    """Every owned model declares OWNER_PATH, the lookup from the model to its owning user."""

    def for_user(self, user):
        return self.filter(**{self.model.OWNER_PATH: user})


def get_owned_or_404(model, user, **lookup):
    """Load an object the user owns. A missing object and someone else's object look the same: 404."""
    try:
        return model.objects.for_user(user).get(**lookup)
    except (model.DoesNotExist, ValueError):
        raise Http404(f"{model.__name__} not found")
```

`backend/common/errors.py`:
```python
class ServiceError(Exception):
    """A business-rule failure that should reach the client as a clean JSON error."""

    def __init__(self, message: str, *, status: int = 400, code: str = "error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
```

- [ ] **Step 7: Write the API root and URLs**

`backend/config/api.py`:
```python
from django.http import Http404
from ninja import NinjaAPI

from common.errors import ServiceError

api = NinjaAPI(title="AI Study Companion", version="0.1.0")


@api.exception_handler(ServiceError)
def handle_service_error(request, exc: ServiceError):
    return api.create_response(request, {"detail": exc.message, "code": exc.code}, status=exc.status)


@api.exception_handler(Http404)
def handle_not_found(request, exc: Http404):
    return api.create_response(request, {"detail": "Not found", "code": "not_found"}, status=404)


@api.get("/health", auth=None, tags=["system"])
def health(request):
    return {"status": "ok"}
```

`backend/config/urls.py`:
```python
from django.contrib import admin
from django.urls import path

from config.api import api

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", api.urls),
]
```

- [ ] **Step 8: Write the environment files**

`.env.example` (repository root):
```
# Django
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=change-me
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
DATABASE_URL=postgres://localhost:5432/studycompanion

# AI
AI_PROVIDER=gemini
GEMINI_API_KEY=
AI_MODEL_FAST=gemini-3.1-flash-lite
AI_MODEL_STRONG=gemini-3.1-flash-lite
AI_MODEL_EMBED=gemini-embedding-001
TUTOR_MIN_SIMILARITY=0.55

# Storage (production only)
STORAGE_BACKEND=local
S3_ENDPOINT_URL=
S3_BUCKET=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_REGION=

# Optional
SENTRY_DSN=
```

```bash
cd .. && cp .env.example .env && git check-ignore .env && cd backend
```
Expected: prints `.env`, which confirms it is ignored. Put the real `GEMINI_API_KEY` in `.env` now.

- [ ] **Step 9: Run the tests**

Run: `pytest common/tests/test_health.py -v`
Expected: 2 passed.

- [ ] **Step 10: Commit**

```bash
cd .. && git add .env.example backend && git commit -m "chore: scaffold Django API with settings, common module and health endpoint

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Accounts and JWT authentication

**Files:**
- Create: `backend/accounts/{models,auth,schemas,api,admin,apps}.py`, `backend/accounts/tests/{__init__,test_auth}.py`
- Create: `backend/conftest.py`, `backend/common/testing.py`
- Modify: `backend/config/settings.py` (`LOCAL_APPS`, `AUTH_USER_MODEL`), `backend/config/api.py` (default auth, router)

**Interfaces:**
- Produces: `accounts.models.User`; `accounts.auth.JWTAuth`, `accounts.auth.StaffJWTAuth`; endpoints `POST /api/auth/register`, `POST /api/auth/token`, `POST /api/auth/token/refresh`, `GET /api/auth/me`; fixtures `user`, `other_user`, `admin_user`, `api`; `common.testing.ApiClient`.

> The custom user model must exist before the first `migrate`. Do not run `migrate` before this task.

- [ ] **Step 1: Create the app**

```bash
cd backend && python manage.py startapp accounts
rm accounts/tests.py accounts/views.py && mkdir accounts/tests && touch accounts/tests/__init__.py
```

In `config/settings.py` set:
```python
LOCAL_APPS = [
    "common",
    "accounts",
]
```
and add below `DEFAULT_AUTO_FIELD`:
```python
AUTH_USER_MODEL = "accounts.User"
```

- [ ] **Step 2: Write the test client and fixtures**

`backend/common/testing.py`:
```python
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from ninja_jwt.tokens import RefreshToken


class ApiClient:
    """django.test.Client with a Bearer token and JSON bodies. Paths may omit the /api prefix."""

    def __init__(self, user=None):
        self.client = Client()
        self.headers = {}
        if user is not None:
            access = RefreshToken.for_user(user).access_token
            self.headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}

    @staticmethod
    def _url(path: str) -> str:
        return path if path.startswith("/api/") else f"/api{path}"

    def get(self, path, **params):
        return self.client.get(self._url(path), params, **self.headers)

    def post(self, path, data=None):
        return self.client.post(
            self._url(path), data=json.dumps(data or {}), content_type="application/json", **self.headers
        )

    def patch(self, path, data=None):
        return self.client.patch(
            self._url(path), data=json.dumps(data or {}), content_type="application/json", **self.headers
        )

    def delete(self, path):
        return self.client.delete(self._url(path), **self.headers)

    def upload(self, path, field, filename, content: bytes, content_type="application/pdf"):
        upload = SimpleUploadedFile(filename, content, content_type=content_type)
        return self.client.post(self._url(path), {field: upload}, **self.headers)
```

`backend/conftest.py`:
```python
import pytest

from common.testing import ApiClient

PASSWORD = "pass12345"


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(email="ada@example.com", password=PASSWORD, name="Ada")


@pytest.fixture
def other_user(db, django_user_model):
    return django_user_model.objects.create_user(email="bob@example.com", password=PASSWORD, name="Bob")


@pytest.fixture
def admin_user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="admin@example.com", password=PASSWORD, name="Admin", is_staff=True
    )


@pytest.fixture
def api():
    def make(user=None) -> ApiClient:
        return ApiClient(user)

    return make
```

- [ ] **Step 3: Write the failing tests**

`backend/accounts/tests/test_auth.py`:
```python
import pytest

pytestmark = pytest.mark.django_db


def test_register_creates_user_and_returns_tokens(api):
    response = api().post("/auth/register", {"name": "Ada", "email": "Ada@Example.com", "password": "pass12345"})
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["is_staff"] is False
    assert body["access"] and body["refresh"]


def test_register_rejects_duplicate_email(api, user):
    response = api().post("/auth/register", {"name": "X", "email": user.email, "password": "pass12345"})
    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


def test_register_rejects_short_password(api):
    response = api().post("/auth/register", {"name": "X", "email": "x@example.com", "password": "short"})
    assert response.status_code == 400
    assert response.json()["code"] == "weak_password"


def test_register_rejects_invalid_email(api):
    response = api().post("/auth/register", {"name": "X", "email": "not-an-email", "password": "pass12345"})
    assert response.status_code == 422


def test_login_returns_tokens(api, user):
    response = api().post("/auth/token", {"email": "ADA@example.com", "password": "pass12345"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)


def test_login_with_wrong_password_is_401(api, user):
    response = api().post("/auth/token", {"email": user.email, "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_refresh_returns_new_access_token(api, user):
    tokens = api().post("/auth/token", {"email": user.email, "password": "pass12345"}).json()
    response = api().post("/auth/token/refresh", {"refresh": tokens["refresh"]})
    assert response.status_code == 200
    assert response.json()["access"]


def test_refresh_with_garbage_token_is_401(api):
    response = api().post("/auth/token/refresh", {"refresh": "garbage"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_refresh"


def test_me_requires_a_token(api):
    assert api().get("/auth/me").status_code == 401


def test_me_returns_the_current_user(api, user):
    response = api(user).get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_inactive_user_cannot_use_a_token(api, user):
    client = api(user)
    user.is_active = False
    user.save()
    assert client.get("/auth/me").status_code == 401
```

- [ ] **Step 4: Run them to see them fail**

Run: `pytest accounts/tests/test_auth.py -v`
Expected: errors — `AUTH_USER_MODEL refers to model 'accounts.User' that has not been installed`.

- [ ] **Step 5: Write the user model**

`backend/accounts/models.py`:
```python
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]      # createsuperuser asks for email, name and password

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email
```

`backend/accounts/admin.py`:
```python
from django.contrib import admin

from accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "is_staff", "is_active", "created_at")
    search_fields = ("email", "name")
    exclude = ("password",)
```

- [ ] **Step 6: Write auth classes, schemas and endpoints**

`backend/accounts/auth.py`:
```python
from ninja_jwt.authentication import JWTAuth as _JWTAuth


class JWTAuth(_JWTAuth):
    """Bearer-token auth. After it succeeds, request.auth is the User."""


class StaffJWTAuth(_JWTAuth):
    """Same as JWTAuth, but only staff users pass. Everyone else gets 401."""

    def authenticate(self, request, token):
        user = super().authenticate(request, token)
        if user is not None and user.is_staff:
            return user
        return None
```

`backend/accounts/schemas.py`:
```python
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from ninja import Schema
from pydantic import Field, field_validator


class RegisterIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        value = value.strip().lower()
        try:
            validate_email(value)
        except ValidationError:
            raise ValueError("Enter a valid email address.")
        return value


class LoginIn(Schema):
    email: str
    password: str


class RefreshIn(Schema):
    refresh: str


class UserOut(Schema):
    id: UUID
    email: str
    name: str
    is_staff: bool


class AuthOut(Schema):
    access: str
    refresh: str
    user: UserOut


class AccessOut(Schema):
    access: str
```

`backend/accounts/api.py`:
```python
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from ninja import Router
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken

from accounts.models import User
from accounts.schemas import AccessOut, AuthOut, LoginIn, RefreshIn, RegisterIn, UserOut
from common.errors import ServiceError

router = Router(tags=["auth"])


def _auth_payload(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": user}


@router.post("/auth/register", auth=None, response={201: AuthOut})
def register(request, data: RegisterIn):
    if User.objects.filter(email=data.email).exists():
        raise ServiceError("An account with this email already exists.", status=409, code="email_taken")
    try:
        validate_password(data.password)
    except ValidationError as exc:
        raise ServiceError(" ".join(exc.messages), status=400, code="weak_password")
    user = User.objects.create_user(email=data.email, password=data.password, name=data.name.strip())
    return 201, _auth_payload(user)


@router.post("/auth/token", auth=None, response=AuthOut)
def login(request, data: LoginIn):
    user = authenticate(request, username=data.email.strip().lower(), password=data.password)
    if user is None:
        raise ServiceError("Email or password is incorrect.", status=401, code="invalid_credentials")
    return _auth_payload(user)


@router.post("/auth/token/refresh", auth=None, response=AccessOut)
def refresh_token(request, data: RefreshIn):
    try:
        token = RefreshToken(data.refresh)
    except TokenError:
        raise ServiceError("Your session has expired. Please sign in again.", status=401, code="invalid_refresh")
    return {"access": str(token.access_token)}


@router.get("/auth/me", response=UserOut)
def me(request):
    return request.auth
```

In `backend/config/api.py`, change the `NinjaAPI(...)` line and mount the router:
```python
from accounts.auth import JWTAuth

api = NinjaAPI(title="AI Study Companion", version="0.1.0", auth=JWTAuth())
```
and at the bottom of the file:
```python
from accounts.api import router as accounts_router  # noqa: E402

api.add_router("", accounts_router)
```

- [ ] **Step 7: Migrate and run the tests**

```bash
python manage.py makemigrations accounts && python manage.py migrate
pytest accounts/tests/test_auth.py common/tests -v
```
Expected: 13 passed. If `ninja_jwt` imports fail, check the django-ninja-jwt documentation with context7 for the installed version and adjust the import paths only.

- [ ] **Step 8: Commit**

```bash
cd .. && git add backend && git commit -m "feat: add email-based accounts with JWT register, login, refresh and me

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Spaces and Projects with isolation

**Files:**
- Create: `backend/workspace/{models,schemas,services,api,admin}.py`, `backend/workspace/tests/{__init__,test_spaces,test_projects,test_isolation}.py`
- Modify: `backend/config/settings.py` (`LOCAL_APPS`), `backend/config/api.py` (router), `backend/conftest.py` (fixtures)

**Interfaces:**
- Consumes: `BaseModel`, `OwnedQuerySet`, `get_owned_or_404`, `ServiceError`, `request.auth`.
- Produces: `workspace.models.Space`, `workspace.models.Project`; `workspace.services.create_space`, `create_project`, `touch_project`; fixtures `space`, `project`, `other_space`, `other_project`; the Space and Project endpoints in spec section 11 (dashboards come in Phase 5).

- [ ] **Step 1: Create the app**

```bash
cd backend && python manage.py startapp workspace
rm workspace/tests.py workspace/views.py && mkdir workspace/tests && touch workspace/tests/__init__.py
```
Add `"workspace",` to `LOCAL_APPS`.

- [ ] **Step 2: Add fixtures**

Append to `backend/conftest.py`:
```python
@pytest.fixture
def space(user):
    from workspace.services import create_space

    return create_space(user=user, name="Biology", description="Cell biology revision")


@pytest.fixture
def project(user, space):
    from workspace.services import create_project

    return create_project(
        user=user, space=space, name="Photosynthesis", description="Unit 4", learning_goal="Pass the unit test"
    )


@pytest.fixture
def other_space(other_user):
    from workspace.services import create_space

    return create_space(user=other_user, name="History", description="Modern history")


@pytest.fixture
def other_project(other_user, other_space):
    from workspace.services import create_project

    return create_project(
        user=other_user, space=other_space, name="Cold War", description="Unit 2", learning_goal="Essay practice"
    )
```

- [ ] **Step 3: Write the failing tests**

`backend/workspace/tests/test_spaces.py`:
```python
import pytest

pytestmark = pytest.mark.django_db


def test_create_space(api, user):
    response = api(user).post("/spaces", {"name": "Biology", "description": "Cells", "color": "#16a34a"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Biology"
    assert body["project_count"] == 0


def test_space_requires_name_and_description(api, user):
    assert api(user).post("/spaces", {"name": "", "description": "x"}).status_code == 422
    assert api(user).post("/spaces", {"name": "x", "description": ""}).status_code == 422


def test_list_spaces_is_paginated_and_counts_projects(api, user, space, project):
    body = api(user).get("/spaces").json()
    assert body["count"] == 1
    assert body["items"][0]["id"] == str(space.id)
    assert body["items"][0]["project_count"] == 1


def test_update_and_delete_space(api, user, space):
    client = api(user)
    assert client.patch(f"/spaces/{space.id}", {"name": "Bio"}).json()["name"] == "Bio"
    assert client.delete(f"/spaces/{space.id}").status_code == 204
    assert client.get(f"/spaces/{space.id}").status_code == 404
```

`backend/workspace/tests/test_projects.py`:
```python
import pytest

pytestmark = pytest.mark.django_db


def test_create_project_in_space(api, user, space):
    response = api(user).post(
        f"/spaces/{space.id}/projects",
        {"name": "Photosynthesis", "description": "Unit 4", "learning_goal": "Pass the test"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["space_id"] == str(space.id)
    assert body["space_name"] == "Biology"
    assert body["learning_goal"] == "Pass the test"


def test_project_requires_learning_goal(api, user, space):
    response = api(user).post(f"/spaces/{space.id}/projects", {"name": "P", "description": "d", "learning_goal": ""})
    assert response.status_code == 422


def test_list_projects_in_space(api, user, space, project):
    body = api(user).get(f"/spaces/{space.id}/projects").json()
    assert [item["id"] for item in body["items"]] == [str(project.id)]


def test_get_update_delete_project(api, user, project):
    client = api(user)
    assert client.get(f"/projects/{project.id}").json()["name"] == "Photosynthesis"
    assert client.patch(f"/projects/{project.id}", {"learning_goal": "Ace it"}).json()["learning_goal"] == "Ace it"
    assert client.delete(f"/projects/{project.id}").status_code == 204
    assert client.get(f"/projects/{project.id}").status_code == 404


def test_touch_project_sets_last_activity(project):
    from workspace.services import touch_project

    assert project.last_activity_at is None
    touch_project(project)
    project.refresh_from_db()
    assert project.last_activity_at is not None
```

`backend/workspace/tests/test_isolation.py`:
```python
import uuid

import pytest

from workspace.models import Project, Space

pytestmark = pytest.mark.django_db


def test_for_user_only_returns_owned_rows(user, space, project, other_space, other_project):
    assert list(Space.objects.for_user(user)) == [space]
    assert list(Project.objects.for_user(user)) == [project]


def test_lists_never_include_another_users_data(api, user, space, other_space, other_project):
    items = api(user).get("/spaces").json()["items"]
    assert [item["id"] for item in items] == [str(space.id)]


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_another_users_space_is_404(api, user, other_space, method):
    client = api(user)
    call = getattr(client, method)
    response = call(f"/spaces/{other_space.id}", {"name": "hacked"}) if method == "patch" else call(f"/spaces/{other_space.id}")
    assert response.status_code == 404
    other_space.refresh_from_db()
    assert other_space.name == "History"


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_another_users_project_is_404(api, user, other_project, method):
    client = api(user)
    call = getattr(client, method)
    response = call(f"/projects/{other_project.id}", {"name": "hacked"}) if method == "patch" else call(f"/projects/{other_project.id}")
    assert response.status_code == 404
    assert Project.objects.filter(id=other_project.id, name="Cold War").exists()


def test_cannot_create_project_in_another_users_space(api, user, other_space):
    response = api(user).post(
        f"/spaces/{other_space.id}/projects", {"name": "X", "description": "d", "learning_goal": "g"}
    )
    assert response.status_code == 404
    assert other_space.projects.count() == 0


def test_cannot_list_projects_of_another_users_space(api, user, other_space):
    assert api(user).get(f"/spaces/{other_space.id}/projects").status_code == 404


def test_unknown_id_and_foreign_id_look_the_same(api, user, other_project):
    unknown = api(user).get(f"/projects/{uuid.uuid4()}")
    foreign = api(user).get(f"/projects/{other_project.id}")
    assert unknown.status_code == foreign.status_code == 404
    assert unknown.json() == foreign.json()


def test_endpoints_require_authentication(api, space):
    assert api().get("/spaces").status_code == 401
    assert api().get(f"/spaces/{space.id}").status_code == 401
```

- [ ] **Step 4: Run them to see them fail**

Run: `pytest workspace -v`
Expected: errors — `ModuleNotFoundError: No module named 'workspace.services'`.

- [ ] **Step 5: Write models and services**

`backend/workspace/models.py`:
```python
from django.conf import settings
from django.db import models

from common.models import BaseModel
from common.scoping import OwnedQuerySet


class Space(BaseModel):
    OWNER_PATH = "owner"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="spaces")
    name = models.CharField(max_length=120)
    description = models.TextField()
    color = models.CharField(max_length=16, blank=True, default="")
    icon = models.CharField(max_length=8, blank=True, default="")

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Project(BaseModel):
    OWNER_PATH = "owner"

    space = models.ForeignKey(Space, on_delete=models.CASCADE, related_name="projects")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=160)
    description = models.TextField()
    learning_goal = models.TextField()
    last_activity_at = models.DateTimeField(null=True, blank=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "-last_activity_at"])]

    def __str__(self) -> str:
        return self.name
```

`backend/workspace/services.py`:
```python
from django.utils import timezone

from common.errors import ServiceError
from workspace.models import Project, Space


def create_space(*, user, name, description="", color="", icon="") -> Space:
    return Space.objects.create(
        owner=user, name=name.strip(), description=description.strip(), color=color, icon=icon
    )


def create_project(*, user, space, name, description="", learning_goal="") -> Project:
    if space.owner_id != user.id:
        raise ServiceError("Space not found", status=404, code="not_found")
    return Project.objects.create(
        space=space,
        owner=user,
        name=name.strip(),
        description=description.strip(),
        learning_goal=learning_goal.strip(),
    )


def touch_project(project) -> None:
    Project.objects.filter(id=project.id).update(last_activity_at=timezone.now())
```

`backend/workspace/admin.py`:
```python
from django.contrib import admin

from workspace.models import Project, Space

admin.site.register(Space)
admin.site.register(Project)
```

- [ ] **Step 6: Write schemas and endpoints**

`backend/workspace/schemas.py`:
```python
from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import Field


class SpaceIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    color: str = Field(default="", max_length=16)
    icon: str = Field(default="", max_length=8)


class SpacePatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=8)


class SpaceOut(Schema):
    id: UUID
    name: str
    description: str
    color: str
    icon: str
    project_count: int = 0
    created_at: datetime


class ProjectIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    learning_goal: str = Field(min_length=1, max_length=2000)


class ProjectPatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    learning_goal: str | None = Field(default=None, min_length=1, max_length=2000)


class ProjectOut(Schema):
    id: UUID
    space_id: UUID
    space_name: str
    name: str
    description: str
    learning_goal: str
    last_activity_at: datetime | None
    created_at: datetime

    @staticmethod
    def resolve_space_name(obj) -> str:
        return obj.space.name
```

`backend/workspace/api.py`:
```python
from uuid import UUID

from django.db.models import Count
from ninja import Router
from ninja.pagination import paginate

from common.scoping import get_owned_or_404
from workspace import services
from workspace.models import Project, Space
from workspace.schemas import ProjectIn, ProjectOut, ProjectPatch, SpaceIn, SpaceOut, SpacePatch

router = Router(tags=["workspace"])


def _spaces(user):
    return Space.objects.for_user(user).annotate(project_count=Count("projects"))


@router.get("/spaces", response=list[SpaceOut])
@paginate
def list_spaces(request):
    return _spaces(request.auth)


@router.post("/spaces", response={201: SpaceOut})
def create_space(request, data: SpaceIn):
    space = services.create_space(user=request.auth, **data.dict())
    return 201, _spaces(request.auth).get(id=space.id)


@router.get("/spaces/{uuid:space_id}", response=SpaceOut)
def get_space(request, space_id: UUID):
    get_owned_or_404(Space, request.auth, id=space_id)
    return _spaces(request.auth).get(id=space_id)


@router.patch("/spaces/{uuid:space_id}", response=SpaceOut)
def update_space(request, space_id: UUID, data: SpacePatch):
    space = get_owned_or_404(Space, request.auth, id=space_id)
    for field, value in data.dict(exclude_unset=True).items():
        if value is not None:
            setattr(space, field, value)
    space.save()
    return _spaces(request.auth).get(id=space_id)


@router.delete("/spaces/{uuid:space_id}", response={204: None})
def delete_space(request, space_id: UUID):
    get_owned_or_404(Space, request.auth, id=space_id).delete()
    return 204, None


@router.get("/spaces/{uuid:space_id}/projects", response=list[ProjectOut])
@paginate
def list_projects(request, space_id: UUID):
    space = get_owned_or_404(Space, request.auth, id=space_id)
    return Project.objects.for_user(request.auth).filter(space=space).select_related("space")


@router.post("/spaces/{uuid:space_id}/projects", response={201: ProjectOut})
def create_project(request, space_id: UUID, data: ProjectIn):
    space = get_owned_or_404(Space, request.auth, id=space_id)
    return 201, services.create_project(user=request.auth, space=space, **data.dict())


@router.get("/projects/{uuid:project_id}", response=ProjectOut)
def get_project(request, project_id: UUID):
    return get_owned_or_404(Project, request.auth, id=project_id)


@router.patch("/projects/{uuid:project_id}", response=ProjectOut)
def update_project(request, project_id: UUID, data: ProjectPatch):
    project = get_owned_or_404(Project, request.auth, id=project_id)
    for field, value in data.dict(exclude_unset=True).items():
        if value is not None:
            setattr(project, field, value)
    project.save()
    return project


@router.delete("/projects/{uuid:project_id}", response={204: None})
def delete_project(request, project_id: UUID):
    get_owned_or_404(Project, request.auth, id=project_id).delete()
    return 204, None
```

Mount it at the bottom of `backend/config/api.py`:
```python
from workspace.api import router as workspace_router  # noqa: E402

api.add_router("", workspace_router)
```

- [ ] **Step 7: Migrate and run the tests**

```bash
python manage.py makemigrations workspace && python manage.py migrate
pytest -q
```
Expected: all tests pass (13 from before plus 21 new).

- [ ] **Step 8: Commit**

```bash
cd .. && git add backend && git commit -m "feat: add Spaces and Projects with owner-scoped queries and isolation tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Frontend scaffold, API client and authentication

**Files:**
- Create: `frontend/` (Vite React TypeScript app), `frontend/.env.example`
- Create: `frontend/src/api/{client,types,auth}.ts`, `frontend/src/auth/{AuthProvider,RequireAuth,RequireAdmin}.tsx`
- Create: `frontend/src/components/ui/{Button,Card,Input,Textarea,Badge,Spinner}.tsx`, `frontend/src/components/shared/{PageHeader,EmptyState,ErrorState,StatusBadge,MasteryBar}.tsx`, `frontend/src/components/layout/{AppLayout,nav}.tsx`
- Create: `frontend/src/features/auth/{LoginPage,RegisterPage}.tsx`, `frontend/src/routes.tsx`
- Modify: `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/vite.config.ts`

**Interfaces:**
- Consumes: the auth endpoints from Task 2.
- Produces: everything in contract section C8 except `projectTabs` and `useProjectId` (Task 5).

- [ ] **Step 1: Scaffold**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install react-router-dom @tanstack/react-query
npm install -D tailwindcss @tailwindcss/vite
rm -f src/App.tsx src/App.css src/assets/react.svg
```
If `create vite` asks extra questions, decline the optional extras and do not start the dev server.

`frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
});
```

`frontend/src/index.css`:
```css
@import "tailwindcss";

body {
  @apply bg-slate-50 text-slate-900 antialiased;
}
```

`frontend/.env.example`:
```
VITE_API_URL=http://localhost:8000
```
```bash
cp .env.example .env
```

- [ ] **Step 2: Write the API client**

`frontend/src/api/client.ts`:
```ts
const BASE = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api`;
const ACCESS_KEY = "asc_access";
const REFRESH_KEY = "asc_refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export type Paginated<T> = { items: T[]; count: number };

type Params = Record<string, string | number | undefined>;
type Options = { body?: unknown; form?: FormData; params?: Params; blob?: boolean };

function messageFrom(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: string[] };
    const field = first.loc?.[first.loc.length - 1];
    return field ? `${field}: ${first.msg}` : (first.msg ?? "Invalid input");
  }
  return `Request failed (${status})`;
}

let refreshing: Promise<boolean> | null = null;

function refreshAccess(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/token/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        tokens.set((await res.json()).access);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function request<T>(method: string, path: string, options: Options = {}, retry = true): Promise<T> {
  const url = new URL(BASE + path);
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }
  const headers: Record<string, string> = {};
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0, "network");
  }

  if (res.status === 401 && retry && tokens.refresh) {
    if (await refreshAccess()) return request<T>(method, path, options, false);
    tokens.clear();
    window.dispatchEvent(new Event("asc:logout"));
  }
  if (res.status === 204) return undefined as T;
  if (options.blob && res.ok) return (await res.blob()) as T;

  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(messageFrom(data, res.status), res.status, (data as { code?: string } | null)?.code);
  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Params) => request<T>("GET", path, { params }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body: body ?? {} }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body: body ?? {} }),
  delete: <T>(path: string) => request<T>("DELETE", path),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, { form }),
  blob: (path: string) => request<Blob>("GET", path, { blob: true }),
};

/**
 * Opens a protected file (such as a PDF) in a new tab, optionally at a page.
 * The file endpoint needs the JWT, so a plain link would return 401. The tab is opened before the
 * first await because browsers block window.open calls that happen after one.
 */
export async function openProtectedFile(path: string, page?: number): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const blob = await api.blob(path);
    const pdf = new Blob([blob], { type: "application/pdf" });
    const url = URL.createObjectURL(pdf);
    const target = page ? `${url}#page=${page}` : url;
    if (tab) tab.location.href = target;
    else window.location.href = target;
    setTimeout(() => URL.revokeObjectURL(url), 5 * 60_000);
  } catch (error) {
    tab?.close();
    throw error;
  }
}
```

`frontend/src/api/types.ts`:
```ts
export type User = { id: string; email: string; name: string; is_staff: boolean };
export type AuthResponse = { access: string; refresh: string; user: User };

export type Space = {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
  project_count: number;
  created_at: string;
};

export type Project = {
  id: string;
  space_id: string;
  space_name: string;
  name: string;
  description: string;
  learning_goal: string;
  last_activity_at: string | null;
  created_at: string;
};
```

- [ ] **Step 3: Write the auth provider and guards**

`frontend/src/auth/AuthProvider.tsx`:
```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, tokens } from "../api/client";
import type { AuthResponse, User } from "../api/types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login(email: string, password: string): Promise<void>;
  register(name: string, email: string, password: string): Promise<void>;
  logout(): void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    tokens.clear();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    if (!tokens.access) {
      setLoading(false);
      return;
    }
    api
      .get<User>("/auth/me")
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    window.addEventListener("asc:logout", logout);
    return () => window.removeEventListener("asc:logout", logout);
  }, [logout]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async login(email, password) {
        const res = await api.post<AuthResponse>("/auth/token", { email, password });
        tokens.set(res.access, res.refresh);
        setUser(res.user);
      },
      async register(name, email, password) {
        const res = await api.post<AuthResponse>("/auth/register", { name, email, password });
        tokens.set(res.access, res.refresh);
        setUser(res.user);
      },
      logout,
    }),
    [user, loading, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
```

`frontend/src/auth/RequireAuth.tsx`:
```tsx
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "./AuthProvider";

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner className="mx-auto mt-24" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
```

`frontend/src/auth/RequireAdmin.tsx`:
```tsx
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "./AuthProvider";

/** A convenience for the UI only. The real control is StaffJWTAuth on the API. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner className="mx-auto mt-16" />;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.is_staff) return <Navigate to="/" replace />;
  return <>{children}</>;
}
```

- [ ] **Step 4: Write the UI primitives**

`frontend/src/components/ui/Spinner.tsx`:
```tsx
export function Spinner({ className = "" }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={`h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600 ${className}`}
    />
  );
}
```

`frontend/src/components/ui/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};

const variants = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-700",
  secondary: "bg-white text-slate-800 border border-slate-300 hover:bg-slate-50",
  ghost: "text-slate-700 hover:bg-slate-100",
  danger: "bg-red-600 text-white hover:bg-red-700",
};
const sizes = { sm: "px-2.5 py-1.5 text-sm", md: "px-4 py-2 text-sm" };

export function Button({ variant = "primary", size = "md", loading, disabled, className = "", children, ...rest }: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading ? "Working…" : children}
    </button>
  );
}
```

`frontend/src/components/ui/Card.tsx`:
```tsx
import type { ReactNode } from "react";

type Props = { title?: string; actions?: ReactNode; className?: string; children: ReactNode };

export function Card({ title, actions, className = "", children }: Props) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
```

`frontend/src/components/ui/Input.tsx`:
```tsx
import { useId, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string };

export function Input({ label, error, className = "", id, ...rest }: Props) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-slate-700">
          {label}
        </label>
      )}
      <input
        id={inputId}
        {...rest}
        className={`w-full rounded-lg border px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 ${error ? "border-red-400" : "border-slate-300"} ${className}`}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
```

`frontend/src/components/ui/Textarea.tsx`:
```tsx
import { useId, type TextareaHTMLAttributes } from "react";

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string };

export function Textarea({ label, error, className = "", id, ...rest }: Props) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-slate-700">
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        rows={3}
        {...rest}
        className={`w-full rounded-lg border px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 ${error ? "border-red-400" : "border-slate-300"} ${className}`}
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
```

`frontend/src/components/ui/Badge.tsx`:
```tsx
import type { ReactNode } from "react";

const tones = {
  gray: "bg-slate-100 text-slate-700",
  green: "bg-green-100 text-green-800",
  yellow: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-800",
  blue: "bg-blue-100 text-blue-800",
};

export function Badge({ tone = "gray", children }: { tone?: keyof typeof tones; children: ReactNode }) {
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
```

- [ ] **Step 5: Write the shared components**

`frontend/src/components/shared/PageHeader.tsx`:
```tsx
import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}
```

`frontend/src/components/shared/EmptyState.tsx`:
```tsx
import type { ReactNode } from "react";

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
      <p className="font-medium text-slate-900">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

`frontend/src/components/shared/ErrorState.tsx`:
```tsx
import { Button } from "../ui/Button";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
      <p className="font-medium">We couldn't load this.</p>
      <p className="mt-1">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
```

`frontend/src/components/shared/StatusBadge.tsx`:
```tsx
import { Badge } from "../ui/Badge";

const toneFor: Record<string, "gray" | "green" | "yellow" | "red" | "blue"> = {
  queued: "gray",
  processing: "blue",
  running: "blue",
  active: "blue",
  ready: "green",
  succeeded: "green",
  completed: "green",
  done: "green",
  ok: "green",
  improving: "green",
  stable: "gray",
  not_enough_data: "gray",
  superseded: "gray",
  needs_attention: "yellow",
  failed: "red",
  error: "red",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={toneFor[status] ?? "gray"}>{status.replaceAll("_", " ")}</Badge>;
}
```

`frontend/src/components/shared/MasteryBar.tsx`:
```tsx
import { StatusBadge } from "./StatusBadge";

export function MasteryBar({ label, value, trend }: { label: string; value: number; trend?: string }) {
  const percent = Math.round(Math.min(Math.max(value, 0), 1) * 100);
  const color = percent >= 70 ? "bg-green-500" : percent >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="truncate font-medium text-slate-800">{label}</span>
        <span className="flex items-center gap-2">
          {trend && <StatusBadge status={trend} />}
          <span className="tabular-nums text-slate-600">{percent}%</span>
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-200" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Write the layout, auth pages and router**

`frontend/src/components/layout/nav.ts`:
```ts
export type NavItem = { to: string; label: string; staffOnly?: boolean };

// Later phases append items here (Analytics, Admin).
export const navItems: NavItem[] = [{ to: "/", label: "Home" }];
```

`frontend/src/components/layout/AppLayout.tsx`:
```tsx
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { Button } from "../ui/Button";
import { navItems } from "./nav";

export function AppLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="font-semibold text-indigo-700">AI Study Companion</span>
            <nav className="flex gap-1">
              {navItems
                .filter((item) => !item.staffOnly || user?.is_staff)
                .map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      `rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100"}`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span className="hidden sm:inline">{user?.name || user?.email}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
```

`frontend/src/features/auth/LoginPage.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-20 max-w-sm px-4">
      <h1 className="mb-6 text-center text-2xl font-semibold text-indigo-700">AI Study Companion</h1>
      <Card title="Sign in">
        <form onSubmit={onSubmit} className="space-y-4">
          <Input label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Input label="Password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <Button type="submit" loading={busy} className="w-full">
            Sign in
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-600">
          New here? <Link to="/register" className="text-indigo-600 hover:underline">Create an account</Link>
        </p>
      </Card>
    </div>
  );
}
```

`frontend/src/features/auth/RegisterPage.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(name, email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-20 max-w-sm px-4">
      <h1 className="mb-6 text-center text-2xl font-semibold text-indigo-700">AI Study Companion</h1>
      <Card title="Create your account">
        <form onSubmit={onSubmit} className="space-y-4">
          <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Input label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Input label="Password" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <Button type="submit" loading={busy} className="w-full">
            Create account
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-600">
          Already registered? <Link to="/login" className="text-indigo-600 hover:underline">Sign in</Link>
        </p>
      </Card>
    </div>
  );
}
```

`frontend/src/routes.tsx` (Task 5 adds the app pages):
```tsx
import { createBrowserRouter } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [{ index: true, element: <p>Signed in.</p> }],
      },
    ],
  },
]);
```

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { router } from "./routes";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 10_000, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
```

Set the page title in `frontend/index.html`: `<title>AI Study Companion</title>`.

- [ ] **Step 7: Verify**

```bash
npm run build
```
Expected: build succeeds with no TypeScript errors.

Manual check with the API (`python manage.py runserver 8000`) and `npm run dev` running:
1. Open `http://localhost:5173`. You are redirected to `/login`.
2. Register a new account. You land on a page that says "Signed in." and the header shows your name.
3. Reload the page. You stay signed in.
4. Sign out. You return to `/login`. Signing in with a wrong password shows "Email or password is incorrect."

- [ ] **Step 8: Commit**

```bash
cd .. && git add frontend && git commit -m "feat: scaffold React app with API client, token refresh, auth pages and UI primitives

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Spaces and Projects UI

**Files:**
- Create: `frontend/src/api/workspace.ts`
- Create: `frontend/src/features/home/HomePage.tsx`, `frontend/src/features/spaces/{SpacesPage,SpacePage}.tsx`
- Modify: `frontend/src/components/layout/nav.ts`
- Create: `frontend/src/features/projects/{ProjectLayout,ProjectDashboardPage}.tsx`, `frontend/src/features/projects/{tabs,useProjectId}.ts`
- Modify: `frontend/src/routes.tsx`

**Interfaces:**
- Consumes: the workspace endpoints from Task 3; `api`, `Paginated`, UI primitives and shared components from Task 4.
- Produces: `projectTabs`, `useProjectId`, `ProjectLayout` with an `<Outlet />` for tab pages; hooks `useSpaces`, `useSpace`, `useCreateSpace`, `useProjects`, `useProject`, `useCreateProject`. Routes `/` (Home), `/spaces` (list and create Spaces), `/spaces/:spaceId`, `/projects/:projectId`. Phase 5 rewrites `HomePage.tsx` and `ProjectDashboardPage.tsx` with real dashboards; `SpacesPage` stays as the place to manage Spaces.

- [ ] **Step 1: Write the hooks**

`frontend/src/api/workspace.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Paginated } from "./client";
import type { Project, Space } from "./types";

export function useSpaces() {
  return useQuery({ queryKey: ["spaces"], queryFn: () => api.get<Paginated<Space>>("/spaces", { limit: 100 }) });
}

export function useSpace(spaceId: string) {
  return useQuery({ queryKey: ["spaces", spaceId], queryFn: () => api.get<Space>(`/spaces/${spaceId}`) });
}

export function useCreateSpace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description: string }) => api.post<Space>("/spaces", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["spaces"] }),
  });
}

export function useProjects(spaceId: string) {
  return useQuery({
    queryKey: ["projects", "by-space", spaceId],
    queryFn: () => api.get<Paginated<Project>>(`/spaces/${spaceId}/projects`, { limit: 100 }),
  });
}

export function useProject(projectId: string) {
  return useQuery({ queryKey: ["projects", projectId], queryFn: () => api.get<Project>(`/projects/${projectId}`) });
}

export function useCreateProject(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description: string; learning_goal: string }) =>
      api.post<Project>(`/spaces/${spaceId}/projects`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", "by-space", spaceId] });
      queryClient.invalidateQueries({ queryKey: ["spaces"] });
    },
  });
}
```

- [ ] **Step 2: Write the Spaces page and a first Home page**

`frontend/src/features/spaces/SpacesPage.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useCreateSpace, useSpaces } from "../../api/workspace";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { PageHeader } from "../../components/shared/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { Textarea } from "../../components/ui/Textarea";

export function NewSpaceForm({ onDone }: { onDone: () => void }) {
  const createSpace = useCreateSpace();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    createSpace.mutate({ name, description }, { onSuccess: onDone });
  }

  return (
    <Card title="New Space" className="mb-6">
      <form onSubmit={onSubmit} className="space-y-3">
        <Input label="Name" required maxLength={120} placeholder="e.g. Machine Learning" value={name} onChange={(e) => setName(e.target.value)} />
        <Textarea label="Description" required placeholder="What broad area is this Space for?" value={description} onChange={(e) => setDescription(e.target.value)} />
        {createSpace.error && <p role="alert" className="text-sm text-red-600">{createSpace.error.message}</p>}
        <div className="flex gap-2">
          <Button type="submit" loading={createSpace.isPending}>Create Space</Button>
          <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

export function SpacesPage() {
  const spaces = useSpaces();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Your Spaces"
        subtitle="A Space is a broad area you want to learn. Projects inside it hold your materials, Tutor and quizzes."
        actions={!creating && <Button onClick={() => setCreating(true)}>New Space</Button>}
      />
      {creating && <NewSpaceForm onDone={() => setCreating(false)} />}
      {spaces.isLoading && <Spinner className="mx-auto mt-10" />}
      {spaces.error && <ErrorState error={spaces.error} onRetry={() => spaces.refetch()} />}
      {spaces.data && spaces.data.items.length === 0 && !creating && (
        <EmptyState
          title="No Spaces yet"
          description="Create your first Space to start a learning journey."
          action={<Button onClick={() => setCreating(true)}>Create a Space</Button>}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {spaces.data?.items.map((space) => (
          <Link key={space.id} to={`/spaces/${space.id}`} className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500">
            <Card className="h-full transition hover:border-indigo-300">
              <h2 className="font-semibold text-slate-900">{space.name}</h2>
              <p className="mt-1 line-clamp-2 text-sm text-slate-600">{space.description}</p>
              <p className="mt-3 text-xs text-slate-500">
                {space.project_count} {space.project_count === 1 ? "project" : "projects"}
              </p>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
```

`frontend/src/features/home/HomePage.tsx` (Phase 5 replaces this with the learning dashboard):
```tsx
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { EmptyState } from "../../components/shared/EmptyState";
import { PageHeader } from "../../components/shared/PageHeader";
import { Button } from "../../components/ui/Button";

export function HomePage() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title={user?.name ? `Welcome, ${user.name}` : "Welcome"} subtitle="Pick up where you left off." />
      <EmptyState
        title="Start with a Space"
        description="A Space is a broad area you want to learn. A Project inside it holds your material, Tutor, quizzes and progress."
        action={
          <Link to="/spaces">
            <Button>Go to Spaces</Button>
          </Link>
        }
      />
    </>
  );
}
```

- [ ] **Step 3: Write the Space page**

`frontend/src/features/spaces/SpacePage.tsx`:
```tsx
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useCreateProject, useProjects, useSpace } from "../../api/workspace";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { PageHeader } from "../../components/shared/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { Textarea } from "../../components/ui/Textarea";

function NewProjectForm({ spaceId, onCancel }: { spaceId: string; onCancel: () => void }) {
  const createProject = useCreateProject(spaceId);
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [goal, setGoal] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    createProject.mutate(
      { name, description, learning_goal: goal },
      { onSuccess: (project) => navigate(`/projects/${project.id}`) },
    );
  }

  return (
    <Card title="New Project" className="mb-6">
      <form onSubmit={onSubmit} className="space-y-3">
        <Input label="Name" required maxLength={160} placeholder="e.g. Neural Networks basics" value={name} onChange={(e) => setName(e.target.value)} />
        <Textarea label="Description" required placeholder="What does this Project cover?" value={description} onChange={(e) => setDescription(e.target.value)} />
        <Textarea label="Learning goal" required placeholder="What do you want to be able to do? The Tutor uses this." value={goal} onChange={(e) => setGoal(e.target.value)} />
        {createProject.error && <p role="alert" className="text-sm text-red-600">{createProject.error.message}</p>}
        <div className="flex gap-2">
          <Button type="submit" loading={createProject.isPending}>Create Project</Button>
          <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

export function SpacePage() {
  const { spaceId = "" } = useParams();
  const space = useSpace(spaceId);
  const projects = useProjects(spaceId);
  const [creating, setCreating] = useState(false);

  if (space.isLoading) return <Spinner className="mx-auto mt-10" />;
  if (space.error) return <ErrorState error={space.error} onRetry={() => space.refetch()} />;

  return (
    <>
      <p className="mb-2 text-sm"><Link to="/spaces" className="text-indigo-600 hover:underline">← All Spaces</Link></p>
      <PageHeader
        title={space.data?.name ?? ""}
        subtitle={space.data?.description}
        actions={!creating && <Button onClick={() => setCreating(true)}>New Project</Button>}
      />
      {creating && <NewProjectForm spaceId={spaceId} onCancel={() => setCreating(false)} />}
      {projects.isLoading && <Spinner className="mx-auto mt-10" />}
      {projects.error && <ErrorState error={projects.error} onRetry={() => projects.refetch()} />}
      {projects.data && projects.data.items.length === 0 && !creating && (
        <EmptyState
          title="No Projects in this Space"
          description="A Project is one focused learning journey with its own materials, Tutor and quizzes."
          action={<Button onClick={() => setCreating(true)}>Create a Project</Button>}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {projects.data?.items.map((project) => (
          <Link key={project.id} to={`/projects/${project.id}`} className="block rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500">
            <Card className="h-full transition hover:border-indigo-300">
              <h2 className="font-semibold text-slate-900">{project.name}</h2>
              <p className="mt-1 line-clamp-2 text-sm text-slate-600">{project.description}</p>
              <p className="mt-3 text-xs text-slate-500">Goal: {project.learning_goal}</p>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 4: Write the Project layout and first tab**

`frontend/src/features/projects/tabs.ts`:
```ts
// Each phase appends its tab here. `path: ""` is the index route.
export const projectTabs: { path: string; label: string }[] = [{ path: "", label: "Dashboard" }];
```

`frontend/src/features/projects/useProjectId.ts`:
```ts
import { useParams } from "react-router-dom";

export function useProjectId(): string {
  const { projectId } = useParams();
  if (!projectId) throw new Error("useProjectId must be used inside a /projects/:projectId route");
  return projectId;
}
```

`frontend/src/features/projects/ProjectLayout.tsx`:
```tsx
import { Link, NavLink, Outlet } from "react-router-dom";
import { useProject } from "../../api/workspace";
import { ErrorState } from "../../components/shared/ErrorState";
import { Spinner } from "../../components/ui/Spinner";
import { projectTabs } from "./tabs";
import { useProjectId } from "./useProjectId";

export function ProjectLayout() {
  const projectId = useProjectId();
  const project = useProject(projectId);

  if (project.isLoading) return <Spinner className="mx-auto mt-10" />;
  if (project.error) return <ErrorState error={project.error} onRetry={() => project.refetch()} />;
  if (!project.data) return null;

  return (
    <>
      <p className="mb-2 text-sm">
        <Link to={`/spaces/${project.data.space_id}`} className="text-indigo-600 hover:underline">
          ← {project.data.space_name}
        </Link>
      </p>
      <h1 className="text-2xl font-semibold text-slate-900">{project.data.name}</h1>
      <p className="mt-1 text-sm text-slate-600">Goal: {project.data.learning_goal}</p>
      <nav className="mb-6 mt-5 flex gap-1 overflow-x-auto border-b border-slate-200" aria-label="Project sections">
        {projectTabs.map((tab) => (
          <NavLink
            key={tab.path}
            to={tab.path}
            end={tab.path === ""}
            className={({ isActive }) =>
              `whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium ${isActive ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-600 hover:text-slate-900"}`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  );
}
```

`frontend/src/features/projects/ProjectDashboardPage.tsx`:
```tsx
import { useProject } from "../../api/workspace";
import { Card } from "../../components/ui/Card";
import { useProjectId } from "./useProjectId";

export function ProjectDashboardPage() {
  const project = useProject(useProjectId());
  if (!project.data) return null;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="About this Project">
        <p className="text-sm text-slate-700">{project.data.description}</p>
      </Card>
      <Card title="Learning goal">
        <p className="text-sm text-slate-700">{project.data.learning_goal}</p>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Register the routes and the nav item**

In `frontend/src/components/layout/nav.ts`:
```ts
export const navItems: NavItem[] = [
  { to: "/", label: "Home" },
  { to: "/spaces", label: "Spaces" },
];
```

Replace `frontend/src/routes.tsx`:
```tsx
import { createBrowserRouter } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { HomePage } from "./features/home/HomePage";
import { ProjectDashboardPage } from "./features/projects/ProjectDashboardPage";
import { ProjectLayout } from "./features/projects/ProjectLayout";
import { SpacePage } from "./features/spaces/SpacePage";
import { SpacesPage } from "./features/spaces/SpacesPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "spaces", element: <SpacesPage /> },
          { path: "spaces/:spaceId", element: <SpacePage /> },
          {
            path: "projects/:projectId",
            element: <ProjectLayout />,
            children: [
              { index: true, element: <ProjectDashboardPage /> },
              // Later phases add: materials, tutor, quiz, growth, analytics
            ],
          },
        ],
      },
    ],
  },
]);
```

- [ ] **Step 6: Verify**

```bash
cd frontend && npm run build
```
Expected: build succeeds.

Manual check:
1. Click **Spaces** in the top nav. Create a Space, then a Project inside it. You land on the Project page with a "Dashboard" tab.
2. Register a second account in a private window. It sees no Spaces.
3. Copy the first account's Project URL into the second account's window. You see the "We couldn't load this. Not found" error state.

- [ ] **Step 7: Phase wrap-up and commit**

```bash
cd ../backend && pytest -q && cd ../frontend && npm run build && cd ..
```
Create `docs/PROMPTS.md` if it does not exist, with the headings Architecture, Frontend, Backend, Database, AI, Debugging, Testing, Documentation. Add the prompts that shaped this phase under the matching headings.

```bash
git add frontend docs/PROMPTS.md && git commit -m "feat: add Spaces and Projects UI with project tab layout

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
