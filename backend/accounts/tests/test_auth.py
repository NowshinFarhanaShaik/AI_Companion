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
