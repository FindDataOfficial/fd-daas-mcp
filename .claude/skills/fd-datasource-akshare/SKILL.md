---
name: fd-datasource-akshare
description: Fetch A-share (A股) stock market data (OHLCV and fundamentals) using the scraw-akshare project. Trigger whenever the user asks to fetch/download stock data, run spiders, query Chinese stock market, get 股票数据, 行情数据, 财务报表, or mentions any akshare-related data fetching. This skill knows all spider commands, CLI options, DB schema, and known issues — consult it before running any fetch command.
license: MIT
compatibility: Requires the scraw-akshare project (`$SCRAW_AKSHARE_DIR`) and PostgreSQL (`$ASTOCK_DATABASE_URL`), both defined in the repo-root `.env`
metadata:
  author: project
  version: "1.0"
---

# scraw-akshare Skill

This skill helps you fetch A-share (沪深A股) stock data into the local PostgreSQL database.

## Two Ways to Fetch

### 1. CLI (`scraw-akshare fetch`) — OHLCV only, synchronous

```bash
# Must unset proxy env vars — akshare calls eastmoney.com directly
export http_proxy= https_proxy=

# Init DB (creates all 6 tables, idempotent)
scraw-akshare init-db

# Fetch specific stocks
scraw-akshare fetch --symbols 600000,000001
scraw-akshare fetch --symbols 600000 --period weekly --adjust hfq
scraw-akshare fetch --symbols 600000 --start-date 20240101 --end-date 20240630

# Fetch all A-shares (~5000 stocks)
scraw-akshare fetch --all
scraw-akshare fetch --all --period monthly --adjust qfq

# Fetch from a file (one symbol per line)
scraw-akshare fetch --symbols-file my_codes.txt
```

Parameters:
- `--symbols` comma-separated stock codes (e.g., `600000,000001`)
- `--all` fetch all A-share stocks
- `--period daily|weekly|monthly` (default: `daily`)
- `--adjust qfq|hfq|none` — qfq=前复权, hfq=后复权, none=不复权 (default: `qfq`)
- `--start-date YYYYMMDD` (optional)
- `--end-date YYYYMMDD` (optional)
- `--symbols-file PATH` (CLI only, not Scrapy)

### 2. Scrapy Spider — supports both OHLCV and fundamentals

```bash
# OHLCV spider
scrapy crawl astock -a symbols=600000,000001
scrapy crawl astock -a all=1 -a period=weekly -a adjust=hfq
scrapy crawl astock -a symbols=600000 -a start_date=20240101 -a end_date=20240630

# Fundamentals spider (financial indicators, 3 financial statements)
scrapy crawl fundamentals -a symbols=600000
scrapy crawl fundamentals -a all=1 -a start_year=2018
scrapy crawl fundamentals -a symbols=600000 -a date=20251030
```

Fundamentals spider parameters:
- `-a symbols` comma-separated stock codes
- `-a all=1` fetch all A-shares
- `-a start_year` year to start financial indicators from (default: `2020`)
- `-a date` YYYYMMDD for performance reports (业绩报表/快报/预告)

## What Data Gets Fetched

### Per stock (always fetched in fundamentals spider):
1. **Financial indicators** (财务指标) — 40+ metrics: eps, bvps, roe, gross_margin, debt_ratio, etc. → `astock_financial_indicators`
2. **Profit sheet** (利润表) — revenue, costs, net profit, eps, etc. → `astock_profit_sheet`
3. **Balance sheet** (资产负债表) — assets, liabilities, equity → `astock_balance_sheet`
4. **Cash flow** (现金流量表) — operating/investing/financing cash flow → `astock_cash_flow`

### If `date` is provided (fetched once for all stocks):
5. **Performance reports** (业绩报表, yjbb) → `astock_performance_report` (type=`yjbb`)
6. **Performance alerts** (业绩预告, yjyg) → `astock_performance_report` (type=`yjyg`)
7. **Performance express** (业绩快报, yjkb) → `astock_performance_report` (type=`yjkb`)

