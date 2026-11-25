"""Endpoint-specific EEX API adapters."""

from .auctions import AuctionsAPI
from .derivatives import DerivativesAPI
from .gas_spot import GasSpotAPI
from .indices import IndicesAPI
from .transparency import TransparencyAPI

__all__ = [
    "AuctionsAPI",
    "DerivativesAPI",
    "GasSpotAPI",
    "IndicesAPI",
    "TransparencyAPI",
]
