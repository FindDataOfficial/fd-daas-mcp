"""
CKAN source adapter — accesses any CKAN open data portal.

Supports configurable portal URL (default: data.gov).
Provides curated function stubs for common CKAN operations.
"""
from __future__ import annotations

from typing import Any

from cli_anything.world.sources.base import SourceAdapter

# Curated CKAN functions — available even without ckanapi installed
CKAN_FUNCTIONS = [
    {
        "name": "ckan_package_search",
        "label": "Search Datasets",
        "description": "Search datasets on a CKAN portal by keyword",
        "category": "discovery",
        "parameters": [
            {"name": "q", "type": "str", "required": True, "description": "Search query"},
            {"name": "rows", "type": "int", "required": False, "description": "Max results (default 10)"},
        ],
        "columns": [
            {"name": "title", "type": "str", "description": "Dataset title"},
            {"name": "name", "type": "str", "description": "Dataset slug/identifier"},
            {"name": "notes", "type": "str", "description": "Dataset description"},
            {"name": "organization", "type": "str", "description": "Publishing organization"},
            {"name": "resources", "type": "int", "description": "Number of resources (files)"},
        ],
    },
    {
        "name": "ckan_package_show",
        "label": "Get Dataset Detail",
        "description": "Get full metadata for a CKAN dataset including resource URLs",
        "category": "discovery",
        "parameters": [
            {"name": "id", "type": "str", "required": True, "description": "Dataset ID or slug"},
        ],
        "columns": [
            {"name": "title", "type": "str", "description": "Dataset title"},
            {"name": "name", "type": "str", "description": "Dataset slug"},
            {"name": "notes", "type": "str", "description": "Description"},
            {"name": "license_title", "type": "str", "description": "License"},
            {"name": "resources_count", "type": "int", "description": "Number of resources"},
        ],
    },
    {
        "name": "ckan_resource_show",
        "label": "Get Resource Detail",
        "description": "Get metadata for a specific resource (file) in a dataset",
        "category": "discovery",
        "parameters": [
            {"name": "id", "type": "str", "required": True, "description": "Resource ID"},
        ],
        "columns": [
            {"name": "name", "type": "str", "description": "Resource name"},
            {"name": "format", "type": "str", "description": "File format (CSV, JSON, etc.)"},
            {"name": "url", "type": "str", "description": "Download URL"},
            {"name": "size", "type": "int", "description": "File size in bytes"},
        ],
    },
    {
        "name": "ckan_organization_list",
        "label": "List Organizations",
        "description": "List all organizations (publishers) on a CKAN portal",
        "category": "discovery",
        "parameters": [],
        "columns": [
            {"name": "display_name", "type": "str", "description": "Organization display name"},
            {"name": "name", "type": "str", "description": "Organization slug"},
            {"name": "description", "type": "str", "description": "Organization description"},
            {"name": "package_count", "type": "int", "description": "Number of datasets"},
        ],
    },
    {
        "name": "ckan_tag_list",
        "label": "List Tags",
        "description": "List all tags used across datasets on the portal",
        "category": "discovery",
        "parameters": [
            {"name": "query", "type": "str", "required": False, "description": "Filter tags by prefix"},
        ],
        "columns": [
            {"name": "display_name", "type": "str", "description": "Tag display name"},
            {"name": "name", "type": "str", "description": "Tag slug"},
        ],
    },
]


class CKANAdapter(SourceAdapter):
    """Adapter for CKAN open data portals."""

    def __init__(self, portal_url: str = "https://demo.ckan.org"):
        self._portal_url = portal_url

    @property
    def name(self) -> str:
        return "ckan"

    @property
    def label(self) -> str:
        return "CKAN Open Data"

    @property
    def description(self) -> str:
        return f"Open data portal — {self._portal_url}"

    @property
    def url(self) -> str:
        return self._portal_url

    def is_available(self) -> bool:
        try:
            import ckanapi
            return True
        except ImportError:
            return False

    def discover(self) -> list[dict]:
        """Return curated CKAN function stubs."""
        result = []
        for func in CKAN_FUNCTIONS:
            result.append({
                **func,
                "source": "ckan",
            })
        return result

    def _get_client(self):
        """Get a CKAN API client. Raises SourceUnavailableError if not installed."""
        from cli_anything.world.core.exceptions import SourceUnavailableError

        if not self.is_available():
            raise SourceUnavailableError("ckan", "Install: pip install ckanapi")

        import ckanapi
        return ckanapi.RemoteCKAN(self._portal_url)

    def fetch(self, function_name: str, **params: Any) -> Any:
        """Execute a CKAN API call.

        Supported functions: ckan_package_search, ckan_package_show,
        ckan_resource_show, ckan_organization_list, ckan_tag_list.
        """
        import pandas as pd

        client = self._get_client()

        # Strip namespace prefix
        local_name = function_name
        if local_name.startswith("ckan_"):
            local_name = local_name[len("ckan_"):]

        if local_name == "package_search":
            result = client.action.package_search(q=params.get("q", ""), rows=params.get("rows", 10))
            datasets = result.get("results", [])
            rows = []
            for ds in datasets:
                rows.append({
                    "title": ds.get("title", ""),
                    "name": ds.get("name", ""),
                    "notes": ds.get("notes", ""),
                    "organization": ds.get("organization", {}).get("title", ""),
                    "resources": len(ds.get("resources", [])),
                })
            return pd.DataFrame(rows)

        elif local_name == "package_show":
            result = client.action.package_show(id=params.get("id", ""))
            return pd.DataFrame([{
                "title": result.get("title", ""),
                "name": result.get("name", ""),
                "notes": result.get("notes", ""),
                "license_title": result.get("license_title", ""),
                "resources_count": len(result.get("resources", [])),
            }])

        elif local_name == "resource_show":
            result = client.action.resource_show(id=params.get("id", ""))
            return pd.DataFrame([{
                "name": result.get("name", ""),
                "format": result.get("format", ""),
                "url": result.get("url", ""),
                "size": result.get("size", 0),
            }])

        elif local_name == "organization_list":
            result = client.action.organization_list(all_fields=True)
            rows = []
            for org in result:
                rows.append({
                    "display_name": org.get("display_name", ""),
                    "name": org.get("name", ""),
                    "description": org.get("description", ""),
                    "package_count": org.get("package_count", 0),
                })
            return pd.DataFrame(rows)

        elif local_name == "tag_list":
            result = client.action.tag_list(query=params.get("query", ""), all_fields=True)
            rows = []
            for tag in result:
                rows.append({
                    "display_name": tag.get("display_name", tag.get("name", "")),
                    "name": tag.get("name", ""),
                })
            return pd.DataFrame(rows)

        else:
            from cli_anything.world.core.exceptions import FunctionNotFoundError
            raise FunctionNotFoundError(function_name)

    def columns(self, function_name: str) -> list[dict]:
        """Return column metadata from curated definitions."""
        local_name = function_name
        if local_name.startswith("ckan_"):
            local_name = local_name[len("ckan_"):]

        for func in CKAN_FUNCTIONS:
            if func["name"] == f"ckan_{local_name}":
                return func.get("columns", [])
        return []
