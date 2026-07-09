"""
Purpose-built MCP server template (edgartools-style).

Use when the package exposes an object/functional API, not a flat function
catalog. Adapt for {{SOURCE}} — replace every {{...}} placeholder.

Pattern:
  - FastMCP, stdio transport.
  - Unified env: root .env first, then this dir's .env with override=True.
  - Lazy-import the package inside each tool (server stays importable without
    the dep; tools return a clear {error, hint} when the dep/auth is missing).
  - _serialize() converts the package's objects to JSON (capped depth).
  - Per-tool auth guard (_require_*) returns an error dict before any work.
  - Registered in .mcp.json via: uv run --directory mcp/{{SOURCE}}-mcp python server.py
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from fastmcp import FastMCP

app = FastMCP(name="{{SOURCE}}-mcp")

# ── Auth / identity ───────────────────────────────────────────────────
# Configure at startup if an env-based identity/credential is required by the
# upstream API. Keep it cheap; don't crash the server if it's missing — tools
# surface a clearer error per-call.
_AUTH_OK: bool = bool(os.environ.get("{{ENV_PREFIX}}_API_KEY", "").strip())
# if _AUTH_OK:
#     try: from {{PACKAGE}} import set_identity; set_identity(...)
#     except Exception: _AUTH_OK = False


def _require_auth() -> Optional[dict]:
    """Return an error dict if auth is not configured, else None."""
    if not _AUTH_OK:
        return {
            "error": "{{ENV_PREFIX}}_API_KEY is not set",
            "hint": 'Set {{ENV_PREFIX}}_API_KEY="..." in root .env.',
        }
    return None


def _import_pkg():
    """Lazy-import {{PACKAGE}}, returning (module, error_dict)."""
    try:
        import {{PACKAGE}}  # type: ignore

        return {{PACKAGE}}, None
    except ImportError:
        return None, {
            "error": "{{PACKAGE}} is not installed",
            "hint": "Install with: pip install {{PACKAGE}}",
        }


# ── Serialization ──────────────────────────────────────────────────────
def _serialize(result: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Convert a {{PACKAGE}} result to a JSON-serializable value."""
    if depth > max_depth:
        return str(result)
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    if isinstance(result, dict):
        return {str(k): _serialize(v, depth + 1, max_depth) for k, v in result.items()}
    if isinstance(result, (list, tuple, set)):
        return [_serialize(v, depth + 1, max_depth) for v in result][:1000]
    # Objects with __dict__: best-effort attribute dump.
    if hasattr(result, "__dict__"):
        return {
            k: _serialize(v, depth + 1, max_depth)
            for k, v in vars(result).items()
            if not k.startswith("_")
        }
    # pandas DataFrame / Series
    if hasattr(result, "to_dict"):
        try:
            return _serialize(result.to_dict("records" if hasattr(result, "columns") else "list"),
                              depth + 1, max_depth)
        except Exception:
            return str(result)
    return str(result)


# ── Tools (4–6 typical) ───────────────────────────────────────────────
@app.tool()
def get_company({{IDENTIFIER}}: str) -> dict:
    """Look up a {{ENTITY_NOUN}} and return its core facts.

    Args:
        {{IDENTIFIER}}: {{IDENTIFIER_DESCRIPTION}}
    """
    err = _require_auth()
    if err:
        return err
    pkg, err = _import_pkg()
    if err:
        return err
    try:
        obj = pkg.{{CLASS}}({{IDENTIFIER}})
        return _serialize(obj)
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.tool()
def list_items({{IDENTIFIER}}: str, limit: int = 10) -> dict:
    """List items for a {{ENTITY_NOUN}}."""
    err = _require_auth()
    if err:
        return err
    pkg, err = _import_pkg()
    if err:
        return err
    try:
        result = pkg.{{CLASS}}({{IDENTIFIER}}).list(limit=limit)
        return {"items": _serialize(result), "count": len(list(result)) if result else 0}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.tool()
def get_detail({{IDENTIFIER}}: str, kind: str = "default") -> dict:
    """Fetch a structured detail (statement / report / panel) for a {{ENTITY_NOUN}}.

    Args:
        kind: which detail to return (e.g. 'income', 'balance', 'cashflow').
    """
    err = _require_auth()
    if err:
        return err
    pkg, err = _import_pkg()
    if err:
        return err
    try:
        result = pkg.{{CLASS}}({{IDENTIFIER}}).detail(kind=kind)
        return {"kind": kind, "data": _serialize(result)}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


if __name__ == "__main__":
    app.run()
