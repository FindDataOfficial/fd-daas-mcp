"""
Source configuration loader for DAAS.

Reads source definitions from metadata/sources.yaml and checks
optional dependency availability.
"""
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SourceConfig:
    """Configuration for a single data source."""

    name: str
    label: str
    description: str = ""
    url: str = ""
    enabled: bool = True
    config: dict = field(default_factory=dict)
    pypi_package: Optional[str] = None
    import_module: Optional[str] = None

    def is_installed(self) -> bool:
        """Check if the optional dependency is importable."""
        mod = self.import_module or self.pypi_package
        if mod is None:
            return True
        try:
            importlib.import_module(mod)
            return True
        except ImportError:
            return False

    def install_hint(self) -> str:
        """Return pip install command for this source's dependency."""
        pkg = self.pypi_package or self.name
        return f"pip install {pkg}"


# Default source configurations — curated for the 4 initial sources.
DEFAULT_SOURCES: list[SourceConfig] = [
    SourceConfig(
        name="akshare",
        label="AKShare",
        description="Chinese financial data — stocks, funds, futures, macro, bonds (673+ functions)",
        url="https://github.com/akfamily/akshare",
        pypi_package="akshare",
        import_module="akshare",
    ),
    SourceConfig(
        name="worldbank",
        label="World Bank",
        description="World Bank Open Data — GDP, population, trade, education, health (1400+ indicators)",
        url="https://data.worldbank.org/",
        pypi_package="wbgapi",
        import_module="wbgapi",
    ),
    SourceConfig(
        name="ckan",
        label="CKAN Open Data",
        description="Open data portals (data.gov, data.gov.uk, etc.) — configurable portal URL",
        url="https://data.gov/",
        pypi_package="ckanapi",
        import_module="ckanapi",
        config={"portal_url": "https://data.gov/api/3/"},
    ),
    SourceConfig(
        name="cnstats",
        label="Chinese Statistics",
        description="National Bureau of Statistics macro indicators — CPI, PMI, industrial output, retail sales",
        url="https://data.stats.gov.cn/",
        pypi_package="akshare",  # Uses akshare for NBS data
        import_module="akshare",
    ),
]


def load_sources(config_path: Optional[str] = None) -> list[SourceConfig]:
    """Load source configurations.

    If config_path is provided, loads from YAML file.
    Otherwise uses DEFAULT_SOURCES.
    """
    if config_path and os.path.exists(config_path):
        return _load_from_yaml(config_path)
    return DEFAULT_SOURCES


def _load_from_yaml(path: str) -> list[SourceConfig]:
    """Load source configs from a YAML file."""
    import yaml

    with open(path, "r") as f:
        data = yaml.safe_load(f)
    sources = []
    for item in data.get("sources", []):
        sources.append(SourceConfig(
            name=item["name"],
            label=item.get("label", item["name"]),
            description=item.get("description", ""),
            url=item.get("url", ""),
            enabled=item.get("enabled", True),
            config=item.get("config", {}),
            pypi_package=item.get("pypi_package"),
            import_module=item.get("import_module"),
        ))
    return sources


def get_adapter(source_name: str):
    """Get a source adapter instance by name. Lazy imports to avoid loading all deps."""
    from cli_anything.daas.sources.akshare_source import AKShareAdapter
    from cli_anything.daas.sources.worldbank_source import WorldBankAdapter
    from cli_anything.daas.sources.ckan_source import CKANAdapter
    from cli_anything.daas.sources.cnstats_source import CNStatsAdapter

    adapters = {
        "akshare": AKShareAdapter,
        "worldbank": WorldBankAdapter,
        "ckan": CKANAdapter,
        "cnstats": CNStatsAdapter,
    }
    cls = adapters.get(source_name)
    if cls is None:
        return None
    return cls()
