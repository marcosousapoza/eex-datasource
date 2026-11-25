"""EEX Group DataSource client and incremental ingestion tools."""

from .client import EEXClient
from .config import Settings
from .errors import (
    EEXAPIError,
    EEXAuthenticationError,
    EEXError,
    EEXNotFoundError,
    EEXRateLimitError,
)

__all__ = [
    "EEXAPIError",
    "EEXAuthenticationError",
    "EEXClient",
    "EEXError",
    "EEXNotFoundError",
    "EEXRateLimitError",
    "Settings",
]

__version__ = "0.1.0"
