# 添加个人数据源

DAAS 的设计让你能接入自己的数据 -- 一个**网站**、一份**文档**、或一个**数据库** -- 并像内置源一样查询。三条路径。

## 路径 A：一个网站（抓取）

用 `fd-daas-scrapling-official` 技能，它直接驱动 [Scrapling](https://github.com/D4Vinci/Scrapling) 库（反爬绕过、CSS/XPath 选择器）。在 Claude Code 里：

> 抓取 <https://example.com/markets> 的每日价格表并持久化到 daas.db。

技能会抓取页面、抽取表格、通过 `scripts/upsert.py` 把行持久化到 `scraw_<slug>` 表（写入前先备份 `daas.db`）。此后它和任何源表一样 -- 计算指标、加入集合、放进研究。

!!! note "这是 Scrapling *库*，不是已移除的 MCP 组"
    `fd-daas-scrapling-official` 直接驱动 Scrapling。旧的 `scrapling`/`firecrawl`/`massive` MCP 组已移除 -- 不要引用。

若是重型、周期性爬取，用 `fd-coding-daas-scraw-builder` 搭一个完整 Scrapy 项目（scrapy + scrapy-redis + scrapyd + scrapyd-web）。

## 路径 B：一份文档（PDF / 文本）

用 `fd-daas-pdf` 技能 / `pdf` MCP 组导入本地 PDF 或文本：

```text
pdf_ingest_document(file_path="/path/to/report.pdf")
# 或纯文本：
pdf_ingest_text(text="...", name="my-notes")
pdf_search_documents(query="主要风险有哪些", top_k=5)
```

文档被分块 + 嵌入（sqlite-vec）到 `daas.db`，可语义搜索。要从文本做结构化抽取，用 `fd-daas-rules-creator` 编写一条 `llm` 规则并运行 `daas_run_rule`（结果落到 `process_results`）。

## 路径 C：一个数据库（或任何 Python 可调用的源）

注册一个数据源并关联到实体，然后通过 dispatch 层获取。

```text
daas_create_datasource(name="mydb", label="My Internal DB", url="postgresql://...")
daas_link_entity_datasource(entity_id=123, source_name="mydb", identifier_in_source="AAPL")
```

若你的源有 Python 库，在 `.claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py` 加一个 dispatch 前缀映射（仿照现有 `akshare_`/`yfinance_`/... 条目），然后解析 + 获取：

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve mydb_<func>
```

用 `scripts/upsert.py` 持久化到 `scraw_<slug>` 表。

## 注册函数/列（可选，用于目录浏览）

要让你的源出现在 MCP 目录浏览中，注册其函数和列：

```text
daas_create_datasource(...)
daas_add_form(source_name="mydb", form_type="table")     # 或 form/section 结构
daas_add_section(form_id=..., section_name="daily_prices", instruction="...")
```

之后 `daas_search_functions`、`daas_search_datasources`、`daas_get_entity_coverage` 会包含你的源。

## 下一步

数据进 `daas.db` 后，其余都一样：计算指标（[浏览指标](browse-indicators.md)）、构建 [集合](create-collections.md)、或做一个 [研究](create-research.md)。
