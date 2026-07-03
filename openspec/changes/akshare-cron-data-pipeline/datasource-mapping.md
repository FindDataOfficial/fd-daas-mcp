# akshare-mcp Datasource → Function Mapping

Reference for the `akshare-cron-data-pipeline` change. Maps each `t.md` data need to a concrete `akshare-mcp` function (`call_akshare_function` name) and the underlying datasource portal. Source URLs and parameter signatures come from the akshare registry at `akshare-agent-harness/cli_anything/akshare/metadata/registry.json`.

All functions below are callable via the `akshare-mcp` tool `call_akshare_function(name=..., params_json=...)`, or equivalently via the harness CLI `uv run cli-anything-akshare call <name> k=v ...`.

---

## Grouped by datasource

### 新浪财经 (sina.com)

| t.md need | function | required params | source |
|---|---|---|---|
| 沪深日行情 | `stock_zh_a_daily` | `symbol="sh600006"` | https://finance.sina.com.cn/realstock/company/sh600006/nc.shtml |
| 港股日行情 | `stock_hk_daily` | `symbol="00700"`, `adjust="qfq"` | http://stock.finance.sina.com.cn/hkstock/quotes/01336.html |
| 增发 | `stock_add_stock` | `symbol="600004"` | https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_AddStock/stockid/600004.phtml |

### 东方财富 (eastmoney)

| t.md need | function | required params | source |
|---|---|---|---|
| 沪深日行情 | `stock_zh_a_hist` | `symbol="000001"`, `period="daily"`, `start_date`, `end_date` | https://quote.eastmoney.com/concept/sh603777.html |
| AH比价 (实时) | `stock_zh_ah_spot_em` | — | https://quote.eastmoney.com/center/gridlist.html#ah_comparison |
| 增发 | `stock_qbzf_em` | — | https://data.eastmoney.com/other/gkzf.html |
| 配股 | `stock_pg_em` | — | https://data.eastmoney.com/xg/pg/ |
| 大宗交易-每日明细 | `stock_dzjy_mrmx` | — | https://data.eastmoney.com/dzjy/dzjy_mrmx.html |
| 大宗交易-每日统计 | `stock_dzjy_mrtj` | — | https://data.eastmoney.com/dzjy/dzjy_mrtj.html |
| 股票基本信息 | `stock_individual_info_em` | `symbol="000001"` | http://quote.eastmoney.com/concept/sh603777.html |
| 股权质押-质押比例 | `stock_gpzy_pledge_ratio_em` | — | https://data.eastmoney.com/gpzy/pledgeRatio.aspx |
| 股权质押-明细 | `stock_gpzy_pledge_ratio_detail_em` | — | https://data.eastmoney.com/gpzy/pledgeDetail.aspx |
| 高管持股 | `stock_ggcg_em` | — | http://data.eastmoney.com/executive/gdzjc.html |
| 高管持股-人员明细 | `stock_hold_management_person_em` | — | https://data.eastmoney.com/executive/personinfo.html |
| 分红配送 | `stock_fhps_em` | — | https://data.eastmoney.com/yjfp/ |
| 分红详情 | `stock_fhps_detail_em` | — | https://data.eastmoney.com/yjfp/detail/300073.html |
| 港股日行情 | `stock_hk_hist` | `symbol="00700"`, `period="daily"`, `adjust` | https://quote.eastmoney.com/hk/08367.html |
| 券商研报 | `stock_research_report_em` | — | https://data.eastmoney.com/report/stock.jshtml |
| 盈利预测 | `stock_profit_forecast_em` | — | http://data.eastmoney.com/report/profitforecast.jshtml |
| 主营构成 | `stock_zygc_em` | `symbol="SH688041"` | https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/Index |

### 巨潮资讯 (cninfo)

