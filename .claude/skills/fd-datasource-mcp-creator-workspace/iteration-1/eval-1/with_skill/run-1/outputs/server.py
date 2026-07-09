"""
MCP Server for ccxt — crypto exchange market data.

Purpose-built (not a registry/harness) because `ccxt` exposes an object model
(Exchange instances with unified methods), not a flat function catalog.

Tools:
  fetch_ohlcv      — OHLCV candles for a symbol/timeframe (representative call)
  fetch_ticker     — current ticker snapshot for a symbol
  fetch_markets    — list available markets/symbols on an exchange
  fetch_order_book — order book (bids/asks) for a symbol

Auth: KEYLESS for public market data (fetch_ohlcv / fetch_ticker / fetch_markets /
fetch_order_book). Private endpoints (trading, balance) need API key+secret and are
intentionally not exposed here.

Default exchange: binance (set CCXT_DEFAULT_EXCHANGE to override). The exchange is
constructed lazily inside each tool so the server stays importable without ccxt
installed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root (when in mcp/<src>-mcp/)
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from fastmcp import FastMCP

app = FastMCP(name="ccxt-mcp")

_DEFAULT_EXCHANGE = os.environ.get("CCXT_DEFAULT_EXCHANGE", "binance").strip().lower() or "binance"


# ── Guards & serialization ────────────────────────────────────────────


def _import_ccxt():
    """Lazy-import ccxt, returning (module, error_dict)."""
    try:
        import ccxt  # type: ignore

        return ccxt, None
    except ImportError:
        return None, {
            "error": "ccxt is not installed",
            "hint": "Install with: pip install ccxt",
        }


def _build_exchange(ccxt_mod, exchange_id: str):
    """Construct a ccxt exchange instance by id (e.g. 'binance')."""
    exchange_id = (exchange_id or _DEFAULT_EXCHANGE).strip().lower()
    klass = getattr(ccxt_mod, exchange_id, None)
    if klass is None:
        raise ValueError(f"Unknown ccxt exchange '{exchange_id}'")
    ex = klass({"enableRateLimit": True})
    return ex


def _serialize(result: Any, depth: int = 0, max_depth: int = 5) -> Any:
    """Convert a ccxt result to a JSON-serializable value."""
    if depth > max_depth:
        return str(result)

    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore

    if pd is not None and isinstance(result, pd.DataFrame):
        clean = result.astype(object).where(result.notna(), None)
        return {
            "type": "dataframe",
            "shape": list(result.shape),
            "columns": [str(c) for c in result.columns],
            "data": clean.to_dict(orient="records"),
        }
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    # ccxt returns python-native ints/floats/strings in its unified structures,
    # but defend against numpy scalars just in case.
    if hasattr(result, "dtype") and hasattr(result, "item"):
        try:
            return result.item() if result.ndim == 0 else _serialize(result.tolist(), depth + 1, max_depth)
        except Exception:
            return str(result)
    if isinstance(result, dict):
        return {str(k): _serialize(v, depth + 1, max_depth) for k, v in result.items()}
    if isinstance(result, (list, tuple, set)):
        return [_serialize(v, depth + 1, max_depth) for v in result]
    # Objects with __dict__: flatten to a dict of public, non-callable attrs.
    if hasattr(result, "__dict__"):
        d = {}
        for k, v in vars(result).items():
            if k.startswith("_") or callable(v):
                continue
            d[k] = _serialize(v, depth + 1, max_depth)
        if d:
            return d
    return str(result)


# ── Tools ─────────────────────────────────────────────────────────────


@app.tool
def fetch_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    limit: int = 100,
    exchange: Optional[str] = None,
) -> dict:
    """Fetch OHLCV candles for a crypto pair.

    Args:
        symbol: Trading pair, e.g. "BTC/USDT".
        timeframe: Candle interval, e.g. "1m", "5m", "1h", "1d" (default "1d").
        limit: Max candles (default 100, max 1000).
        exchange: ccxt exchange id (default "binance").
    """
    ccxt, err = _import_ccxt()
    if err:
        return err
    try:
        ex = _build_exchange(ccxt, exchange or _DEFAULT_EXCHANGE)
    except Exception as e:
        return {"error": f"Exchange init failed: {type(e).__name__}: {e}"}
    try:
        limit = max(1, min(int(limit), 1000))
        rows = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        return {"error": f"fetch_ohlcv failed: {type(e).__name__}: {e}"}
    # rows are [timestamp_ms, open, high, low, close, volume]
    candles = []
    for r in (rows or []):
        if not r or len(r) < 6:
            continue
        candles.append({
            "timestamp": r[0],
            "datetime": ex.iso8601(r[0]) if hasattr(ex, "iso8601") else None,
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5],
        })
    return {
        "exchange": (exchange or _DEFAULT_EXCHANGE).lower(),
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(candles),
        "ohlcv": candles,
    }


@app.tool
def fetch_ticker(symbol: str, exchange: Optional[str] = None) -> dict:
    """Fetch the current ticker snapshot for a crypto pair.

    Args:
        symbol: Trading pair, e.g. "BTC/USDT".
        exchange: ccxt exchange id (default "binance").
    """
    ccxt, err = _import_ccxt()
    if err:
        return err
    try:
        ex = _build_exchange(ccxt, exchange or _DEFAULT_EXCHANGE)
    except Exception as e:
        return {"error": f"Exchange init failed: {type(e).__name__}: {e}"}
    try:
        ticker = ex.fetch_ticker(symbol)
    except Exception as e:
        return {"error": f"fetch_ticker failed: {type(e).__name__}: {e}"}
    return _serialize(ticker)


@app.tool
def fetch_markets(exchange: Optional[str] = None, limit: int = 200) -> dict:
    """List available markets/symbols on an exchange.

    Args:
        exchange: ccxt exchange id (default "binance").
        limit: Max markets to return (default 200, max 2000).
    """
    ccxt, err = _import_ccxt()
    if err:
        return err
    try:
        ex = _build_exchange(ccxt, exchange or _DEFAULT_EXCHANGE)
    except Exception as e:
        return {"error": f"Exchange init failed: {type(e).__name__}: {e}"}
    try:
        markets = ex.load_markets()
    except Exception as e:
        return {"error": f"load_markets failed: {type(e).__name__}: {e}"}
    limit = max(1, min(int(limit), 2000))
    items = []
    for sym, m in (markets or {}).items():
        items.append({
            "symbol": sym,
            "base": m.get("base") if isinstance(m, dict) else None,
            "quote": m.get("quote") if isinstance(m, dict) else None,
            "type": m.get("type") if isinstance(m, dict) else None,
            "active": m.get("active") if isinstance(m, dict) else None,
        })
        if len(items) >= limit:
            break
    return {
        "exchange": (exchange or _DEFAULT_EXCHANGE).lower(),
        "count": len(items),
        "markets": items,
    }


@app.tool
def fetch_order_book(symbol: str, limit: int = 50, exchange: Optional[str] = None) -> dict:
    """Fetch the order book (bids/asks) for a crypto pair.

    Args:
        symbol: Trading pair, e.g. "BTC/USDT".
        limit: Max price levels per side (default 50, max 500).
        exchange: ccxt exchange id (default "binance").
    """
    ccxt, err = _import_ccxt()
    if err:
        return err
    try:
        ex = _build_exchange(ccxt, exchange or _DEFAULT_EXCHANGE)
    except Exception as e:
        return {"error": f"Exchange init failed: {type(e).__name__}: {e}"}
    try:
        limit = max(1, min(int(limit), 500))
        ob = ex.fetch_order_book(symbol, limit=limit)
    except Exception as e:
        return {"error": f"fetch_order_book failed: {type(e).__name__}: {e}"}
    return _serialize(ob)


def _selfcheck() -> int:
    """Offline check of the _serialize + _build_exchange error paths. No network."""
    # serialize paths
    assert _serialize({"a": [1, 2]}) == {"a": [1, 2]}
    assert _serialize([1, "x"]) == [1, "x"]
    assert _serialize("hi") == "hi"
    assert _serialize(3.14) == 3.14
    assert _serialize(None) is None

    # ccxt missing-guard
    mod, err = _import_ccxt()
    if mod is None:
        assert err and "ccxt is not installed" in err["error"], err
    else:
        # ccxt present — _build_exchange should reject a bogus id
        try:
            _build_exchange(mod, "this_is_not_an_exchange_id_12345")
            assert False, "expected ValueError for bogus exchange id"
        except ValueError:
            pass
        # and a real id should construct
        ex = _build_exchange(mod, "binance")
        assert ex is not None

    print("selfcheck OK")
    return 0


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        raise SystemExit(_selfcheck())
    app.run(transport="stdio", show_banner=False)
