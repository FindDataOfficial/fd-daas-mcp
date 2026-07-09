"""
MCP Server for meteostat — weather station time series.

Purpose-built (not a registry/harness) because `meteostat` exposes an
object/functional API (`Station`, `Stations`, `daily`/`hourly`/`monthly`
`TimeSeries`), not a flat function catalog. Mirrors the edgartools/edinet
shape: FastMCP + lazy import + per-tool auth guards + `_serialize` helper.

Tools:
  station_daily        — daily weather observations for a station over a
                         date range (the representative call). Returns the
                         documented daily columns: date, tavg, tmin, tmax,
                         prcp, snow, wdir, wspd, wpgt, pres, tsun.
  station_info         — station metadata (name, country, latitude/longitude/
                         elevation, identifiers).
  find_stations_nearby — discover weather stations near a lat/lon.

Auth: KEYLESS. meteostat downloads bulk data from bulk.meteostat.net —
no API key required for the Python library. (The hosted RapidAPI endpoint
needs a key, but the library does not.)

Registered in .mcp.json via:
  uv run --directory mcp/meteostat-mcp python server.py
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

# Unified env: root .env first, then per-MCP .env with override=True.
# (When this server lives outside the real repo — e.g. under /tmp for an
# eval — parents[2] still resolves to a sensible ancestor and the missing
# root .env is a no-op.)
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root (or eval root)
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from fastmcp import FastMCP

app = FastMCP(name="meteostat-mcp")

# meteostat is KEYLESS — no auth guard. We still track config for diagnostics.
# Optional: METEOSTAT_CACHE_DIR overrides the bulk-data cache location.
_CACHE_DIR: Optional[str] = os.environ.get("METEOSTAT_CACHE_DIR") or None


def _import_meteostat():
    """Lazy-import meteostat, returning (module, error_dict)."""
    try:
        import meteostat  # type: ignore

        return meteostat, None
    except ImportError:
        return None, {
            "error": "meteostat is not installed",
            "hint": "Install with: pip install meteostat",
        }


# ── Serialization ──────────────────────────────────────────────────────
def _serialize(result: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Convert a meteostat result to a JSON-serializable value."""
    if depth > max_depth:
        return str(result)

    # Lazy pandas import (meteostat depends on pandas)
    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore

    if pd is not None and isinstance(result, pd.DataFrame):
        clean = result.where(result.notna(), None)
        # Reset index so the date index becomes a column (meteostat's daily
        # DataFrame is indexed by `time` — surface it as `date`).
        try:
            if result.index.name and "date" not in result.columns:
                clean = result.reset_index(names=[result.index.name])
        except Exception:
            pass
        return {
            "type": "dataframe",
            "shape": list(result.shape),
            "columns": [str(c) for c in clean.columns],
            "data": clean.to_dict(orient="records"),
        }
    if pd is not None and isinstance(result, pd.Series):
        clean = result.where(result.notna(), None)
        return {
            "type": "series",
            "length": len(result),
            "name": str(result.name) if result.name is not None else None,
            "data": clean.to_dict(),
        }
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    if isinstance(result, dict):
        return {str(k): _serialize(v, depth + 1, max_depth) for k, v in result.items()}
    if isinstance(result, (list, tuple, set)):
        return [_serialize(v, depth + 1, max_depth) for v in result][:1000]

    # Objects exposing to_dict()
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        try:
            return _serialize(to_dict(), depth + 1, max_depth)
        except Exception:
            pass

    # Objects with __dict__: best-effort attribute dump.
    if hasattr(result, "__dict__"):
        d = {}
        for k, v in vars(result).items():
            if k.startswith("_") or callable(v):
                continue
            d[k] = _serialize(v, depth + 1, max_depth)
        return d if d else str(result)
    return str(result)


def _parse_date(s: str) -> date:
    """Parse YYYY-MM-DD (raises ValueError on bad input)."""
    return datetime.strptime(s, "%Y-%m-%d").date()


# ── Tools ─────────────────────────────────────────────────────────────
@app.tool()
def station_daily(station_id: str, start: str, end: str) -> dict:
    """Fetch daily weather observations for a station over a date range.

    Returns the documented daily columns: date, tavg, tmin, tmax, prcp,
    snow, wdir, wspd, wpgt, pres, tsun
    (average/min/max temperature °C, precipitation mm, snow depth mm,
    wind direction °, wind speed km/h, peak gust km/h, sea-level pressure
    hPa, sunshine minutes).

    Args:
        station_id: meteostat station id, e.g. "10637" (Frankfurt).
        start: start date, YYYY-MM-DD.
        end: end date, YYYY-MM-DD.
    """
    pkg, err = _import_meteostat()
    if err:
        return err
    try:
        start_d = _parse_date(start)
        end_d = _parse_date(end)
    except ValueError as e:
        return {"error": f"bad date: {e}", "hint": "dates must be YYYY-MM-DD"}
    try:
        ts = pkg.daily(pkg.Station(station_id), start_d, end_d)
        df = ts.fetch()
        return _serialize(df)
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.tool()
def station_info(station_id: str) -> dict:
    """Return metadata for a single weather station (name, country,
    latitude/longitude/elevation, identifiers).
    """
    pkg, err = _import_meteostat()
    if err:
        return err
    try:
        st = pkg.Station(station_id)
        info = st.get_info() if hasattr(st, "get_info") else st
        return _serialize(info)
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.tool()
def find_stations_nearby(lat: float, lon: float, limit: int = 10) -> dict:
    """Discover weather stations near a lat/lon, closest first.

    Args:
        lat, lon: coordinates in decimal degrees.
        limit: max number of stations to return (default 10).
    """
    pkg, err = _import_meteostat()
    if err:
        return err
    try:
        stations = pkg.Stations()
        stations = stations.nearby(lat, lon, limit=limit)
        df = stations.fetch() if hasattr(stations, "fetch") else stations
        return _serialize(df)
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


if __name__ == "__main__":
    app.run()
