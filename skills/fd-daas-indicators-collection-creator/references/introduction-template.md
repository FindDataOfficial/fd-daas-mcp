# indicators-<collection>.md — introduction template

Adapt this shape when writing an indicator-collection introduction. Plain markdown, no JS, no external fetch. Co-located with the sibling CSV (`<collection>.csv`).

```markdown
# <collection-name>

<description — one line>

- **Created:** YYYY-MM-DD
- **Members:** N
- **Machine-readable export:** `<collection>.csv` (sibling file — one row per member with resolved scores).
- **Score inheritance:** members with `item_score = null` inherit `indicator_default_score`, else `source_default_score` (the datasource's default). Resolved via `COALESCE(item.score, indicator_rules.score, sources.score)`.

## Members

| indicator | datasource | op | params | source_table | value_column | resolved score | item_score | indicator_default_score | source_default_score |
|---|---|---|---|---|---|---|---|---|---|
| rsi_5 | akshare | rsi | {"window":5} | scraw_ashare_daily | 最新价 | 0.6 | null | null | 0.6 |
| sma_20 | akshare | sma | {"window":20} | scraw_ashare_daily | 最新价 | 0.9 | 0.9 | null | 0.6 |

## How to refresh

Re-run `uv run --with pandas --with numpy python .claude/skills/skill-based-data-fetch/scripts/run_indicator.py <indicator>` for each member (recomputes the series into `observations`).
```

Notes:
- The four score columns come straight from a `sqlite3` query joining `indicator_collection_items` -> `indicator_rules` -> `sources` with `COALESCE(item.score, r.score, s.score)` (see SKILL.md Step 3).
- The `op` / `params` / `source_table` / `value_column` come from `indicator_rules` (joined by indicator name - they live on the rule, not the membership row).
- The sibling CSV has the same data plus `datasource_columns` (value_column + date_column), `enabled`, and a `collection` column — point readers at it for machine use.
- Filename: `indicators-<collection>.md` (nested) or `<collection>.md` (standalone).
  - **Standalone path**: `daas-doc/indicators-collections/<collection>.md` (sibling to `<collection>.csv`).
  - **Nested path** (when invoked inside `fd-daas-workflow-creator`): `daas-doc/<workflow-name>/indicators-<collection>.md` (sibling to `indicators-<collection>.csv`).
