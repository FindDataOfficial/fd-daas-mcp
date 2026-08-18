# Descriptor JSON Schema

`daas.descriptor.json` mirrors the daas.db tables (`sources`, `daas_functions`,
`daas_function_columns`, `indicator_rules`) so it can be imported idempotently by
`scripts/import_descriptor.py`. Every field the agent can't determine should be
left empty (`""`) with a `note` explaining why - never guess.

## Top level

```jsonc
{
  "schema_version": 1,
  "generated_at": "",            // ISO timestamp; agent fills at write time
  "source": { /* Source, see below */ },
  "daas_functions": [ /* Function[], see below */ ]
}
```

## Source (mirrors `sources` table)

```jsonc
{
  "name": "tiny_econ",            // REQUIRED, unique daas source name
  "label": "Tiny Econ (test fixture)",
  "description": "Fake economic data library for testing.",
  "url": "https://github.com/example/tiny_econ",
  "score": 0.6,                  // source-level default score, 0..1 (nullable)
  "category": null               // optional category id/name
}
```

## Function (mirrors `daas_functions` + nested columns/entities)

```jsonc
{
  "name": "get_cpi_series",       // REQUIRED, the Python function name
  "label": "CPI 同比序列",
  "description": "获取 CPI 同比序列数据。",
  "category": "macro",            // REQUIRED
  "module": "tiny_econ.api",      // dotted import path
  "file": "tiny_econ/api.py",
  "lineno": 10,
  "output_type": "DataFrame",     // DataFrame | list | dict | ...
  "frequency": "monthly",         // see rubric: realtime|intraday|daily|weekly|monthly|quarterly|annual|irregular
  "has_existing_cli": false,      // from analyze_project.py; sidecar wraps only false
  "data_provenance": "国家统计局 (simulated)",  // upstream source
  "confidence": 0.72,             // 0..1, see rubric
  "confidence_reasoning": "provenance=official(0.3) + doc=fields+params(0.25) + freshness=monthly-official(0.2) + stability=partial-hints(0.075) + keyless(0.1) - 1 missing field annotation",
  "parameters": [ /* Param[] */ ],
  "columns":    [ /* Column[] */ ],
  "entities":   [ /* EntityRef[] */ ]
}
```

### Param

```jsonc
{ "name": "country", "type": "str", "required": false, "description": "ISO alpha-2 国家代码", "default": "CN" }
```

### Column (mirrors `daas_function_columns` + nested indicator proposals)

```jsonc
{
  "name": "cpi_yoy",              // REQUIRED
  "label": "CPI 同比",
  "type": "float",
  "description": "居民消费价格指数同比涨幅 (%)",
  "nullable": false,
  "indicator_match": "candidate_new_metric",  // candidate_new_metric | existing_metric | not_a_metric
  "indicator_note": "CPI 同比是宏观通胀指标, daas 现有 indicator_rules 全为美股技术指标, 无任何宏观概念匹配",
  "proposed_indicator_rules": [ /* Indicator[] */ ]
}
```

### Indicator (mirrors `indicator_rules`)

```jsonc
{
  "name": "tiny_econ_get_cpi_series_cpi_yoy_sma12",  // REQUIRED, unique rule name
  "indicator_name": "tiny_econ_get_cpi_series_cpi_yoy_sma12",  // REQUIRED, the series label
  "datasource": "tiny_econ",
  "function_name": "get_cpi_series",
  "source_table": "scraw_tiny_econ_get_cpi_series",
  "date_column": "date",
  "value_column": "cpi_yoy",      // REQUIRED
  "op": "sma",                    // REQUIRED, one of run_indicator.py ops
  "params": { "window": 12 },
  "enabled": true,
  "score": null,                  // nullable
  "dedup_status": "new_concept",  // exists | new | new_concept
  "note": "CPI 12月移动平均; 全新宏观概念"
}
```

### EntityRef (entity coverage; does NOT auto-create links)

```jsonc
{
  "entity_type": "country",       // REQUIRED, e.g. stock | country
  "identifier_shape": "ISO alpha-2 code (CN/US/...)",
  "matched_existing": true,       // does daas.entities already have this type covering these ids?
  "note": "daas has 60 countries incl. CN/US"
}
```

## Full example (fragment)

```json
{
  "schema_version": 1,
  "source": { "name": "tiny_econ", "label": "Tiny Econ", "url": "", "score": 0.6 },
  "daas_functions": [
    {
      "name": "get_cpi_series",
      "label": "CPI 同比序列",
      "description": "获取 CPI 同比序列数据。",
      "category": "macro",
      "module": "tiny_econ.api",
      "output_type": "DataFrame",
      "frequency": "monthly",
      "has_existing_cli": false,
      "data_provenance": "simulated 国家统计局",
      "confidence": 0.72,
      "confidence_reasoning": "official-ish + good doc + monthly + partial hints + keyless",
      "parameters": [
        { "name": "country", "type": "str", "required": false, "description": "ISO alpha-2", "default": "CN" },
        { "name": "start_year", "type": "int", "required": false, "description": "起始年份", "default": 2010 },
        { "name": "end_year", "type": "int", "required": false, "description": "结束年份", "default": 2024 }
      ],
      "columns": [
        { "name": "date", "type": "datetime", "indicator_match": "not_a_metric", "indicator_note": "date axis", "proposed_indicator_rules": [] },
        { "name": "cpi_yoy", "type": "float", "indicator_match": "candidate_new_metric",
          "indicator_note": "CPI 同比 - 全新宏观概念",
          "proposed_indicator_rules": [
            { "name": "tiny_econ_get_cpi_series_cpi_yoy_sma12", "indicator_name": "tiny_econ_get_cpi_series_cpi_yoy_sma12",
              "datasource": "tiny_econ", "function_name": "get_cpi_series", "source_table": "scraw_tiny_econ_get_cpi_series",
              "date_column": "date", "value_column": "cpi_yoy", "op": "sma", "params": { "window": 12 },
              "dedup_status": "new_concept", "note": "CPI 12M MA" },
            { "name": "tiny_econ_get_cpi_series_cpi_yoy_pct_change", "indicator_name": "tiny_econ_get_cpi_series_cpi_yoy_pct_change",
              "datasource": "tiny_econ", "function_name": "get_cpi_series", "source_table": "scraw_tiny_econ_get_cpi_series",
              "date_column": "date", "value_column": "cpi_yoy", "op": "pct_change", "params": {},
              "dedup_status": "new_concept", "note": "CPI 月环比" }
          ]
        },
        { "name": "country", "type": "str", "indicator_match": "not_a_metric", "indicator_note": "identifier", "proposed_indicator_rules": [] }
      ],
      "entities": [
        { "entity_type": "country", "identifier_shape": "ISO alpha-2", "matched_existing": true, "note": "daas has 60 countries" }
      ]
    }
  ]
}
```
