# canonical indicators — seed vocabulary

The source of truth for the `canonical_indicators` table in `mcp/daas.db`.
`scripts/setup_indicator_vocabulary.py` parses this file and upserts each row.

**How to extend:** add a row to the table below, re-run `setup_indicator_vocabulary.py`,
then re-run the matcher for the relevant source(s). Only add a canonical name
when a column recurs across sources with the same meaning — don't mint a name
for a one-off column with no cross-source significance.

## Format

A markdown table. The setup script parses every line that starts with `|` and
isn't the separator row (`|---|…`). Fields, in order:

| name | label | unit | semantic_type | category | aliases | description |

- `name` — canonical handle, lowercase with underscores (`close`, `gdp_nominal_usd`)
- `unit` — `currency`, `shares`, `percent`, `ratio`, `count`, `index`, or blank
- `semantic_type` — `price`, `volume`, `ratio`, `count`, `index`, `rate`, or blank
- `category` — `market-data`, `fundamentals`, `macro`, `alternative`
- `aliases` — comma-separated; lowercased on match. Include the Chinese name
  (akshare/cnstats), the yfinance column, the edgar field, and any World Bank
  indicator code where relevant — that's what makes auto-match work across
  English-only and Chinese sources alike.

## Seed table

| name | label | unit | semantic_type | category | aliases | description |
|---|---|---|---|---|---|---|
| open | Opening price | currency | price | market-data | 开盘, 开盘价, Open, price_open | First traded price of the period. |
| high | High price | currency | price | market-data | 最高, 最高价, High, price_high | Highest traded price in the period. |
| low | Low price | currency | price | market-data | 最低, 最低价, Low, price_low | Lowest traded price in the period. |
| close | Closing price | currency | price | market-data | 收盘, 收盘价, Close*, Last, price_close | Last traded price of the period. |
| adj_close | Adjusted close | currency | price | market-data | 复权收盘, adjclose, Adj Close, adjusted_close | Close adjusted for splits and dividends. |
| volume | Trading volume | shares | volume | market-data | 成交量, Vol, Quantity, trading_volume | Number of shares/contracts traded. |
| turnover | Trading turnover | currency | volume | market-data | 成交额, Amount, turnover_value | Total value traded in the period. |
| shares_outstanding | Shares outstanding | shares | count | market-data | 总股本, Shares, outstanding_shares | Total shares currently outstanding. |
| market_cap | Market capitalization | currency | price | market-data | 总市值, 市值, MarketCap, market_capitalization | Share price × shares outstanding. |
| revenue | Revenue | currency | price | fundamentals | 营业收入, 营收, Total Revenue, Sales, total_revenue | Top-line sales for the period. |
| net_income | Net income | currency | price | fundamentals | 净利润, NetIncome, earnings | Bottom-line profit after tax. |
| eps | Earnings per share | currency | ratio | fundamentals | 每股收益, EPS, earnings_per_share | Net income / shares outstanding. |
| book_value_per_share | Book value per share | currency | ratio | fundamentals | 每股净资产, BVPS, book_value | Equity / shares outstanding. |
| total_assets | Total assets | currency | price | fundamentals | 总资产, 资产总计, Total Assets | Sum of all assets on the balance sheet. |
| total_liabilities | Total liabilities | currency | price | fundamentals | 总负债, 负债总计, Total Liabilities | Sum of all liabilities. |
| cash_flow_ops | Cash flow from operations | currency | price | fundamentals | 经营现金流, 经营活动产生的现金流量净额, OCF, CFO | Operating cash flow. |
| pe_ratio | Price-to-earnings ratio | ratio | ratio | fundamentals | 市盈率, PE, P/E, pe_ttm, trailingPE | Share price / EPS. |
| pb_ratio | Price-to-book ratio | ratio | ratio | fundamentals | 市净率, PB, P/B, priceToBook | Share price / book value per share. |
| ps_ratio | Price-to-sales ratio | ratio | ratio | fundamentals | 市销率, PS, P/S, priceToSales | Share price / revenue per share. |
| dividend_yield | Dividend yield | percent | ratio | fundamentals | 股息率, DivYield, yield, dividendYield | Annual dividend / share price. |
| roe | Return on equity | percent | ratio | fundamentals | 净资产收益率, ROE | Net income / equity. |
| roa | Return on assets | percent | ratio | fundamentals | 总资产收益率, ROA | Net income / total assets. |
| debt_to_equity | Debt-to-equity ratio | ratio | ratio | fundamentals | 资产负债率, D/E, debt_equity, debtToEquity | Total debt / equity. |
| gdp_nominal_usd | Nominal GDP | currency | price | macro | 国内生产总值, GDP, gdp_current_usd, NY.GDP.MKTP.CD | Gross domestic product, current USD. |
| gdp_real_growth_pct | Real GDP growth | percent | rate | macro | GDP增长率, GDP growth, gdp_growth, NY.GDP.MKTP.KD.ZG | Annual real GDP growth rate. |
| cpi_level | CPI level | index | index | macro | CPI, 居民消费价格指数, cpi_index, FP.CPI.TOTL | Consumer price index level. |
| cpi_yoy_pct | CPI year-over-year | percent | rate | macro | CPI同比, CPI YoY, cpi_inflation, FP.CPI.TOTL.ZG | CPI inflation, year-over-year. |
| unemployment_rate_pct | Unemployment rate | percent | rate | macro | 失业率, Unemployment, SL.UEM.TOTL.ZS | Share of labor force unemployed. |
| policy_interest_rate | Policy interest rate | percent | rate | macro | 政策利率, Policy Rate, central_bank_rate, central_bank_policy_rate | Central bank policy rate. |
| population | Population | count | count | macro | 人口, Population, SP.POP.TOTL | Total population. |
| m2_supply | M2 money supply | currency | price | macro | M2, 广义货币, money_supply_m2, FM.LBL.MONY.CN | Broad money supply. |
| fx_rate | Exchange rate | ratio | price | macro | 汇率, Exchange Rate, FX, exchange_rate | Domestic currency per 1 USD (or as documented). |
| vix_close | VIX close | index | index | alternative | VIX, 波动率指数, volatility_index | CBOE volatility index close. |
| put_call_ratio | Put-call ratio | ratio | ratio | alternative | PCR, 认沽认购比, put_call | Put volume / call volume. |
| settle_price | Settlement price | currency | price | market-data | 结算价, Settlement, Settle, settlement_price, SettlementPrice | Daily settlement price of a futures contract. |
| open_interest | Open interest | count | count | market-data | 持仓量, 持仓, OpenInterest, open interest, OI | Number of outstanding (unsettled) futures/options contracts. |
| warehouse_stocks | Warehouse stocks | count | count | alternative | 库存, 仓单, WarehouseStocks, warehouse_inventory, inventory | Quantity of a commodity held in registered warehouses (commodity-specific physical units). |
