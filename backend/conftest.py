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


@pytest.fixture(autouse=True)
def fake_ai():
    """No test ever reaches a real AI provider."""
    from ai.provider import set_provider
    from ai.testing import FakeProvider

    provider = FakeProvider()
    set_provider(provider)
    yield provider
    set_provider(None)
