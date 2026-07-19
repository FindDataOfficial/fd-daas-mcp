"""
Leader MCP — CrewAI-powered orchestrator for multi-harness registry queries.

The LeaderCrew uses a hierarchical CrewAI crew with a Manager Agent that
delegates to specialist agents (Searcher, Aggregator), all with access to
the unified database tools.

NOTE: CrewAI requires Python < 3.14 due to chromadb/pydantic-v1 incompatibility.
The plain tool functions (in leader_tools.py) work without CrewAI on any version.

Usage (with CrewAI):
    from leader_mcp.leader_crew import LeaderCrew

    crew = LeaderCrew(manager_llm="gpt-4o")
    result = crew.ask("Find all stock market functions across all harnesses")

Usage (without CrewAI, direct tools):
    from leader_mcp.leader_tools import search_registry_functions, list_harnesses
    print(list_harnesses())
    print(search_registry_functions("股票"))
"""
from __future__ import annotations

import sys
from typing import Optional

from leader_tools import (
    list_harnesses,
    search_registry_functions,
    get_registry_function_detail,
    list_harness_categories,
    find_functions_by_column,
    import_harness_registry,
)

SHARED_TOOLS = [
    list_harnesses,
    search_registry_functions,
    get_registry_function_detail,
    list_harness_categories,
    find_functions_by_column,
    import_harness_registry,
]


