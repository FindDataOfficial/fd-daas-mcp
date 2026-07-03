## ADDED Requirements

### Requirement: A curated catalog maps every `t.md` data need to an `akshare-mcp` function

The system SHALL provide a single Python module `mcp/akshare-mcp/datasets.py` that enumerates one `AkshareDataset` entry per `t.md` data need, mapping it to a concrete `akshare-mcp` function (the `name` argument to `call_akshare_function`). The catalog is the single source of truth that both the fetcher and the cron-wiring helper read from.

#### Scenario: Catalog covers all `t.md` categories

- **WHEN** the catalog module is imported
- **THEN** it SHALL contain at least one entry for each of these `t.md` categories: 沪深股票日行情, 交易市场日度成交概况, 行业估值信息, AH股比价, 增发, 配股, 大宗交易, 股票基本信息, 公司股本变动, 股权质押冻结, 高管持股变动, 股票分红信息, 港股日行情, 港股基本信息, 港股公司行为, 券商研报, 盈利预测/一致预期, 主营构成
- **AND** each entry's `akshare_function` SHALL be a name present in the akshare registry (e.g. `stock_zh_a_hist`, `stock_dzjy_mrmx`, `stock_zh_ah_spot_em`, `stock_gpzy_pledge_ratio_em`, `stock_hk_hist`, `stock_research_report_em`, `stock_profit_forecast_em`, `stock_zygc_em`)

#### Scenario: Catalog is importable without network access

- **WHEN** `mcp/akshare-mcp/datasets.py` is imported in a fresh process with no network
- **THEN** the import SHALL succeed and expose the dataset list
- **AND** it SHALL NOT import `akshare` or call any network function at module load

### Requirement: Each catalog entry declares the fields needed to fetch, store, and schedule

Each `AkshareDataset` SHALL declare: `name` (kebab-case unique id), `akshare_function`, `default_params_json` (str), `table` (the `scraw_<slug>` target), `upsert_keys` (list of column names), `cron` (5-field cron expression), `description`, and the `t.md` need it satisfies.

#### Scenario: Entry fields are complete and well-formed

- **WHEN** any catalog entry is inspected
- **THEN** `table` SHALL match `^scraw_[a-z0-9_]+$`
- **AND** `upsert_keys` SHALL be a non-empty list of valid Python identifiers
- **AND** `cron` SHALL be a 5-field cron expression parseable by APScheduler `CronTrigger`
- **AND** `name` SHALL be unique across the catalog

#### Scenario: Default params cover required akshare parameters

- **WHEN** an entry's `default_params_json` is parsed
- **THEN** it SHALL include values for every parameter the akshare registry marks `required=True` for that function
- **AND** it MAY include optional parameters (e.g. `period="daily"`, `adjust="qfq"`)

### Requirement: The catalog exposes lookup helpers

The module SHALL expose `ALL_DATASETS` (a list) and a `get_dataset(name)` function returning the matching entry or raising `KeyError`.

#### Scenario: Look up a dataset by name

- **WHEN** `get_dataset("ashare-daily")` is called with a name that exists
- **THEN** the matching `AkshareDataset` is returned
- **WHEN** `get_dataset("nope")` is called with a name that does not exist
- **THEN** `KeyError` is raised

#### Scenario: Iterate all datasets

- **WHEN** a caller iterates `ALL_DATASETS`
- **THEN** every `t.md` category is represented at least once
- **AND** each entry is an `AkshareDataset` instance with all required fields populated
