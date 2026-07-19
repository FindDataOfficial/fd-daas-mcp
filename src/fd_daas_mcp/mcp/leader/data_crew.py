"""CrewAI DataCrew — routes natural-language data requests to the project's
data-fetch MCPs via the gateway tools.

Mirrors leader_crew.py's pattern: try CrewAI; on ImportError / runtime error,
fall back to a deterministic direct router. Both paths terminate in
`call_data_mcp_sync` (gateway_tools) and return the upstream's raw result dict.

Tool shapes (see design.md Decision 7):
  - registry-based upstreams (yfinance, akshare) expose a single dispatch
    tool (call_yfinance_function / call_akshare_function) taking
    {name, params_json};
  - purpose-built upstreams (edgartools, edinet, dartlab, cnreport,
    hkreport, ckan, cnstats, worldbank) expose direct per-operation tools.

The router must know which shape each upstream has. The gateway itself
(call_data_mcp) is shape-agnostic — it just calls the named tool.

Usage:
    from data_crew import DataCrew
    DataCrew().ask("get AAPL 1-month price history")
"""
from __future__ import annotations

import json
from typing import Optional

from gateway_tools import (
    call_data_mcp_sync,
    list_data_mcps,
    list_data_mcp_tools_sync,
)
# LLM resolver + direct-router helpers are shared with the specialist-agent
# layer (specialist_agents.py) so there is one build_llm / one set of parsing
# helpers for the whole MCP. See `crewai-data-workflow` design Decision 3/8.
from specialist_agents import (
    _call_registry,
    build_llm,
    extract_period,
    extract_symbol,
)


# ═══════════════════════════════════════════════════════════════
# DataCrew
# ═══════════════════════════════════════════════════════════════


