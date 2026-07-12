"""Self-check for the model-tier registry (high / balance / fast).

Pure env + resolver tests — NO DB, NO subprocess, NO network call. Asserts:
  - `resolve_tier` resolves a set tier to its LEADER_MODELS entry's spec.
  - `resolve_tier` returns `(None, None)` for an unset tier (soft fallback).
  - `resolve_tier` returns a dangling-tier error when the env var names a
    missing LEADER_MODELS entry.
  - `build_llm` propagates the dangling-tier error as a hard error (no LLM,
    no network) and resolves a set tier to a CrewAI LLM built from the entry
    (when crewai is importable).
  - `list_model_tiers` reports set / unset / dangling tiers correctly.

Usage:
    uv run --directory mcp/leader-mcp python selfcheck_tiers.py
    # or:
    PYTHONPATH=mcp:mcp/leader-mcp python3 selfcheck_tiers.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MCP_ROOT = _HERE.parent
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))

# Do NOT load .env — this selfcheck sets LEADER_MODELS / LEADER_MODEL_* explicitly
# and must be hermetic. Clear any inherited values first.
for _k in (
    "LEADER_MODELS", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "OPENAI_API_KEY",
    "LEADER_MODEL_HIGH", "LEADER_MODEL_BALANCE", "LEADER_MODEL_FAST",
):
    os.environ.pop(_k, None)

import specialist_agents as sa  # noqa: E402

# Minimal shared creds so per-entry fallbacks resolve (we never make a network call).
os.environ["LLM_BASE_URL"] = "https://example.test/v3"
os.environ["LLM_API_KEY"] = "test-key"


def _check(label: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return cond


def _set_registry() -> None:
    os.environ["LEADER_MODELS"] = (
        '{"flash":{"model":"deepseek-v4-flash"},'
        '"pro":{"model":"deepseek-v4-pro-260425"},'
        '"glm":{"model":"glm-5.2"}}'
    )
    sa.reset_models_cache()


def main() -> int:
    failures: list[str] = []
    print("Self-check: model-tiers (hermetic, no DB, no network)")

    # 1. set tier resolves to its entry's spec
    _set_registry()
    os.environ["LEADER_MODEL_FAST"] = "flash"
    cfg, err = sa.resolve_tier("fast")
    if not _check("resolve_tier('fast') → flash spec", cfg is not None and err is None and cfg["model"] == "deepseek-v4-flash", str(err)):
        failures.append("resolve-set")

    # 2. unset tier → (None, None)
    os.environ.pop("LEADER_MODEL_BALANCE", None)
    cfg, err = sa.resolve_tier("balance")
    if not _check("resolve_tier('balance') unset → (None, None)", cfg is None and err is None, f"cfg={cfg} err={err}"):
        failures.append("resolve-unset")

    # 3. dangling tier → (None, error)
    os.environ["LEADER_MODEL_HIGH"] = "ghost"  # not in LEADER_MODELS
    cfg, err = sa.resolve_tier("high")
    if not _check(
        "resolve_tier('high') dangling → (None, error)",
        cfg is None and err is not None and "ghost" in err and "not in LEADER_MODELS" in err,
        str(err),
    ):
        failures.append("resolve-dangling")

    # 4. build_llm propagates dangling tier as a HARD error (no llm, error set, reason None)
    llm, err, reason = sa.build_llm("high")
    if not _check(
        "build_llm('high') dangling → hard error (no network)",
        llm is None and err is not None and reason is None,
        f"err={err} reason={reason}",
    ):
        failures.append("build_llm-dangling")

    # 5. build_llm resolves a set tier to a CrewAI LLM (when crewai importable)
    os.environ["LEADER_MODEL_FAST"] = "flash"
    sa.reset_models_cache()
    try:
        import crewai  # type: ignore  # noqa: F401
        crewai_available = True
    except ImportError:
        crewai_available = False
    if crewai_available:
        llm, err, reason = sa.build_llm("fast")
        # A valid tier MUST NOT produce a hard error (err must be None). The LLM
        # may still fail to construct when litellm is absent (crewai raises →
        # soft "LLM build failed" fallback, by design) — that is environmental,
        # not a tier-resolution bug. So: pass when an LLM is built OR the build
        # soft-fails, as long as no hard error is surfaced.
        ok = err is None and (llm is not None or (reason is not None and "LLM build failed" in reason))
        if not _check("build_llm('fast') → LLM or soft build-fail (no hard error)", ok, f"err={err} reason={reason}"):
            failures.append("build_llm-set")
    else:
        _check("build_llm('fast') → skipped (crewai unavailable)", True, "non-fatal")

    # 6. list_model_tiers reports set / unset / dangling
    _set_registry()
    os.environ["LEADER_MODEL_FAST"] = "flash"      # set
    os.environ.pop("LEADER_MODEL_BALANCE", None)   # unset
    os.environ["LEADER_MODEL_HIGH"] = "ghost"      # dangling
    tiers = sa.list_model_tiers()["tiers"]
    ok = (
        tiers["fast"] == {"entry": "flash", "model": "deepseek-v4-flash", "provider": None, "vision": False}
        and tiers["balance"] is None
        and tiers["high"] == {"entry": "ghost", "error": "not in LEADER_MODELS"}
    )
    if not _check("list_model_tiers reports set/unset/dangling", ok, str(tiers)):
        failures.append("list_model_tiers-mixed")

    # 7. list_agent_models carries the tiers mapping
    lam = sa.list_agent_models()
    if not _check("list_agent_models carries tiers mapping", "tiers" in lam and set(lam["tiers"].keys()) == {"high", "balance", "fast"}):
        failures.append("list_agent_models.tiers")

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed: {failures}")
        return 1
    print("PASS: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
