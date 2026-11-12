"""Public exception hierarchy."""

from __future__ import annotations

from typing import Any


class EEXError(Exception):
    """Base class for all client errors."""


class ConfigurationError(EEXError):
    """The client configuration is invalid."""


class APIError(EEXError):
    """An HTTP response reported an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        operation: str | None = None,
        parameters: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.operation = operation
        self.parameters = parameters or {}
        self.request_id = request_id


class InvalidRequestError(APIError, ValueError):
    """A local input or remote request is invalid."""


class AuthenticationError(APIError):
    """The API token is missing, invalid, or expired."""


class AuthorizationError(APIError):
    """The subscription does not permit access."""


class NotFoundError(APIError):
    """The requested resource was not found."""


class RateLimitError(APIError):
    """The retry budget was exhausted after rate limiting."""


class TransportError(APIError):
    """A network or server failure occurred."""


class ResponseParsingError(APIError):
    """The response was not valid for the expected JSON shape."""


class SuspectedTruncationError(APIError):
    """A response reached the API record cap and may be incomplete."""

    def __init__(self, result: object, **kwargs: Any) -> None:
        super().__init__("Response reached the API record cap and may be incomplete", **kwargs)
        self.result = result


class MultiRequestError(APIError):
    """At least one partition of a multi-request retrieval failed."""

    def __init__(self, message: str, *, completed: int, failed_partition: object) -> None:
        super().__init__(message)
        self.completed = completed
        self.failed_partition = failed_partition
