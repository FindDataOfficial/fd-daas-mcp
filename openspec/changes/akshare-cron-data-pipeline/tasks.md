## 1. Catalog module (`mcp/akshare-mcp/datasets.py`)

- [ ] 1.1 Define the `AkshareDataset` dataclass with fields `name`, `akshare_function`, `default_params_json`, `table`, `upsert_keys`, `cron`, `timezone`, `description`, `tmd_need`; add `__all__ = ["AkshareDataset", "ALL_DATASETS", "get_dataset"]`.
- [ ] 1.2 Populate `ALL_DATASETS` with one entry per `t.md` category, using the akshare functions identified in `design.md`: `stock_zh_a_hist` (沪深日行情), `stock_sse_summary`+`stock_szse_summary` (成交概况), `stock_szse_sector_summary` (行业估值), `stock_zh_ah_spot_em` (AH比价), `stock_qbzf_em` (增发), `stock_pg_em` (配股), `stock_dzjy_mrmx` (大宗交易), `stock_individual_info_em` (基本信息), `stock_share_change_cninfo` (股本变动), `stock_gpzy_pledge_ratio_em` (股权质押), `stock_ggcg_em` (高管持股), `stock_fhps_em` (分红), `stock_hk_hist` (港股日行情), `stock_individual_basic_info_hk_xq` (港股基本信息), `stock_hk_fhpx_detail_ths` (港股公司行为), `stock_research_report_em` (券商研报), `stock_profit_forecast_em` (盈利预测), `stock_zygc_em` (主营构成).
- [ ] 1.3 Add `get_dataset(name)` returning the matching entry or raising `KeyError`.
- [ ] 1.4 Validate at import: every `table` matches `^scraw_[a-z0-9_]+$`, every `name` is unique, every `cron` is 5-field, every `upsert_keys` is a non-empty list of valid identifiers. Raise `ValueError` with the offending entry if any check fails.
- [ ] 1.5 For per-symbol functions (`stock_zh_a_hist`, `stock_individual_info_em`, etc.), set `default_params_json` to a representative single symbol for the smoke test and document (in a module docstring) that a real daily job iterates `mcp/akshare-mcp/watchlist.txt` — to be confirmed with the user at apply time (see design Open Questions).
- [ ] 1.6 Confirm the module imports in a fresh process with no network and does not import `akshare`.

## 2. Fetcher bridge (`mcp/akshare-mcp/fetch_to_store.py`)