class LeaderCrew:
    """CrewAI-powered orchestrator for multi-harness registry queries.

    Uses hierarchical process: Manager → Searcher + Aggregator.
    Falls back to direct function calls if CrewAI is unavailable.
    """

    def __init__(self, manager_llm: str = "gpt-4o"):
        self._manager_llm = manager_llm
        self._crew = None

    def ask(self, question: str, verbose: bool = True) -> str:
        """Ask the Leader MCP a question about harness data.

        If CrewAI is available, uses hierarchical agent delegation.
        Otherwise falls back to a direct search-and-aggregate approach.
        """
        try:
            return self._ask_with_crewai(question, verbose)
        except (ImportError, Exception) as e:
            if verbose:
                print(f"[LeaderCrew] CrewAI unavailable ({e}), using direct mode")
            return self._ask_direct(question)

    def _ask_with_crewai(self, question: str, verbose: bool) -> str:
        from crewai import Agent, Task, Crew, Process

        # Wrap tools for CrewAI
        from leader_tools import _get_crewai_tools

        crewai_tools = _get_crewai_tools()

        manager = Agent(
            role="MCP Registry Manager",
            goal=(
                "Understand the user's question about CLI-Anything harness registries, "
                "delegate to specialist agents to find the right data, and synthesize "
                "a clear, accurate answer."
            ),
            backstory=(
                "You manage a unified database of CLI-Anything harness registries. "
                "Each harness stores its functions with: harness name, command, category, "
                "source, description, parameters (JSON), and output columns. "
                "Route queries to the right tools and combine results."
            ),
            tools=crewai_tools,
            allow_delegation=True,
            verbose=verbose,
        )

        searcher = Agent(
            role="Registry Searcher",
            goal="Execute precise searches across harness registries using available tools.",
            backstory=(
                "Expert at querying the unified harness registry. Use list_harnesses "
                "to see what's available, search_registry_functions for text search, "
                "get_registry_function_detail for full info, list_harness_categories to browse, "
                "and find_functions_by_column to discover data fields."
            ),
            tools=crewai_tools,
            allow_delegation=False,
            verbose=verbose,
        )

        task = Task(
            description=(
                f"User question: {question}\n\n"
                "Steps:\n"
                "1. Use list_harnesses to see what data is available.\n"
                "2. Use search_registry_functions or find_functions_by_column to find matches.\n"
                "3. Use get_registry_function_detail for any specific functions.\n"
                "4. Synthesize a clear answer with harness labels, counts, and details."
            ),
            expected_output=(
                "A clear, structured answer addressing the user's question. "
                "Include [harness] labels, counts, and relevant details."
            ),
            agent=manager,
        )

        self._crew = Crew(
            agents=[manager, searcher],
            tasks=[task],
            manager_agent=manager,
            process=Process.hierarchical,
            verbose=verbose,
        )

        return self._crew.kickoff()

    def _ask_direct(self, question: str) -> str:
        """Fallback: search directly without CrewAI agents.

        Parses the question to route to the right tool and extract meaningful
        search terms rather than searching the literal question text.
        """
        import re

        # Stop words to strip from queries (English + Chinese)
        stop_words = {
            "find", "which", "what", "any", "the", "a", "an", "have", "has",
            "with", "that", "return", "returns", "column", "columns", "field",
            "fields", "named", "called", "are", "is", "there", "show", "list",
            "all", "me", "i", "want", "need", "get", "give", "how", "many",
            "search", "for", "in", "to", "of", "available", "do", "does",
            "查找", "哪些", "什么", "怎么", "如何", "有没有", "请", "帮",
            "一下", "所有", "的", "是", "有", "找", "显示",
        }

        def _extract_keywords(text: str) -> str:
            """Extract meaningful Chinese/English keywords, dropping stop words."""
            # Split on common delimiters
            tokens = re.split(r'[\s,，。？?！!]+', text)
            keywords = [t for t in tokens if t and t.lower() not in stop_words and len(t) >= 1]
            return " ".join(keywords[:6])  # top 6 keywords

        q_lower = question.lower()

        # 1. Column name lookup: "column named X", "X column", "返回X字段"
        col_match = re.search(
            r'(?:column|field|字段|列)\s*(?:named|called|is|are|叫|是)?\s*[「「""\']?(\S+?)[」」""\']?(?:\s*(?:column|field|字段|列|$))',
            question
        )
        if col_match:
            col_name = col_match.group(1).strip().rstrip("?？")
            if col_name and len(col_name) >= 2:
                result = find_functions_by_column(col_name)
                return f"Functions with column '{col_name}':\n{result}"

        # Also try: "which functions return X"
        col_match2 = re.search(r'return\s+[a\s]*\s*[「「""\']?(\S+?)[」」""\']?(?:\s|$|\?)', question)
        if col_match2:
            col_name = col_match2.group(1).strip().rstrip("?？")
            if col_name and len(col_name) >= 2 and col_name.lower() not in stop_words:
                result = find_functions_by_column(col_name)
                return f"Functions with column '{col_name}':\n{result}"

        # 2. Harness listing
        if any(w in q_lower for w in ("harness", "available", "what data", "databases")):
            return f"Available harnesses:\n{list_harnesses()}"

        # 3. Categories
        if any(w in q_lower for w in ("category", "categories", "分类", "domain")):
            return f"Categories:\n{list_harness_categories()}"

        # 4. Detail lookup: "detail for X", "info about X", "X 详情"
        detail_match = re.search(
            r'(?:detail|info|details|详情|信息)\s+(?:for|about|of|on)?\s*[「「""\']?(\S+?)[」」""\']?(?:\s|$|\?)',
            question
        )
        if detail_match:
            func_name = detail_match.group(1).strip().rstrip("?？")
            if func_name and len(func_name) >= 3:
                # Try to find which harness this function belongs to
                db = get_leader_db()
                session = db.get_session()
                try:
                    from fd_daas_mcp.models import Function
                    match = session.query(Function).filter(Function.command == func_name).first()
                    if match:
                        return get_registry_function_detail(match.harness, func_name)
                finally:
                    session.close()
                return f"Function '{func_name}' not found. Try search_registry_functions first."

        # 5. Default: keyword search
        keywords = _extract_keywords(question)
        if not keywords:
            return f"Please provide a search term. Available harnesses:\n{list_harnesses()}"

        results = []
        lines = []

        # Search across all harnesses
        lines.append(f"Search results for '{keywords}':")
        lines.append(search_registry_functions(keywords))
        lines.append("")

        # Also check if any column matches
        for kw in keywords.split():
            if len(kw) >= 2:
                col_result = find_functions_by_column(kw)
                if "No functions found" not in col_result:
                    lines.append(f"\nFunctions with column '{kw}':")
                    lines.append(col_result)
                    break

        return "\n".join(lines)

    def import_harness(self, harness: str, registry_path: str) -> str:
        """Import a harness registry into the unified database."""
        return import_harness_registry(harness, registry_path)


def ask_leader(question: str, manager_llm: str = "gpt-4o") -> str:
    """Quick one-shot query to the Leader MCP."""
    crew = LeaderCrew(manager_llm=manager_llm)
    return crew.ask(question)
