class ServiceError(Exception):
    """A business-rule failure that reaches the client as a JSON error."""

    def __init__(self, message: str, *, status: int = 400, code: str = "error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