class DataCrew:
    """CrewAI-powered router for data-fetch MCP access, with a direct fallback."""

    def __init__(self, manager_llm: str = "gpt-4o"):
        self._manager_llm = manager_llm
        self._last_result: Optional[dict] = None

    def ask(self, question: str, verbose: bool = True) -> dict:
        """Route a natural-language data request and return the fetched data.

        Tries the CrewAI crew first; falls back to a deterministic direct
        router on ImportError or any runtime error. Returns the upstream's
        raw result dict (the same payload `call_data_mcp` returns).
        """
        self._last_result = None
        try:
            self._ask_with_crewai(question, verbose)
        except Exception as exc:  # noqa: BLE001 — any CrewAI failure → fallback
            if verbose:
                print(f"[DataCrew] CrewAI unavailable ({type(exc).__name__}: {exc}), using direct mode")
        if self._last_result is not None:
            return self._last_result
        # CrewAI ran but never executed a fetch (or was skipped) → direct route
        return self._ask_direct(question)

    # ── CrewAI path ─────────────────────────────────────────────

    def _ask_with_crewai(self, question: str, verbose: bool) -> None:
        from crewai import Agent, Crew, Process, Task
        from crewai.tools import tool as crewai_tool

        from leader_tools import search_registry_functions as _search_functions

        # NOTE: we do NOT use leader_tools._get_crewai_tools() here. Those
        # wrappers carry `Optional` type hints (e.g. search_registry_functions(harness:
        # Optional[str]=None)) and CrewAI's generated pydantic model fails to
        # build with "not fully defined; define Optional". Instead we wrap a
        # CrewAI-safe subset with non-Optional signatures.

        @crewai_tool("list_data_mcps")
        def _list_mcps() -> str:
            """List the data-fetch MCP upstreams leader-mcp can route to."""
            return json.dumps(list_data_mcps(), default=str)

        @crewai_tool("list_data_mcp_tools")
        def _list_tools(server: str) -> str:
            """List the tools exposed by a data-fetch MCP upstream (by name)."""
            return json.dumps(list_data_mcp_tools_sync(server), default=str)[:4000]

        @crewai_tool("call_data_mcp")
        def _call_data_mcp(server: str, tool: str, arguments: str = "{}") -> str:
            """Call a tool on a data-fetch MCP upstream.

            server: upstream name (e.g. 'yfinance', 'edgartools').
            tool: the tool name on that upstream. For registry-based upstreams
                  (yfinance, akshare) this is the dispatch tool
                  (call_yfinance_function / call_akshare_function) and arguments
                  is {"name": <func>, "params_json": "<json>"}.
            arguments: JSON object string of arguments.
            """
            result = call_data_mcp_sync(server, tool, arguments)
            self._last_result = result  # stash raw dict for ask() to return
            return json.dumps(result, default=str)[:4000]

        @crewai_tool("search_registry_functions")
        def _search_registry(query: str, harness: str = "") -> str:
            """Search the yfinance/akshare registry for a function by keyword.

            harness: optional, '' (default) searches all harnesses; use
                     'yfinance' or 'akshare' to scope.
            """
            return _search_functions(query, harness if harness else None)[:4000]

        all_tools = [_list_mcps, _list_tools, _call_data_mcp, _search_registry]

        # Single agent that manages access: routes the request to the right
        # upstream+tool and executes the fetch. Sequential process (no
        # hierarchical manager) — hierarchical mode forbids the manager from
        # holding tools, and we want this agent to both route AND call.
        agent = Agent(
            role="Data Access Manager",
            goal=(
                "Route the user's data request to the right data-fetch MCP "
                "upstream and tool, call it via call_data_mcp, and return the "
                "raw fetched data."
            ),
            backstory=(
                "You manage access to the project's data-fetch MCPs via leader-mcp's "
                "gateway. Use list_data_mcps to see upstreams, list_data_mcp_tools to "
                "inspect an upstream's tools, and search_registry_functions to find "
                "yfinance/akshare functions. Registry-based upstreams (yfinance, akshare) "
                "expose a dispatch tool (call_yfinance_function / call_akshare_function) "
                "taking {name, params_json}; other upstreams expose direct tools. Always "
                "finish by calling call_data_mcp and returning its result."
            ),
            tools=all_tools,
            llm=build_llm(None)[0],
            allow_delegation=False,
            verbose=verbose,
        )

        task = Task(
            description=(
                f"User request: {question}\n\n"
                "Steps:\n"
                "1. Use list_data_mcps to see available upstreams.\n"
                "2. Pick the upstream that serves the request. If unsure which tool, "
                "use list_data_mcp_tools(server) to inspect it. For yfinance/akshare, "
                "the tool is the dispatch tool and the real function is an argument "
                "(use search_registry_functions to find the function name).\n"
                "3. Build the JSON arguments (extract symbols, periods, etc. from the request).\n"
                "4. Call call_data_mcp(server, tool, arguments) and return its result.\n"
            ),
            expected_output=(
                "The raw data returned by call_data_mcp (the upstream's result). "
                "Do not summarize — return the fetched data."
            ),
            agent=agent,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=verbose,
        )
        crew.kickoff()

    # ── direct fallback router ──────────────────────────────────

    def _ask_direct(self, question: str) -> dict:
        """Deterministic router: parse the question, pick an upstream + tool,
        build arguments, and call call_data_mcp_sync. Returns the raw result
        dict, or an `{"error": "could not route", ...}` dict."""
        q = question.lower()

        symbol = extract_symbol(question)
        period = extract_period(q)

        # 1. price / market history → yfinance (registry dispatch)
        if any(k in q for k in ("price", "history", "quote", "行情", "历史行情", "股价")):
            if symbol:
                params = {"symbol": symbol, "period": period}
                return _call_registry("yfinance", "ticker_history", params)
            return call_data_mcp_sync("yfinance", "list_categories", "{}")

        # 2. SEC EDGAR filings / 10-K / insider
        if any(k in q for k in ("filing", "10-k", "10k", "edgar", "sec ", "insider")):
            if symbol:
                return call_data_mcp_sync(
                    "edgartools", "list_filings", json.dumps({"ticker_or_cik": symbol})
                )
            return call_data_mcp_sync("edgartools", "list_filings", json.dumps({"limit": 10}))

        # 3. company facts / info
        if any(k in q for k in ("company", "facts", "公司")):
            if symbol:
                return call_data_mcp_sync(
                    "edgartools", "get_company", json.dumps({"ticker_or_cik": symbol})
                )

        # 4. financial statements
        if any(k in q for k in ("financial", "income", "balance sheet", "cashflow", "财务")):
            if symbol:
                return call_data_mcp_sync(
                    "edgartools", "get_financials", json.dumps({"ticker_or_cik": symbol})
                )

        # 5. HK listings
        if any(k in q for k in ("hkex", "hong kong", "港", "00700")):
            if symbol:
                return call_data_mcp_sync(
                    "hkreport", "get_company", json.dumps({"ticker_or_name": symbol})
                )

        # 6. China A-share
        if any(k in q for k in ("a-share", "a股", "akshare", "沪深")):
            if symbol:
                return _call_registry(
                    "akshare", "stock_zh_a_hist", {"symbol": symbol, "period": "daily"}
                )

        # could not route
        available = list_data_mcps()
        return {
            "error": "could not route request",
            "question": question,
            "available": available.get("upstreams", []),
            "hint": "Call call_data_mcp(server, tool, arguments) directly, or ask_data_crew with more specifics.",
        }
