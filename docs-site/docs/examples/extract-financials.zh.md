# 提取并分析财报

拉取一份财报并在其上计算指标 -- 很多指标已预置。DAAS 支持 SEC EDGAR（美国）、EDINET（日本）、DART（韩国），以及本地 PDF/文档提取与语义搜索。

## 1. 解析财报源

每个财报源有一个 dispatch 前缀：

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve edgar_get_filing
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve edinet_list_documents
```

它们打印精确的 Python import + 调用形状（如 `edgar.Filing(filing_id)`、`edinet_tools.Entity(code).documents`）。

## 2. 获取财报（技能）

在 Claude Code 里：

> 获取 Apple 最新的 10-K（来自 EDGAR）并持久化。

`fd-daas-fetch-data` 技能解析 AAPL -> `edgar` 标识符，调用 `edgar` 库，把结构化行持久化到 `scraw_<slug>` 表（和/或 LLM 抽取的 section 到 `process_results`）。

## 3. 抽取结构化 section（LLM）

对自由文本财报，DAAS 通过一条 `llm` 规则（`rules.rule_type='llm'`、`target='rows'`）抽取结构化记录到 `process_results`。`fd-daas-rules-creator` 技能编写规则；`daas_run_rule` 运行。

```text
daas_test_rule(name="extract_revenue_segments")   # 干跑样本
daas_run_rule(name="extract_revenue_segments")    # 持久化
```

## 4. 导入 PDF/文档做语义搜索

若有本地 PDF（年报、招股书），用 `fd-daas-pdf` 技能（由 `pdf` MCP 组支撑）导入：

```text
pdf_ingest_document(file_path="/path/to/report.pdf")
pdf_search_documents(query="revenue concentration by segment", top_k=5)
```

它会分块 + 嵌入（sqlite-vec）到 `daas.db`（`pdf_documents` / `pdf_chunks` / `pdf_chunks_vec`），返回带页码的排名分块。

## 5. 在其上计算指标

财报数据进 `scraw_<slug>` 表后，像任何序列一样计算指标：

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py <indicator_name>
```

预置算子：`sma`、`ema`、`rsi`、`pct_change`、`log_return`、`diff`、`rolling_std`、`rolling_min`、`rolling_max`、`zscore`、`ratio`、`level`。用 `daas_create_indicator`（或 `fd-daas-indicators-creator` 技能）新建一条指标规则并运行。

## 6. 放进研究

把财报抽取 + 指标 + 看板绑成一个研究：

```text
research_create(name="aapl-10k-analysis", ...)
research_generate_report(name="aapl-10k-analysis")
```

见 [创建研究](create-research.md)。

## 数据源覆盖

| 源 | 前缀 | 地区 |
| --- | --- | --- |
| SEC EDGAR | `edgar_` | 美国 |
| EDINET | `edinet_` | 日本 |
| DART | `dartlab_`（Python 3.12） | 韩国 |

!!! note "dartlab 需要 Python 3.12"
    用 `uv run --python 3.12 --with dartlab ...` 运行 dartlab（非根依赖）。
