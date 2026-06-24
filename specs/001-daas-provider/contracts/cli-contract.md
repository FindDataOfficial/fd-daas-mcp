# CLI Contract: cli-anything-daas

## Entry Point

```
cli-anything-daas [--json] <command> [args...]
```

## Commands

### `list-sources`

List all configured data sources.

```
cli-anything-daas list-sources
cli-anything-daas --json list-sources
```

**Output** (table):
```
SOURCE       LABEL              FUNCTIONS  ENABLED
akshare      AKShare            673        yes
worldbank    World Bank         1400+      yes
ckan         CKAN Open Data     500+       yes
cnstats      Chinese Statistics 50+        yes
```

**Output** (JSON):
```json
{
  "sources": [
    {"name": "akshare", "label": "AKShare", "function_count": 673, "enabled": true},
    ...
  ]
}
```

### `search <query>`

Search functions across all sources.

```
cli-anything-daas search GDP
cli-anything-daas --json search 股票
```

**Output** (JSON):
```json
{
  "results": [
    {
      "source": "worldbank",
      "function": "gdp_by_country",
      "category": "macro",
      "description": "GDP (current US$) by country and year",
      "parameters": [{"name": "country", "type": "str", "required": true}]
    }
  ]
}
```

### `call <function> [params...]`

Execute a data function. Parameters as `key=value` pairs.

```
cli-anything-daas call worldbank_gdp country=CN date=2020:2023
cli-anything-daas --json call stock_zh_a_hist symbol=000001 period=daily start_date=20250101
```

**Output**: Pandas DataFrame as table, or JSON array if `--json` flag.

### `describe <function>`

Show function details including parameters and return columns.

```
cli-anything-daas describe worldbank_gdp
```

**Output**: Function name, description, parameters table, columns table.

### `help`

Show help text (or run with no args for REPL).

## REPL Mode

Running `cli-anything-daas` with no command enters REPL mode:

```
daas> search GDP
daas> call worldbank_gdp country=CN date=2020:2023
daas> help
daas> exit
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Function not found |
| 3 | Parameter error |
| 4 | Source unavailable |