## Database Schema

- **URL**: read from `$ASTOCK_DATABASE_URL` (repo-root `.env`)
- **Default** (set this in `.env` if unset): `postgresql+psycopg2://postgres:postgres@localhost:5432/finddata`
- **Env override**: `ASTOCK_DATABASE_URL`

| Table | Content | Unique Key |
|-------|---------|-----------|
| `astock_daily` | OHLCV bars | (symbol, trade_date, period, adjust) |
| `astock_financial_indicators` | 财务指标 (40 columns) | (symbol, report_date) |
| `astock_profit_sheet` | 利润表 | (symbol, report_date) |
| `astock_balance_sheet` | 资产负债表 | (symbol, report_date) |
| `astock_cash_flow` | 现金流量表 | (symbol, report_date) |
| `astock_performance_report` | 业绩报表/快报/预告 | (symbol, report_date, report_type) |

### Check data
```bash
# Using Python
python3 -c "
from scraw_akshare.database import AstockDatabase
from sqlalchemy import text
db = AstockDatabase()
db.init_db()
with db.engine.connect() as conn:
    rows = conn.execute(text('SELECT count(*) FROM astock_financial_indicators')).fetchall()
    print(f'Financial indicators: {rows[0][0]} rows')
    rows = conn.execute(text('SELECT count(*) FROM astock_daily')).fetchall()
    print(f'OHLCV: {rows[0][0]} rows')
"
```

## Known Issues

### 1. Proxy env vars must be unset
akshare calls eastmoney.com APIs directly. If the user has `http_proxy`/`https_proxy` set, the calls will fail with ProxyError/RemoteDisconnected. Always unset them:
```bash
export http_proxy= https_proxy=
```
Or use one-liner: `env -u http_proxy -u https_proxy scrapy crawl astock ...`

### 2. Three financial statement endpoints are broken in akshare 1.18.64
These three functions crash with `TypeError: 'NoneType' object is not subscriptable` due to an akshare bug (HTML parsing regression):
- `fetch_profit_sheet()` → `ak.stock_profit_sheet_by_report_em`
- `fetch_balance_sheet()` → `ak.stock_balance_sheet_by_report_em`
- `fetch_cash_flow()` → `ak.stock_cash_flow_sheet_by_report_em`

They are wrapped in try/except so the spider continues — they just return empty data.

### 3. Performance reports need a valid date
`stock_yjbb_em` / `stock_yjyg_em` / `stock_yjkb_em` raise TypeError when no data exists for the given date. Wrapped in try/except in the spider. Try dates near quarter end (e.g., `20250331`, `20250630`).

### 4. Column names may change
akshare updates may change Chinese column names. If this happens, the client code will raise `RuntimeError("missing expected columns")` — update the `_COLUMN_MAP` in the relevant `akshare_client*.py` file.

## Common Workflows

> **Prerequisite**: `$SCRAW_AKSHARE_DIR` and `$ASTOCK_DATABASE_URL` live in the
> repo-root `.env`. Load them into the shell first (from the DAAS repo root):
> ```bash
> set -a; source .env; set +a
> ```
> `set -a` exports every var so child processes (`scrapy`, `scraw-akshare`) pick
> up `ASTOCK_DATABASE_URL` too.

### First-time setup
```bash
cd "$SCRAW_AKSHARE_DIR"
export http_proxy= https_proxy=
scraw-akshare init-db
scraw-akshare fetch --symbols 600000,000001
```

### Full fundamentals for one stock
```bash
cd "$SCRAW_AKSHARE_DIR"
export http_proxy= https_proxy=
scrapy crawl fundamentals -a symbols=600000
```

### Fetch all daily data
```bash
cd "$SCRAW_AKSHARE_DIR"
export http_proxy= https_proxy=
scrapy crawl astock -a all=1
```
