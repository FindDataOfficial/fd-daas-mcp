# MCP Tools Contract: daas-mcp

## Server

- **Name**: `daas-mcp`
- **Transport**: stdio (FastMCP)
- **Entry**: `mcp/daas-mcp/server.py`

## Tools

### `list_sources`

List all configured data sources.

```
Input:  (none)
Output: { "sources": [Source] }
```

### `search_functions`

Search for data functions by query string.

```
Input:  { "query": str, "source": str? }
Output: { "results": [FunctionSummary] }
```

### `get_function_detail`

Get full details for a specific function.

```
Input:  { "function_name": str }
Output: { "function": FunctionDetail }
```

### `fetch_data`

Execute a data function and return results.

```
Input:  { "function_name": str, "parameters": dict }
Output: { "data": [dict], "columns": [str], "row_count": int }
```

### `list_categories`

List all categories across sources.

```
Input:  { "source": str? }
Output: { "categories": [str] }
```

## Types

### Source
```json
{
  "name": "worldbank",
  "label": "World Bank",
  "description": "World Bank Open Data",
  "function_count": 1400,
  "enabled": true
}
```

### FunctionSummary
```json
{
  "source": "worldbank",
  "name": "gdp_by_country",
  "label": "GDP by Country",
  "category": "macro",
  "description": "GDP (current US$) by country and year"
}
```

### FunctionDetail
```json
{
  "source": "worldbank",
  "name": "gdp_by_country",
  "label": "GDP by Country",
  "description": "GDP (current US$) by country and year",
  "category": "macro",
  "parameters": [
    {"name": "country", "type": "str", "required": true, "description": "ISO 3-letter country code"},
    {"name": "date", "type": "str", "required": false, "description": "Year range, e.g. 2020:2023"}
  ],
  "columns": [
    {"name": "country", "type": "str", "description": "Country name"},
    {"name": "year", "type": "int64", "description": "Year"},
    {"name": "value", "type": "float64", "description": "GDP in current US$"}
  ]
}
```

## Integration with leader-mcp

daas-mcp registers its functions in the `leader_mcp.db` unified registry via the `store_registry.py` script. leader-mcp queries across all harnesses including DAAS.
