"""EEX Group DataSource REST API v2 client."""

from .client import EEXClient
from .exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    EEXError,
    InvalidRequestError,
    MultiRequestError,
    NotFoundError,
    RateLimitError,
    ResponseParsingError,
    SuspectedTruncationError,
    TransportError,
)
from .rate_limit import RateLimiter
from .result import Record, RequestMetadata, Result

__all__ = [
    "APIError",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "EEXClient",
    "EEXError",
    "InvalidRequestError",
    "MultiRequestError",
    "NotFoundError",
    "RateLimitError",
    "RateLimiter",
    "Record",
    "RequestMetadata",
    "ResponseParsingError",
    "Result",
    "SuspectedTruncationError",
    "TransportError",
]
