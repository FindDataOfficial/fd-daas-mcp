"""Dynamic membership rule for us_leadership_pool.

Members = pool A symbols (Top5 by 7/20/60/120d return, union) from the
scraw_us_top300_screen table produced by /tmp/us_top300_screener.py
(re-run to refresh). Re-sync via daas_sync_entity_collection.
"""


def members(ctx):
    rows = ctx.query(
        "SELECT symbol FROM scraw_us_top300_screen WHERE in_pool_a=1 ORDER BY symbol"
    )
    return [r["symbol"] for r in rows]
