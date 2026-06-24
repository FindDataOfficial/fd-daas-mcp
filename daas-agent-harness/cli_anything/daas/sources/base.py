"""
Abstract base class for DAAS data source adapters.

Each source implements three methods:
  - discover() -> list[dict]: return available functions
  - fetch(function_name, **params) -> pd.DataFrame: execute a function
  - columns(function_name) -> list[dict]: return column metadata
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SourceAdapter(ABC):
    """Base class for all data source adapters.

    Subclasses MUST implement discover(), fetch(), and columns().
    The `name` property must match the source name in the config (e.g., 'worldbank').
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique source identifier: 'akshare', 'worldbank', 'ckan', 'cnstats'."""
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-readable label: 'AKShare', 'World Bank', etc."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of what data this source provides."""
        ...

    @property
    def url(self) -> str:
        """Source homepage or API base URL."""
        return ""

    @property
    def enabled(self) -> bool:
        """Whether this source is active."""
        return True

    def is_available(self) -> bool:
        """Check if the underlying dependency is installed/accessible."""
        return True

    @abstractmethod
    def discover(self) -> list[dict]:
        """Return all available functions from this source.

        Each dict must have keys: name, category, description, parameters (list),
        and optionally columns (list of {name, type, description}).
        """
        ...

    @abstractmethod
    def fetch(self, function_name: str, **params: Any) -> Any:
        """Execute a function and return results (typically a pandas DataFrame)."""
        ...

    @abstractmethod
    def columns(self, function_name: str) -> list[dict]:
        """Return column metadata for a function.

        Each dict must have keys: name, type, description, nullable.
        """
        ...