| t.md need | function | required params | source |
|---|---|---|---|
| 配股 | `stock_allotment_cninfo` | — | http://webapi.cninfo.com.cn/#/dataBrowse |
| 公司股本变动 | `stock_share_change_cninfo` | — | https://webapi.cninfo.com.cn/#/apiDoc |
| 机构推荐评级 | `stock_rank_forecast_cninfo` | — | https://webapi.cninfo.com.cn/#/thematicStatistics |

### 同花顺 (10jqka)

| t.md need | function | required params | source |
|---|---|---|---|
| 港股公司行为/分红 | `stock_hk_fhpx_detail_ths` | `symbol="00700"` | https://stockpage.10jqka.com.cn/HK0700/bonus/ |
| 盈利预测 | `stock_profit_forecast_ths` | — | http://basic.10jqka.com.cn/new/600519/worth.html |

### 雪球 (xueqiu)

| t.md need | function | required params | source |
|---|---|---|---|
| 股票基本信息 | `stock_individual_basic_info_xq` | `symbol="SH601127"` | https://xueqiu.com/snowman/S/SH601127/detail |
| 港股基本信息 | `stock_individual_basic_info_hk_xq` | `symbol="00700"` | https://xueqiu.com/S/00700 |

### 腾讯财经 (tencent)

| t.md need | function | required params | source |
|---|---|---|---|
| AH比价 (实时) | `stock_zh_ah_spot` | — | https://stockapp.finance.qq.com/mstats/ |
| AH比价 (历史) | `stock_zh_ah_daily` | — | https://gu.qq.com/hk02359/gp |

### 交易所 (SSE / SZSE)

| t.md need | function | required params | source |
|---|---|---|---|
| 成交概况-上交所 | `stock_sse_summary` | `date="20250221"` | http://www.sse.com.cn/market/stockdata/statistic/ |
| 成交概况-上交所每日 | `stock_sse_deal_daily` | `date="20250221"` | http://www.sse.com.cn/market/stockdata/overview/day/ |
| 成交概况-深交所 | `stock_szse_summary` | `date="20250221"` | http://www.szse.cn/market/overview/index.html |
| 行业估值/行业成交 | `stock_szse_sector_summary` | — | http://docs.static.szse.cn/ |

---

## Sina example — full call

`stock_zh_a_daily` (新浪财经 沪深日行情). Returns columns: `时间, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 最新价`.

**Via `akshare-mcp`:**

```
call_akshare_function(
  name="stock_zh_a_daily",
  params_json='{"symbol":"sh600006","start_time":"09:00:00","end_time":"15:40:00"}'
)
```

| param | type | required | notes |
|---|---|---|---|
| `symbol` | str | yes | prefix `sh`/`sz`/`bj`, e.g. `"sh600006"` |
| `start_time` | str | no | `"09:00:00"`; defaults to all history |
| `end_time` | str | no | `"15:40:00"` |

**Via the harness CLI (equivalent):**

```bash
uv run cli-anything-akshare call stock_zh_a_daily symbol=sh600006 start_time=09:00:00 end_time=15:40:00
```

---

## Notes & gaps

- **萝卜投研 (datayes / `robo.datayes.com`)**: akshare does **not** expose a 萝卜投研 endpoint (paid API). The closest free equivalents for 券商研报 / 一致预期 / 业绩预测 are `stock_research_report_em` + `stock_profit_forecast_em` (eastmoney) and `stock_profit_forecast_ths` (10jqka) + `stock_rank_forecast_cninfo` (cninfo 机构推荐评级).
- **同花顺价值分析-业绩预测详表**: covered by `stock_profit_forecast_ths`.
- For per-symbol functions (`stock_zh_a_hist`, `stock_zh_a_daily`, `stock_individual_info_em`, `stock_hk_hist`, etc.), a real daily cron job iterates a symbol list — see `design.md` Open Questions (watchlist vs. one-task-per-symbol).
- Each function's full parameter list and output columns live in the registry (`registry.json`); query live via `akshare-mcp` `search_functions` / `get_function_info` (or `list_functions`).
