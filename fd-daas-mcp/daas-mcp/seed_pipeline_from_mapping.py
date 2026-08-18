"""Seed a pipeline_collection from the akshare datasource mapping.

DEPRECATED: the `akshare-mcp` data-fetch upstream was removed when the 11
per-source data-fetch MCPs were replaced by the single concept-based
`fd-open-data-mcp` upstream (see
openspec/changes/replace-datafetch-with-open-data-mcp). Items seeded here use
`source_mcp="akshare-mcp"` + `call_akshare_function` (function-based, does not
map to `fd-open-data-mcp`'s concept-based `read`), so they will fail at
execution ("upstream 'akshare-mcp' not found"). Migrate these cron fetches to
fd-open-data-mcp concept reads (where a binding exists) or to the skill-driven
fetch path (.claude/skills/fd-daas-based-data-fetch, which calls akshare
directly + upserts into scraw_<slug>).

Loads the `t.md` data needs mapped in
`openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md` into a
`pipeline_collection` (default name `akshare-t-md`) and adds one item per
mapped need — each item drives `akshare-mcp.call_akshare_function` on a cron
cadence and upserts into its own `scraw_<slug>` table.

Usage:
  uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py --dry-run
  uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py
  uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py --only ashare-daily
  uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py --unseed

Idempotent on collection name + item name: re-run updates existing items
(via update_pipeline_item, no backfill) and does not duplicate cron-mcp rows.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# make mcp/models + this dir importable
_HERE = Path(__file__).resolve().parent
_MODELS = _HERE.parent / "models"
for p in (str(_MODELS), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pipeline_tools as P  # noqa: E402


@dataclass
class SeedItem:
    name: str
    akshare_function: str
    params: dict = field(default_factory=dict)
    storage_table: str = ""
    upsert_keys: list = field(default_factory=list)
    cron: str = ""
    timezone: str = "Asia/Shanghai"
    tmd_need: str = ""

    def arguments_json(self) -> str:
        return json.dumps(
            {"name": self.akshare_function, "params_json": json.dumps(self.params, ensure_ascii=False)},
            ensure_ascii=False,
        )


# Curated from openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md.
# Cadence: Asia/Shanghai, off-minute staggered (no two at the same :00/:30).
ALL_ITEMS: list[SeedItem] = [
    SeedItem("ashare-daily", "stock_zh_a_hist",
             {"symbol": "000001", "period": "daily", "start_date": "20240101", "end_date": "20250703"},
             "scraw_ashare_daily", ["日期"], "30 16 * * 1-5", tmd_need="沪深日行情"),
    SeedItem("sse-summary", "stock_sse_summary",
             {"date": "20250702"}, "scraw_sse_summary", ["单日情况", "成交金额", "成交数量"],
             "33 17 * * 1-5", tmd_need="成交概况-上交所"),
    SeedItem("szse-summary", "stock_szse_summary",
             {"date": "20250702"}, "scraw_szse_summary", ["证券类别", "成交金额", "成交数量"],
             "37 17 * * 1-5", tmd_need="成交概况-深交所"),
    SeedItem("szse-sector-summary", "stock_szse_sector_summary",
             {}, "scraw_szse_sector_summary", ["板块名称", "板块代码"],
             "7 10 * * 5", tmd_need="行业估值/行业成交"),
    SeedItem("ah-spot-em", "stock_zh_ah_spot_em",
             {}, "scraw_ah_spot_em", ["代码"], "42 16 * * 1-5", tmd_need="AH比价(实时)"),
    SeedItem("qbzf-em", "stock_qbzf_em",
             {}, "scraw_qbzf_em", ["代码", "增发代码"], "13 10 * * 5", tmd_need="增发"),
    SeedItem("pg-em", "stock_pg_em",
             {}, "scraw_pg_em", ["代码"], "17 10 * * 5", tmd_need="配股"),
    SeedItem("dzjy-mrmx", "stock_dzjy_mrmx",
             {}, "scraw_dzjy_mrmx", ["交易日期", "股票代码"], "47 17 * * 1-5", tmd_need="大宗交易-每日明细"),
    SeedItem("dzjy-mrtj", "stock_dzjy_mrtj",
             {}, "scraw_dzjy_mrtj", ["交易日期"], "53 17 * * 1-5", tmd_need="大宗交易-每日统计"),
    SeedItem("individual-info-em", "stock_individual_info_em",
             {"symbol": "000001"}, "scraw_individual_info_em", ["item"], "0 9 * * 5", tmd_need="股票基本信息"),
    SeedItem("gpzy-pledge-ratio-em", "stock_gpzy_pledge_ratio_em",
             {}, "scraw_gpzy_pledge_ratio_em", ["公司代码", "公司名称"], "23 10 * * 5", tmd_need="股权质押-质押比例"),
    SeedItem("ggcg-em", "stock_ggcg_em",
             {}, "scraw_ggcg_em", ["变动日期", "股票代码"], "3 18 * * 1-5", tmd_need="高管持股"),
    SeedItem("fhps-em", "stock_fhps_em",
             {}, "scraw_fhps_em", ["代码", "名称"], "20 10 1 * *", tmd_need="分红配送"),
    SeedItem("hk-hist", "stock_hk_hist",
             {"symbol": "00700", "period": "daily", "adjust": "qfq"},
             "scraw_hk_hist", ["日期"], "0 18 * * 1-5", tmd_need="港股日行情"),
    SeedItem("research-report-em", "stock_research_report_em",
             {}, "scraw_research_report_em", ["股票代码", "研究机构"], "27 18 * * 1-5", tmd_need="券商研报"),
    SeedItem("profit-forecast-em", "stock_profit_forecast_em",
             {}, "scraw_profit_forecast_em", ["股票代码", "机构名称"], "33 18 * * 1-5", tmd_need="盈利预测"),
    SeedItem("zygc-em", "stock_zygc_em",
             {"symbol": "SH688041"}, "scraw_zygc_em", ["股票代码", "报表类型"],
             "40 9 1 */3 *", tmd_need="主营构成"),
]


def _select(only: Optional[str]) -> list[SeedItem]:
    if only is None:
        return list(ALL_ITEMS)
    for it in ALL_ITEMS:
        if it.name == only:
            return [it]
    raise SystemExit(f"--only: no seed item named {only!r}; options: {[i.name for i in ALL_ITEMS]}")


def _plan(collection: str, items: list[SeedItem]) -> list[dict]:
    return [
        {
            "collection": collection,
            "name": it.name,
            "source_mcp": "akshare-mcp",
            "tool": "call_akshare_function",
            "arguments": json.loads(it.arguments_json()),
            "storage_table": it.storage_table,
            "upsert_keys": it.upsert_keys,
            "cron_expr": it.cron,
            "timezone": it.timezone,
            "tmd_need": it.tmd_need,
        }
        for it in items
    ]


async def _seed(collection: str, items: list[SeedItem]) -> dict:
    # ensure collection exists
    try:
        await P.create_pipeline_collection(collection, description="akshare t.md data pipeline (seeded)")
    except P.PipelineError as e:
        if "already exists" not in str(e):
            raise
    # index existing items
    try:
        existing = await P.get_pipeline_collection(collection)
        existing_names = {it["name"] for it in existing.get("items", [])}
    except P.PipelineError:
        existing_names = set()

    created, updated, failed = [], [], []
    for it in items:
        try:
            if it.name in existing_names:
                await P.update_pipeline_item(
                    collection_name=collection,
                    name=it.name,
                    arguments_json=it.arguments_json(),
                    cron_expr=it.cron,
                    timezone=it.timezone,
                    upsert_keys=it.upsert_keys,
                )
                updated.append(it.name)
            else:
                res = await P.add_pipeline_item(
                    collection_name=collection,
                    name=it.name,
                    source_mcp="akshare-mcp",
                    tool="call_akshare_function",
                    arguments_json=it.arguments_json(),
                    storage_table=it.storage_table,
                    upsert_keys=it.upsert_keys,
                    cron_expr=it.cron,
                    timezone=it.timezone,
                )
                created.append(it.name)
                if res["backfill"]["status"] == "backfill_failed":
                    failed.append({"item": it.name, "phase": "backfill", "error": res["backfill"]["error"]})
                if res["cron"]["status"] == "cron_failed":
                    failed.append({"item": it.name, "phase": "cron", "error": res["cron"]["error"]})
        except Exception as e:
            failed.append({"item": it.name, "phase": "seed", "error": f"{type(e).__name__}: {e}"})
    return {"created": created, "updated": updated, "failed": failed}


async def _unseed(collection: str) -> dict:
    try:
        return await P.delete_pipeline_collection(collection)
    except P.PipelineError as e:
        return {"error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed akshare pipeline collection from datasource-mapping.md")
    ap.add_argument("--collection", default="akshare-t-md")
    ap.add_argument("--only", default=None, help="seed only one item by name")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--unseed", action="store_true", help="delete the collection (cascades cron unwiring)")
    args = ap.parse_args()

    if args.unseed:
        res = asyncio.run(_unseed(args.collection))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    items = _select(args.only)
    plan = _plan(args.collection, items)
    if args.dry_run:
        print(json.dumps({"collection": args.collection, "count": len(plan), "items": plan}, ensure_ascii=False, indent=2))
        return 0

    res = asyncio.run(_seed(args.collection, items))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if not res["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
