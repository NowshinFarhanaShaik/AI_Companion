from ninja_jwt.authentication import JWTAuth


class StaffJWTAuth(JWTAuth):
    def authenticate(self, request, token):
        user = super().authenticate(request, token)
        if user is not None and user.is_staff:
            return user
        return None


__all__ = ["JWTAuth", "StaffJWTAuth"]
