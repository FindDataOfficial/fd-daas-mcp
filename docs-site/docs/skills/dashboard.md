# fd-daas-dashboard (and -creator)

Two skills cover dashboards: **`fd-daas-dashboard`** to *find/use* an existing
dashboard, and **`fd-daas-dashboard-creator`** to *build* a new one. Both are
read/write over the `dashboards` registry table; neither uses MCP tools
(`sqlite3` + the `register_dashboard.py` script).

## fd-daas-dashboard - find & inspect (read-only)

Use this when you want to **use or find** an already-built dashboard.

**Triggers:** "我们有哪些看板", "打开之前那个看板", "show me the BYD dashboard",
"leaders 看板里是什么数据", "有没有关于比特币的看板", "what data backs this
dashboard" - any "dashboard / 看板" + "open / find / list / show".

**What it does:**

- List every dashboard.
- Search by keyword (name / intro / source table).
- Show a dashboard's introduction + data lineage + entity/time coverage.
- Open it in the browser.
- Query the rows backing it.

It is **read-only** over the `dashboards` registry - it lists, describes,
opens, and queries backing data, nothing more.

## fd-daas-dashboard-creator - build (write)

Use this when you want to **visualize** daas data as a dashboard.

**Triggers:** "给这些指标做一个看板", "build a dashboard for these indicators",
"画一个图看看这个 scraw 表", "visualize this series", "做个图表" - any daas
data + "dashboard / chart / visualize / 看板 / 图表".

**What it does:**

1. Proposes a name + introduction + structure.
2. Validates the source data.
3. Builds a **single standalone HTML file** with ECharts and interactive entity
   + time filters.
4. Offers to open it, iterates on changes.
5. **Registers** the dashboard in the `dashboards` DB table (which regenerates
   the charts index at `dashboards/index.html` + `daas.md`).
6. Writes a companion instruction md under `daas-doc/dashboard/<name>-dashboard.md`.

It does **not** open/find existing dashboards (use `fd-daas-dashboard`) or
create indicators (use `fd-daas-indicators-creator`).

## The `dashboards` table

```bash
sqlite3 daas.db "SELECT slug, name, file_url FROM dashboards LIMIT 5;"
```

Columns: `slug`, `name`, `intro`, `source_tables`, `entity_coverage`,
`time_range`, `refresh_cadence`, `chart_config`, `file_path`, `file_url`.

## MCP equivalents (dashboard group)

```text
dashboard_register(slug=..., name=..., intro=..., source_tables=..., refresh_cadence=..., file_path=..., file_url=...)
dashboard_list()
dashboard_search(keyword="momentum")
dashboard_get(slug="my-momentum")
dashboard_update(slug="my-momentum", intro="...")
dashboard_delete(slug="my-momentum")
```

## Share it

Once built, [share the dashboard](../examples/share-dashboard.md) over WiFi or
a tunnel.
