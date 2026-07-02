"""Storefinder-Infrastruktur für deutschlandweite Filialabfragen."""

from .base import StoreFinderResult
from .cache import StoreCache

__all__ = [
    "StoreFinderResult",
    "StoreCache",
]
