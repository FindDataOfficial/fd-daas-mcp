"""
Source router — resolves namespaced function names to source adapters.

Parses 'source_functionname' format, finds the correct adapter,
and delegates fetch().
"""
from __future__ import annotations

from typing import Any

from cli_anything.daas.sources.config import load_sources, get_adapter
from cli_anything.daas.core.exceptions import (
    FunctionNotFoundError,
    SourceUnavailableError,
    ParameterError,
)


class SourceRouter:
    """Routes function calls to the correct source adapter."""

    # Known source prefixes in order of priority
    SOURCE_PREFIXES = ["akshare_", "worldbank_", "ckan_", "cnstats_"]

    def route(self, function_name: str, **params: Any) -> Any:
        """Resolve function name → source adapter → fetch.

        Supports two naming patterns:
          1. Namespaced: 'worldbank_gdp' → worldbank adapter, function 'worldbank_gdp'
          2. Bare name: 'stock_zh_a_hist' → try all adapters

        Returns the result from the adapter's fetch() method.
        """
        # Try to identify source from prefix
        source_name = None
        for prefix in self.SOURCE_PREFIXES:
            if function_name.startswith(prefix):
                source_name = prefix.rstrip("_")
                break

        if source_name:
            return self._fetch_from_source(source_name, function_name, **params)

        # Bare name — try all adapters
        return self._fetch_from_all(function_name, **params)

    def _fetch_from_source(self, source_name: str, function_name: str, **params: Any) -> Any:
        """Fetch from a specific source adapter."""
        configs = load_sources()
        cfg = next((c for c in configs if c.name == source_name), None)
        if cfg is None:
            raise FunctionNotFoundError(function_name)

        if not cfg.enabled:
            raise SourceUnavailableError(source_name, "Source is disabled")

        adapter = get_adapter(source_name)
        if adapter is None:
            raise FunctionNotFoundError(function_name)

        if not adapter.is_available():
            raise SourceUnavailableError(
                source_name,
                f"Optional dependency not installed. {cfg.install_hint()}",
            )

        return adapter.fetch(function_name, **params)

    def _fetch_from_all(self, function_name: str, **params: Any) -> Any:
        """Try all adapters for a bare function name. Returns first match."""
        configs = load_sources()
        last_error = None

        for cfg in configs:
            if not cfg.enabled:
                continue
            adapter = get_adapter(cfg.name)
            if adapter is None or not adapter.is_available():
                continue

            try:
                # Try with namespaced name
                namespaced = f"{cfg.name}_{function_name}"
                return adapter.fetch(namespaced, **params)
            except FunctionNotFoundError:
                continue
            except Exception as e:
                last_error = e
                continue

        if last_error:
            raise last_error
        raise FunctionNotFoundError(function_name)
