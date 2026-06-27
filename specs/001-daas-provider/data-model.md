# Data Model: DAAS Provider

## Entities

### Source

Represents a data source (akshare, worldbank, ckan, cnstats).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, auto | Source ID |
| name | TEXT | UNIQUE, NOT NULL | Source identifier: `akshare`, `yfinance`, `worldbank`, `ckan`, `cnstats` |
| label | TEXT | NOT NULL | Human-readable: "AKShare", "Yahoo Finance", "World Bank", "CKAN", "Chinese Statistics" |
| description | TEXT | | What data this source provides |
| url | TEXT | | Source homepage or API base URL |
| enabled | BOOLEAN | DEFAULT TRUE | Whether this source is active |
| config | TEXT | JSON | Source-specific config (CKAN portal URL, API keys, etc.) |
| created_at | TIMESTAMP | DEFAULT NOW | |
| updated_at | TIMESTAMP | DEFAULT NOW | |

### Function

A callable data function within a source.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, auto | |
| source_id | INTEGER | FK → source.id, NOT NULL | Parent source |
| name | TEXT | NOT NULL | Function identifier: `stock_zh_a_hist`, `gdp_by_country` |
| label | TEXT | | Human-readable description |
| description | TEXT | | What this function returns |
| category | TEXT | | Category tag: `stock`, `macro`, `demographics` |
| parameters | TEXT | JSON | Parameter schema: `[{"name": "symbol", "type": "str", "required": true}]` |
| output_type | TEXT | DEFAULT "DataFrame" | Return type hint |
| created_at | TIMESTAMP | DEFAULT NOW | |
| updated_at | TIMESTAMP | DEFAULT NOW | |

**Unique constraint**: `(source_id, name)`

### FunctionColumn

Describes a column returned by a function.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PK, auto | |
| function_id | INTEGER | FK → function.id, NOT NULL | Parent function |
| name | TEXT | NOT NULL | Column name |
| label | TEXT | | Human-readable label |
| type | TEXT | | Python/dtype: `str`, `float64`, `int64`, `datetime64` |
| description | TEXT | | What this column represents |
| nullable | BOOLEAN | DEFAULT TRUE | |
| created_at | TIMESTAMP | DEFAULT NOW | |

**Unique constraint**: `(function_id, name)`

## Relationships

```
Source 1 ──── * Function
Function 1 ──── * FunctionColumn
```

## State Transitions

**Source**: `enabled` boolean — no complex state machine. Toggle on/off.

**Function/Column**: Read-only after discovery. Re-discovered on `store_registry.py` run (upsert by unique key).

## Validation Rules

1. Source `name` must match `^[a-z][a-z0-9_]*$`
2. Function `parameters` must be valid JSON array of `{name, type, required, default?}` objects
3. FunctionColumn `type` should be one of: `str`, `int64`, `float64`, `bool`, `datetime64`, `object`
4. At least one source must be enabled for the system to be useful (warning, not error)

## Indexes

- `idx_function_source` on `function.source_id`
- `idx_column_function` on `function_column.function_id`
- `idx_function_category` on `function.category`
- Full-text search on `function.name` and `function.description` (via SQLite FTS5 or LIKE)
