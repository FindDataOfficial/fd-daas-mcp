"""Selfcheck invariants runnable as a pytest assertion (no drift from __main__)."""
from __future__ import annotations

from cli_anything.fd_daas_mcp import selfcheck


def test_run_invariants_returns_ok():
    result = selfcheck.run_invariants()
    assert result["ok"] is True, (
        f"selfcheck invariants failed: "
        + "; ".join(f"{c['name']}={c['detail']}" for c in result["checks"] if not c["ok"])
    )


def test_run_invariants_has_five_checks():
    result = selfcheck.run_invariants()
    names = [c["name"] for c in result["checks"]]
    assert names == [
        "tool-count",
        "collisions",
        "leaf-isolation",
        "no-scheduler-thread",
        "report-no-core-failure",
    ]


def test_run_invariants_tool_count_meets_baseline():
    result = selfcheck.run_invariants()
    assert result["tool_count"] >= 170
    assert len(result["group_counts"]) >= 6
