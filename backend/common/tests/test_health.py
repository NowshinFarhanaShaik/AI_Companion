from django.test import Client


def test_health_endpoint_is_public():
    response = Client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_route_returns_json_404():
    response = Client().get("/api/does-not-exist")
    assert response.status_code == 404
