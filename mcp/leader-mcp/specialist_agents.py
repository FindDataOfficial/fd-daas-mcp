"""CrewAI specialist data agents + per-agent LLM control for leader-mcp.

Specialist agents (one per data-fetch MCP) + the LLM registry they bind to +
the deterministic fallback that keeps a step working without an LLM. This is
the agent layer of the `crewai-data-workflow` capability; `workflow_tools.py`
composes these agents into step-by-step workflows.

Three concerns, in order:

1. **LLM registry** (`LEADER_MODELS` JSON, mirroring process-mcp's `PROCESS_MODELS`):
   `{name: {model, base_url?, api_key?, provider?, vision?}}` with a shared
   `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` fallback. `build_llm(name)`
   returns a `(llm, error, reason)` triple: `error` set = hard config error
   (surface it, no fetch); `reason` set = soft "no LLM" (fall back to direct);
   `llm` set = a ready CrewAI `LLM`.

2. **Specialist tools** (`build_specialist_tools`) — a CrewAI-safe tool list
   curried to one `upstream`: the agent's `call_data_mcp` fixes `server=<upstream>`
   so it can only fetch from its specialized MCP (hard guarantee, not prompt-based).

3. **Step runner** (`run_specialist_step`) — builds a one-agent Crew, kicks it
   off, returns the stashed raw `call_data_mcp` result. Falls back to
   `_direct_fetch` (extracted from `data_crew.DataCrew._ask_direct`) when
   CrewAI is unavailable, the model is soft-unconfigured, or the crew errors.

`data_crew.py` reuses `build_llm` + the parsing helpers here so there is one
LLM resolver and one direct router for the whole MCP.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, Tuple

from gateway_tools import call_data_mcp_sync, list_data_mcp_tools_sync


# ═══════════════════════════════════════════════════════════════
# LLM registry (LEADER_MODELS, mirrors process-mcp PROCESS_MODELS)
# ═══════════════════════════════════════════════════════════════

_DEFAULT_MODEL = "gpt-4o"
_MODELS: Optional[dict] = None


def load_models() -> dict:
    """Parse `LEADER_MODELS` JSON (or fall back to single-model env). Cached.

    Shape: `{name: {model, base_url?, api_key?, provider?, vision?}}`. Per-model
    fields fall back to the shared `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`
    env (the same shared OpenAI-compatible endpoint process-mcp / cnreport-mcp
    use). When `LEADER_MODELS` is unset, a single `"default"` entry is built from
    the shared env.
    """
    global _MODELS
    if _MODELS is not None:
        return _MODELS

    raw = os.environ.get("LEADER_MODELS", "").strip()
    shared_key = os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    shared_base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    shared_model = os.environ.get("LLM_MODEL", _DEFAULT_MODEL)

    if raw:
        try:
            registry = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LEADER_MODELS is not valid JSON: {exc}") from exc
        models: dict[str, dict] = {}
        for name, spec in registry.items():
            spec = spec or {}
            models[name] = {
                "model": spec.get("model", shared_model),
                "vision": bool(spec.get("vision", False)),
                "base_url": (spec.get("base_url") or shared_base).rstrip("/"),
                "api_key": spec.get("api_key") or shared_key,
                "provider": (spec.get("provider") or "").lower() or None,
            }
        _MODELS = models
        return _MODELS

    # single-model fallback when LEADER_MODELS unset
    _MODELS = {
        "default": {
            "model": shared_model,
            "vision": False,
            "base_url": shared_base,
            "api_key": shared_key,
            "provider": None,
        }
    }
    return _MODELS


def reset_models_cache() -> None:
    """Clear the cached model registry (used by tests / selfcheck)."""
    global _MODELS
    _MODELS = None


def _litellm_model_str(cfg: dict) -> str:
    """Build the litellm model string for a CrewAI LLM.

    `provider/<model>` when a provider is set (e.g. anthropic, openai);
    `openai/<model>` when only a custom base_url is set (OpenAI-compatible
    endpoint like Volcengine ark / DeepSeek); bare `model` otherwise.
    """
    model = cfg["model"]
    provider = cfg.get("provider")
    base_url = cfg.get("base_url")
    if provider:
        return f"{provider}/{model}"
    if base_url:
        return f"openai/{model}"
    return model


def build_llm(model_name: Optional[str]) -> Tuple[Any, Optional[str], Optional[str]]:
    """Resolve a named model into a CrewAI `LLM`.

    Returns `(llm, error, reason)`:
    - `llm` set, `error=None`, `reason=None` → ready to run a crew.
    - `llm=None`, `error` set → hard config error (caller returns it as the
      step's error, no fetch, no fallback). E.g. named model not in registry,
      or a named model missing api_key/base_url.
    - `llm=None`, `error=None`, `reason` set → soft "no LLM available" (caller
      falls back to `_direct_fetch`). E.g. crewai not installed, or the shared
      fallback (model=None) has no LLM_* env, or LLM construction raised.
    """
    try:
        from crewai import LLM  # type: ignore
    except ImportError:
        return None, None, "crewai unavailable"

    models = load_models()
    if model_name is not None:
        cfg = models.get(model_name)
        if cfg is None:
            # named but not in LEADER_MODELS — surface the misconfig (hard error)
            return None, f"model '{model_name}' not configured", None
        label = model_name
    else:
        # shared fallback: prefer "default", else first registered, else none
        cfg = models.get("default") or (next(iter(models.values()), None) if models else None)
        label = "default"
        if cfg is None or not cfg.get("api_key") or not cfg.get("base_url"):
            # no LLM_* fallback configured → soft (fall back to direct)
            return None, None, "no LLM configured (set LEADER_MODELS or LLM_*)"

    if not cfg.get("api_key") or not cfg.get("base_url"):
        # named model present in registry but missing keys → hard error
        return None, f"model '{label}' missing api_key/base_url", None

    try:
        return LLM(model=_litellm_model_str(cfg), base_url=cfg["base_url"], api_key=cfg["api_key"]), None, None
    except Exception as exc:  # noqa: BLE001 — any LLM build failure → soft fallback
        return None, None, f"LLM build failed: {type(exc).__name__}: {exc}"


def list_agent_models() -> dict:
    """List configured agent models (api keys never serialized).

    Returns `{models: [{name, model, provider, base_url, vision}, ...]}`.
    """
    models = load_models()
    return {
        "models": [
            {
                "name": n,
                "model": c["model"],
                "provider": c.get("provider"),
                "base_url": c.get("base_url"),
                "vision": c.get("vision", False),
            }
            for n, c in models.items()
        ]
    }


# ═══════════════════════════════════════════════════════════════
# upstream shape map + parsing helpers (shared with data_crew.DataCrew)
# ═══════════════════════════════════════════════════════════════

# Registry-based upstreams → their dispatch tool name. Upstreams NOT in this
# map are purpose-built and expose direct per-operation tools.
_REGISTRY_DISPATCH_TOOL = {
    "yfinance": "call_yfinance_function",
    "akshare": "call_akshare_function",
}


def is_registry_based(server: str) -> bool:
    return server in _REGISTRY_DISPATCH_TOOL


def _call_registry(server: str, func_name: str, params: dict) -> dict:
    """Call a registry-based upstream's dispatch tool."""
    tool = _REGISTRY_DISPATCH_TOOL[server]
    arguments = {"name": func_name, "params_json": json.dumps(params)}
    return call_data_mcp_sync(server, tool, json.dumps(arguments))


def extract_symbol(question: str) -> Optional[str]:
    # "symbol AAPL", "ticker: AAPL", "for AAPL"
    m = re.search(r"\b(?:symbol|ticker|for|stock)\s*[:：]?\s*([A-Za-z0-9]{1,8})\b", question, re.I)
    if m:
        return m.group(1).upper()
    # bare uppercase token 1–6 chars (US ticker) — skip common words
    for m in re.finditer(r"\b([A-Z]{1,6})\b", question):
        tok = m.group(1)
        if tok.lower() not in {"get", "the", "for", "and", "of", "us", "hk", "a"}:
            return tok
    # 6-digit A-share / 5-digit HK code
    m = re.search(r"\b(\d{5,6})\b", question)
    if m:
        return m.group(1)
    return None


def extract_period(q_lower: str) -> str:
    m = re.search(r"\b(\d+)\s*(mo|month|y|year|d|day|wk|week)s?\b", q_lower)
    if not m:
        return "1mo"
    n, unit = m.group(1), m.group(2)
    if unit.startswith("mo") or unit.startswith("month"):
        return f"{n}mo"
    if unit.startswith("y"):
        return f"{n}y"
    if unit.startswith("d"):
        return f"{n}d"
    if unit.startswith("wk") or unit.startswith("week"):
        return f"{n}wk"
    return "1mo"


# keyword sets for the direct router (ported from data_crew.DataCrew._ask_direct)
_KW_PRICE = ("price", "history", "quote", "行情", "历史行情", "股价")
_KW_FILING = ("filing", "10-k", "10k", "edgar", "sec ", "insider")
_KW_COMPANY = ("company", "facts", "公司")
_KW_FINANCIAL = ("financial", "income", "balance sheet", "cashflow", "财务")
_KW_HK = ("hkex", "hong kong", "港", "00700")
_KW_ASHARE = ("a-share", "a股", "akshare", "沪深")


def _direct_fetch(upstream: str, request: str) -> dict:
    """Deterministic per-upstream fetch (no LLM).

    Given a FIXED upstream (the specialist agent's bound MCP) and a request,
    parse symbol/period/keywords and call the right tool on that upstream via
    `call_data_mcp_sync`. Returns the upstream's raw result dict, or an
    `{"error": ...}` dict when the request can't be routed for this upstream.
    """
    q = request.lower()
    symbol = extract_symbol(request)
    period = extract_period(q)

    if upstream == "yfinance":
        if symbol:
            return _call_registry("yfinance", "ticker_history", {"symbol": symbol, "period": period})
        return call_data_mcp_sync("yfinance", "list_categories", "{}")

    if upstream == "akshare":
        if symbol:
            return _call_registry("akshare", "stock_zh_a_hist", {"symbol": symbol, "period": "daily"})
        return call_data_mcp_sync("akshare", "list_categories", "{}")

    if upstream == "edgartools":
        if any(k in q for k in _KW_FILING):
            if symbol:
                return call_data_mcp_sync("edgartools", "list_filings", json.dumps({"ticker_or_cik": symbol}))
            return call_data_mcp_sync("edgartools", "list_filings", json.dumps({"limit": 10}))
        if any(k in q for k in _KW_FINANCIAL) and symbol:
            return call_data_mcp_sync("edgartools", "get_financials", json.dumps({"ticker_or_cik": symbol}))
        if any(k in q for k in _KW_COMPANY) or symbol:
            if symbol:
                return call_data_mcp_sync("edgartools", "get_company", json.dumps({"ticker_or_cik": symbol}))
        return call_data_mcp_sync("edgartools", "list_filings", json.dumps({"limit": 10}))

    if upstream == "hkreport":
        if symbol:
            return call_data_mcp_sync("hkreport", "get_company", json.dumps({"ticker_or_name": symbol}))
        return {"error": "hkreport direct fallback needs a ticker/name (e.g. '00700')"}

    # edinet / dartlab / cnreport / ckan / cnstats / worldbank + unknown:
    # the direct router has no keyword mapping for these purpose-built MCPs.
    return {
        "error": (
            f"direct fallback cannot route for upstream '{upstream}'; install "
            f"crewai + configure LEADER_MODELS, or call_data_mcp('{upstream}', "
            f"<tool>, <arguments>) directly"
        )
    }


# ═══════════════════════════════════════════════════════════════
# specialist CrewAI tools (curried to one upstream) + step runner
# ═══════════════════════════════════════════════════════════════


def build_specialist_tools(upstream: str, stash: dict) -> list:
    """Build a CrewAI-safe tool list curried to `upstream`.

    The agent gets:
    - `call_data_mcp_<upstream>(tool, arguments)` — calls `call_data_mcp_sync`
      with `server=<upstream>` fixed, so it can ONLY fetch from this MCP. The
      raw result is stashed into `stash["result"]` for the runner to return.
    - `list_tools_<upstream>()` — wraps `list_data_mcp_tools_sync(upstream)`.
    - `search_registry_<upstream>(query)` — for registry-based upstreams only,
      scopes `leader_tools.search_functions` to `harness=<upstream>`.

    Tools use non-`Optional` type hints (CrewAI's generated pydantic model
    fails to build with `Optional` — see data_crew.py).
    """
    from crewai.tools import tool as crewai_tool  # type: ignore
    if is_registry_based(upstream):
        from leader_tools import search_functions as _search_functions

    @crewai_tool(f"call_data_mcp_{upstream}")
    def _call_data_mcp(tool: str, arguments: str = "{}") -> str:
        """Call a tool on this agent's bound MCP upstream and return the raw result.

        tool: the tool name on this upstream. For registry-based upstreams this
              is the dispatch tool (call_yfinance_function / call_akshare_function)
              and arguments is {"name": <func>, "params_json": "<json>"}.
        arguments: JSON object string of arguments.
        """
        result = call_data_mcp_sync(upstream, tool, arguments)
        stash["result"] = result  # stash raw dict for the runner to return
        return json.dumps(result, default=str)[:4000]

    @crewai_tool(f"list_tools_{upstream}")
    def _list_tools() -> str:
        """List the tools exposed by this agent's bound MCP upstream."""
        return json.dumps(list_data_mcp_tools_sync(upstream), default=str)[:4000]

    tools = [_call_data_mcp, _list_tools]

    if is_registry_based(upstream):
        @crewai_tool(f"search_registry_{upstream}")
        def _search_registry(query: str) -> str:
            """Search this upstream's registry for a function by keyword."""
            return _search_functions(query, upstream)[:4000]
        tools.append(_search_registry)

    return tools


def run_specialist_step(agent: dict, request: str, model_override: Optional[str] = None) -> dict:
    """Run one specialist-agent step. Returns `{status, output, error, meta}`.

    `agent` is a specialist-agent dict (as returned by the DB `to_dict`):
    needs `upstream`; `role`/`goal`/`backstory`/`model` are optional (defaults
    derived from `upstream`).

    - `status="completed"`, `output=<raw>` — the agent (or fallback) fetched data.
    - `status="failed"`, `error=<msg>` — hard error (no fetch): model misconfig,
      or the fallback could not route the request.

    The `output` is the raw `call_data_mcp` result dict (the upstream's data),
    not an LLM summary. `meta` records `{"fallback": "direct", "reason": ...}`
    when the direct path was used so it is never silent.
    """
    upstream = agent["upstream"]
    model_name = model_override or agent.get("model")
    llm, error, reason = build_llm(model_name)

    if error is not None:
        # hard config error — surface it, no fetch, no fallback
        return {"status": "failed", "output": None, "error": error, "meta": {}}

    if llm is None:
        # soft "no LLM" — deterministic direct fallback so data still flows
        out = _direct_fetch(upstream, request)
        meta = {"fallback": "direct", "reason": reason or "no LLM"}
        if "error" in out:
            return {"status": "failed", "output": None, "error": out["error"], "meta": meta}
        return {"status": "completed", "output": out, "meta": meta}

    # CrewAI path — build a one-agent crew and kick it off
    try:
        from crewai import Agent, Crew, Process, Task  # type: ignore
    except ImportError:
        out = _direct_fetch(upstream, request)
        meta = {"fallback": "direct", "reason": "crewai unavailable"}
        if "error" in out:
            return {"status": "failed", "output": None, "error": out["error"], "meta": meta}
        return {"status": "completed", "output": out, "meta": meta}

    stash: dict = {"result": None}
    tools = build_specialist_tools(upstream, stash)

    role = agent.get("role") or f"{upstream} data specialist"
    goal = agent.get("goal") or (
        f"Fetch data from the {upstream} MCP via its bound call_data_mcp tool "
        f"and return the raw result."
    )
    backstory = agent.get("backstory") or (
        f"You are a specialist for the {upstream} data-fetch MCP. You can only "
        f"fetch from this upstream. Always finish by calling its "
        f"call_data_mcp_{upstream} tool and return its raw result."
    )

    agent = Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        tools=tools,
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=(
            f"Request: {request}\n\n"
            f"Steps:\n"
            f"1. ALWAYS start by calling list_tools_{upstream} to see the exact "
            f"tool names AND their parameter names"
            + (
                f", and search_registry_{upstream} to find the right function name"
                f" (the dispatch tool takes {{name, params_json}})."
                if is_registry_based(upstream)
                else "."
            )
            + f"\n2. Build the JSON arguments using the EXACT parameter names from "
            f"step 1 (extract symbols, periods, etc. from the request).\n"
            f"3. Call call_data_mcp_{upstream}(tool, arguments) and return its raw result.\n"
        ),
        expected_output=(
            "The raw data returned by call_data_mcp (the upstream's result). "
            "Do not summarize — return the fetched data."
        ),
        agent=agent,
    )

    try:
        Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    except Exception as exc:  # noqa: BLE001 — any crew failure → direct fallback
        out = _direct_fetch(upstream, request)
        meta = {"fallback": "direct", "reason": f"crew error: {type(exc).__name__}: {exc}"}
        if "error" in out:
            return {"status": "failed", "output": None, "error": out["error"], "meta": meta}
        return {"status": "completed", "output": out, "meta": meta}

    out = stash["result"]
    if out is None:
        # crew ran but never called the fetch tool → direct fallback
        out = _direct_fetch(upstream, request)
        meta = {"fallback": "direct", "reason": "crew did not call_data_mcp"}
        if "error" in out:
            return {"status": "failed", "output": None, "error": out["error"], "meta": meta}
        return {"status": "completed", "output": out, "meta": meta}

    # crew called the tool — if the upstream returned an error dict, the fetch
    # failed (do not mark a failed fetch as "completed")
    if isinstance(out, dict) and "error" in out:
        return {"status": "failed", "output": None, "error": out["error"], "meta": {}}
    return {"status": "completed", "output": out, "meta": {}}
