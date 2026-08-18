# Indicator, Frequency & Confidence Rubric

This reference guides the inference steps (Step 4 frequency + confidence, Step 5
indicator proposals). The goal is **honest, conservative inference**: when a
signal is missing, lower the score and write a `note` - don't guess.

## 1. Frequency keyword map

Infer `frequency` from the function name + docstring + parameter names. First
match wins (check realtime/intraday before daily).

| frequency | keywords (CN / EN) |
|---|---|
| `realtime` | 实时, real_time, realtime, tick, 分笔, live, snapshot-realtime |
| `intraday` | 分钟, intraday, minute, 分钟线, 1min, 5min, 15min, 分时 |
| `daily` | 日, daily, 日k, 日线, 日行情, historical(price), 每日 |
| `weekly` | 周, weekly, 周k |
| `monthly` | 月, monthly, 月度, 月报 |
| `quarterly` | 季, quarterly, 季度, 季报 |
| `annual` | 年, annual, yearly, 年度, 年报 |
| `irregular` | (default when nothing matches) |

If the function returns a snapshot with no time axis (e.g. `list_countries`),
use `irregular` and note "snapshot, no time series".

## 2. Confidence rubric (0..1)

`confidence` is a weighted sum of 5 dimensions. Score each dimension 0 / 0.5 / 1
(or interpolate), multiply by its weight, sum, round to 2 decimals. Always write
`confidence_reasoning` as a short string citing each dimension's score.

| dimension | weight | 1.0 | 0.5 | 0.0 |
|---|---|---|---|---|
| `provenance_officialness` | 0.30 | 官方机构/交易所 (stats.gov.cn, SEC, exchange, 央行) | 知名聚合器 (akshare, yfinance, polygon) | 来源不明 / 爬虫易碎 / 第三方未署名 |
| `doc_quality` | 0.25 | docstring + 参数说明 + 返回字段说明齐全 | 有 docstring 但缺字段或参数说明 | 无 docstring |
| `freshness_signal` | 0.20 | frequency 明确且来自官方源 (realtime/daily/月度官方) | frequency 可推断但非官方 / 偶尔中断 | frequency 未知 / irregular / 已停止更新 |
| `api_stability` | 0.15 | 有 type hints + 稳定签名 + 非废弃 | 部分 hints / 签名可变 / 未标版本 | 废弃标记 / 无 hints / 签名混乱 |
| `keyless_access` | 0.10 | 无需 API key | 需 key 但免费易获取 | 需付费/企业 key |

**Example**: official stats bureau source, good docstring with fields, monthly
official frequency, partial type hints, keyless ->
`0.30*1 + 0.25*1 + 0.20*1 + 0.15*0.5 + 0.10*1 = 0.875 -> 0.88`.

**Example**: unknown aggregator, minimal docstring, daily but flaky, no hints, keyless ->
`0.30*0 + 0.25*0.5 + 0.20*0.5 + 0.15*0 + 0.10*1 = 0.275 -> 0.28`.

## 3. Indicator proposal rules

### Which columns get proposals

Only **numeric time-series metric** columns with a date/index axis get
`proposed_indicator_rules`. Concretely:

- A `date` / `datetime` / time column -> `indicator_match: "not_a_metric"` (it's the
  axis). No proposals.
- An identifier column (`code`, `ticker`, `country`, `symbol`, `name`) ->
  `not_a_metric`. No proposals.
- A text/categorical column -> `not_a_metric`. No proposals.
- A numeric column that varies over time (price, rate, index, volume, GDP, CPI) ->
  gets proposals. Set `indicator_match`:
  - `"existing_metric"` if daas already has indicator_rules whose
    `value_column` matches this field's concept (e.g. `Close` -> existing price
    indicators). Proposals here will mostly `dedup_status: "exists"`.
  - `"candidate_new_metric"` if the field is a metric whose **concept** is absent
    from daas today (e.g. GDP, CPI, population - the existing indicators are all
    price/return technicals on a few US tickers). Still propose standard ops, but
    mark every proposal `dedup_status: "new_concept"` and write an
    `indicator_note` describing the concept (e.g. "CPI 同比 - 宏观通胀指标").

### Which ops to propose (pick relevant, not all)

| field flavor | propose |
|---|---|
| price-like (close/open/high/low/price) | `sma`(5,10,20), `ema`(12), `rsi`(14), `pct_change`, `rolling_std`(20), `rolling_min/max`(20) |
| macro flow / rate (CPI, GDP growth, unemployment) | `sma`(12), `pct_change`, `zscore`(12), `diff` |
| snapshot / stock (inventory, balance) | `level` only |
| ratio fields | `level`, `pct_change` |

Don't over-propose: 2-5 rules per metric column is plenty. Each rule needs a
sensible `params` (e.g. `{"window": 12}` for sma on monthly macro).

### Naming convention

`name` = `indicator_name` = `<SOURCE>_<func>_<field>_<op><window>` (lowercase,
underscores). Example: `tiny_econ_get_cpi_series_cpi_yoy_sma12`.
`source_table` = `scraw_<source>_<func_slug>` where func_slug strips non-alnum.

### Dedup (against `existing.json.indicator_names`)

For each proposal, set `dedup_status`:

- `"exists"` - the exact `indicator_name` is already in daas. Skip on import
  (import_descriptor.py does this). Don't duplicate.
- `"new"` - a new computed series on a known concept (will be inserted on import).
- `"new_concept"` - a new computed series on a brand-new metric concept (also
  inserted on import, but flagged so the user can review the concept).

Also consult `existing.json.existing_value_op_pairs` - if a `(value_column, op)`
pair already exists for this source's field concept, prefer `"exists"`.

## 4. Entity matching

For each function, list the `entity_type`(s) it covers and the identifier shape.
Set `matched_existing`:

- `true` if `existing.json.entity_sample[entity_type]` is non-empty AND the
  identifier shape is plausibly the same space (e.g. country -> ISO alpha-2, and
  daas already has 60 countries).
- `false` otherwise, with a `note` (e.g. "daas has no `crypto` entity type yet" or
  "identifier is exchange-specific code, no matches in daas.entities").

`matched_existing=false` entities are surfaced by `import_descriptor.py` for
manual linking - they are NOT auto-created.
