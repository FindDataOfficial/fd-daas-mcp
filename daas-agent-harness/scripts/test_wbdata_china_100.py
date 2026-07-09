#!/usr/bin/env python3
"""Fetch the most-recent value of 100 REAL World Bank indicators for China.

Uses the package's own get_indicators() catalog (not a hand-picked list),
filters to the "World Development Indicators" source (country-level data),
and pulls each indicator's mrv=1 value for CHN via get_series(). Bypasses the
sandbox proxy (it can't do TLS to api.worldbank.org); direct connection works.

Run: python -u test_wbdata_china_100.py   (foreground, unbuffered)
Output: prints progress + a table, writes /tmp/wbdata_china_100.csv.
"""
from __future__ import annotations

import csv
import os
import time
from pathlib import Path

for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_k, None)

import world_bank_data as wbd

wbd.options.proxies = {"http": None, "https": None}

COUNTRY = "CHN"
TARGET = 100
OUT = Path("/tmp/wbdata_china_100.csv")


def main() -> int:
    t0 = time.time()
    print("Fetching indicator catalog ...", flush=True)
    cat = wbd.get_indicators()
    print(f"Catalog: {len(cat)} indicators ({time.time()-t0:.1f}s)", flush=True)

    # Filter to World Development Indicators (country-level, has China data).
    wdi = cat[cat["source"].astype(str) == "World Development Indicators"]
    print(f"WDI source: {len(wdi)} indicators. Fetching {COUNTRY} mrv=1 ...", flush=True)

    rows = []
    tried = 0
    for code, row in wdi.iterrows():
        if len(rows) >= TARGET:
            break
        tried += 1
        name = str(row["name"])
        try:
            s = wbd.get_series(code, country=COUNTRY, mrv=1, id_or_value="value")
        except Exception:
            continue
        if s is None or (hasattr(s, "empty") and s.empty):
            continue
        try:
            if hasattr(s, "items"):
                items = list(s.items())
                if not items:
                    continue
                idx, val = items[0]
                year = idx[-2] if isinstance(idx, tuple) and len(idx) >= 2 else (
                    idx if not isinstance(idx, tuple) else idx[-1]
                )
            else:
                val = s
                year = ""
        except Exception:
            continue
        if val is None or (isinstance(val, float) and val != val):
            continue
        rows.append({
            "indicator_id": code,
            "indicator_name": name,
            "year": str(year),
            "value": val,
        })
        if len(rows) % 10 == 0:
            print(f"  [{len(rows)}/{TARGET}] tried {tried} "
                  f"({time.time()-t0:.1f}s) e.g. {code}={val}", flush=True)

    dt = time.time() - t0
    print(f"\nFetched {len(rows)} indicators with data for {COUNTRY} "
          f"(tried {tried}, {dt:.1f}s)\n", flush=True)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["indicator_id", "indicator_name", "year", "value"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {OUT}\n")

    print(f"{'indicator_id':24s} {'year':6s} {'value':>22s}  name")
    print("-" * 104)
    for r in rows[:30]:
        val = r["value"]
        valstr = f"{val:,.4f}" if isinstance(val, (int, float)) else str(val)
        if len(valstr) > 22:
            valstr = valstr[:19] + "..."
        print(f"{r['indicator_id']:24s} {r['year']:6s} {valstr:>22s}  {r['indicator_name'][:42]}")
    if len(rows) > 30:
        print(f"... and {len(rows)-30} more (see {OUT})")

    numeric = [r for r in rows if isinstance(r["value"], (int, float))]
    print(f"\nNumeric values: {len(numeric)}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
