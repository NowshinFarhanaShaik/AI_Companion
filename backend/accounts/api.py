from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from ninja import Router, Status
from ninja_jwt.exceptions import TokenError
from ninja_jwt.tokens import RefreshToken

from accounts.models import User
from accounts.schemas import AccessOut, AuthOut, LoginIn, RefreshIn, RegisterIn, UserOut
from common.errors import ServiceError
from common.throttling import ScopedThrottle

router = Router(tags=["auth"])


def _auth_payload(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": user}


@router.post("/auth/register", auth=None, response={201: AuthOut}, throttle=ScopedThrottle("sign_up"))
def register(request, data: RegisterIn):
    if User.objects.filter(email=data.email).exists():
        raise ServiceError("An account with this email already exists.", status=409, code="email_taken")
    try:
        validate_password(data.password)
    except ValidationError as exc:
        raise ServiceError(" ".join(exc.messages), status=400, code="weak_password")
    user = User.objects.create_user(email=data.email, password=data.password, name=data.name.strip())
    return Status(201, _auth_payload(user))


@router.post("/auth/token", auth=None, response=AuthOut, throttle=ScopedThrottle("sign_in"))
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