- [ ] 2.1 Parse CLI args `--name`, `--params` (JSON string), `--table`, `--keys` (comma-separated); fail fast with a clear message if any is missing.
- [ ] 2.2 Resolve the `akshare-mcp` launch command from `.mcp.json` (read `mcp/.mcp.json` or root `.mcp.json`); allow override via `AKSHARE_MCP_COMMAND` env.
- [ ] 2.3 Resolve `DAAS_DATABASE_URL`; resolve relative `sqlite:///` against the repo root (mirror `process-mcp`'s resolution); exit with a clear error if unset.
- [ ] 2.4 Connect to `akshare-mcp` via `fastmcp.Client` (subprocess transport, the resolved launch command) and call `call_akshare_function(name=..., params_json=...)`; convert the returned records to a `pandas.DataFrame`.
- [ ] 2.5 `CREATE TABLE IF NOT EXISTS <table>` with column names from the DataFrame and types inferred from the first non-null value; `CREATE UNIQUE INDEX IF NOT EXISTS` on the `--keys` columns.
- [ ] 2.6 Detect columns in the DataFrame not present in the table and `ALTER TABLE ... ADD COLUMN` (inferred type, default NULL) before upserting.
- [ ] 2.7 Upsert each row via `INSERT ... ON CONFLICT(<keys>) DO UPDATE SET <non-key cols>`; commit once per run.
- [ ] 2.8 Print a JSON summary `{"status":"completed","dataset":...,"table":...,"rows_upserted":N}` on success (exit 0); on any failure print `{"status":"failed",...,"error":<msg>}` (exit non-zero) and roll back / skip commit — no unhandled exception.

## 3. Cron-wiring helper (`mcp/akshare-mcp/register_cron.py`)

- [ ] 3.1 Resolve the `cron-mcp` launch command from `.mcp.json` (override via `CRON_MCP_COMMAND`).
- [ ] 3.2 Connect to `cron-mcp` via `fastmcp.Client` and wrap the calls used: `list_db_tasks`, `create_task`, `update_task`, `delete_task`, `list_schedules`, `create_schedule`, `delete_schedule`, `run_now`.
- [ ] 3.3 Build each task `command` as `uv run --directory <abs_repo>/mcp/akshare-mcp python fetch_to_store.py --name <fn> --params '<json>' --table <table> --keys <cols>` (absolute path computed from `Path(__file__).resolve().parents[1]`).
- [ ] 3.4 Implement idempotent wiring per entry: if task `akshare_<name>` exists → `update_task` (command); else `create_task`. If schedule `akshare_<name>` exists → update its `cron`/`timezone` via delete+recreate only if changed, preserving `enabled` and `id` where possible (cron-mcp has no `update_schedule`, so fetch existing `enabled`/`prompt`/`agent` and recreate with the same values if a cron change is needed); else `create_schedule(name, cron, task, timezone="Asia/Shanghai")`.
- [ ] 3.5 Implement `--dry-run` (print planned commands + crons, call no mutating tool), `--only <name>` (process one entry), `--unregister` (delete schedule then task per entry), `--run <name>` (after wiring, call `run_now` and include the execution result).
- [ ] 3.6 Print a JSON summary `{"created":[...],"updated":[...],"skipped":[...],"failed":[...]}` at the end.

## 4. Smoke test (`mcp/akshare-mcp/selfcheck.py`)

- [ ] 4.1 `--no-network` mode: import `datasets`, assert every `t.md` category is represented, assert slug/cron/uniqueness validators pass, assert CLI parsing in `fetch_to_store.py` rejects missing args.
- [ ] 4.2 Live mode (gated behind `AKSHARE_LIVE=1`): run `fetch_to_store.py` against `stock_individual_info_em` for one symbol into a temp `scraw__selfcheck` table; assert rows inserted; re-run and assert row count unchanged (idempotent); inject a synthetic new column in a second mock record and assert `ALTER TABLE` appended it.
- [ ] 4.3 Assert a forced akshare error produces `status="failed"` JSON and a non-zero exit (mock the `fastmcp.Client` call).

## 5. Wire datasets and verify end-to-end

- [ ] 5.1 Run `uv run --directory mcp/akshare-mcp python register_cron.py --dry-run` and review the planned tasks + cron expressions against `design.md`'s cadence table.
- [ ] 5.2 Run `uv run --directory mcp/akshare-mcp python register_cron.py` to create all tasks + schedules.
- [ ] 5.3 Via `cron-mcp`, call `list_schedules` and confirm every entry has the correct `cron`, `task`, and `timezone="Asia/Shanghai"`.
- [ ] 5.4 Trigger one fetch with `register_cron.py --run ashare-daily` (or `cron-mcp.run_now`); confirm `scraw_ashare_daily` has rows via `dashboard-mcp.query_table(database="daas", table="scraw_ashare_daily")`.
- [ ] 5.5 Verify idempotency: re-run `register_cron.py` and confirm the summary reports `updated` (not `created`) and no errors.
- [ ] 5.6 Verify cleanup: `register_cron.py --unregister --only <name>` removes that task + schedule and leaves the `scraw_*` table intact.

## 6. Documentation

- [ ] 6.1 Update `CLAUDE.md` `mcp/akshare-mcp/` section: add `datasets.py`, `fetch_to_store.py`, `register_cron.py`, the selfcheck command, and a note pointing to `design.md` for the full `t.md → akshare function` mapping.
- [ ] 6.2 Add a short `mcp/akshare-mcp/README.md` section describing the two wiring paths: (a) helper (`register_cron.py`) and (b) manual `create_task` + `create_schedule` by hand — with one concrete worked example.
- [ ] 6.3 Note the relationship to the `add-cron-mcp-data-fetch` change: today's shell-task wiring is the pragmatic path; when `data_job` lands, catalog entries migrate 1:1 to `create_data_job` + `create_schedule(data_job=...)`.
