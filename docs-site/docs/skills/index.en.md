# Skills

DAAS skills live in `.claude/skills/` and are invoked by Claude Code. They call
Python data libraries directly and read/write `daas.db` via `sqlite3` - no MCP
round-trip. There are two families.

## `fd-daas-*` - data skills

The data-fetch, indicator, collection, research, and dashboard skills.

| Skill | What it does |
| --- | --- |
| [`fd-daas-brainstorm`](brainstorm.md) | Clarify a fuzzy research goal into a plan doc. |
| [`fd-daas-research`](research.md) | Full pipeline: analyze -> collections -> indicators -> dashboard -> bundle + report. |
| `fd-daas-based-data-fetch` | Core resolve -> fetch -> persist. |
| `fd-daas-fetch-data` | Entity -> coverage -> indicator workflow. |
| `fd-daas-dashboard` / [`-creator`](dashboard.md) | Browse / build standalone HTML dashboards. |
| `fd-daas-entities-collection` / `-creator` | Entity collections + rules. |
| `fd-daas-indicators-collection-creator` | Indicator collections + export. |
| `fd-daas-indicators-creator` | Persist a series to `scraw_<slug>`. |
| `fd-daas-rules-creator` | Author a unified rule (json/script/position/llm). |
| `fd-daas-pdf` | Local PDF/text semantic vector search. |
| `fd-daas-scrapling-official` | Web scraping with anti-bot bypass (Scrapling library). |
| `fd-datasource-akshare` | A-share OHLCV/fundamentals via the external `scraw-akshare` Scrapy project. |
| `fd-daas-skill-creator` / `fd-daas-skill-review` | Create/inspect + review daas skills. |

## `fd-coding-*` - infra & builder skills

| Skill | What it does |
| --- | --- |
| [`fd-coding-bore-tunnel`](sharing.md) / [`fd-coding-cloudflare-tunnel`](sharing.md) | Expose a local service (dashboard/docs) to the internet. |
| `fd-coding-skill-creator` | The generic skill-creation loop (draft -> eval -> iterate). |
| `fd-coding-daas-datasource-builder` (+ `-workspace`) | Scaffold datasource builder projects. |
| `fd-coding-daas-scraw-builder` | Scaffold `scraw-*` Scrapy projects. |
| `fd-coding-daas-reset-project` | Reset `daas.db` to clean at 3 guarded levels. |
| `fd-coding-documents-builder` | Scaffold a MkDocs Material docs-site (like this one). |
| `fd-coding-documents-add` | Add a page to an existing docs-site. |

## Emphasized skills

If you learn only four skills, learn these - they cover the most common
end-to-end journeys:

1. [**fd-daas-brainstorm**](brainstorm.md) - turn a vague idea into a plan.
2. [**fd-daas-research**](research.md) - run the full study.
3. [**fd-daas-dashboard**](dashboard.md) - see and build dashboards.
4. [**Sharing Dashboards**](sharing.md) - publish over WiFi/tunnel.

!!! tip "Skills vs. MCP"
    Skills are the simpler, offline-friendly path. The same capabilities are
    available as MCP tools (`<group>_<tool>`) on the consolidated `fd-daas-mcp`
    server - see [MCP Tools](../mcp/index.md).
