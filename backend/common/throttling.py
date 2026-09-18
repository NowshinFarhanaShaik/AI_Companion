from ninja.throttling import AuthRateThrottle


class ScopedThrottle(AuthRateThrottle):
    """A named bucket from NINJA_DEFAULT_THROTTLE_RATES, counted per user, or per client IP before sign-in."""

    def __init__(self, scope: str):
        self.scope = scope
        super().__init__()
