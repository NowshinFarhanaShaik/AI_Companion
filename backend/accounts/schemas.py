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
