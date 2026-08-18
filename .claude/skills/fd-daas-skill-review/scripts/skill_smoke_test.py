#!/usr/bin/env python3
"""L1 static smoke-test harness for the fd-daas-* skill family.

Implements the L1 tier of the `fd-daas-skills-test-suite` contract: for every
`fd-daas-*` skill (excluding `fd-coding-*`), check

  - **malformed**: SKILL.md present with valid `name` + `description` frontmatter.
  - **script-bug**:  every referenced script path exists, parses, and (best
    effort) runs without ImportError on its --help/--list-ops/--resolve/no-arg
    surface.
  - **stale-ref**:   references to removed CLIs / dropped MCP groups / `mcp__*`
    tool names / old DB URLs / `fd-daas-workflow-creator`, or a `daas.db`
    table that does not exist.
  - **routing-drift**: two skills whose `description` fields overlap heavily
    (flagged for manual confirmation).

L2 (functional) + repair are AI-driven through `fd-daas-skill-creator` /
`fd-coding-skill-creator`; this script is the deterministic L1 part.

Usage:
  python skill_smoke_test.py                # all fd-daas-* skills, JSON to stdout
  python skill_smoke_test.py --skill fd-daas-research
  python skill_smoke_test.py --no-run       # skip the best-effort script run
  python skill_smoke_test.py --pretty       # indented JSON

Offline: no network. `uv run` (for the script-run check) uses the already-synced
project venv and is skipped with `--no-run`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import py_compile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # scripts/ -> skill -> skills -> .claude -> repo
SKILLS_DIR = REPO / ".claude" / "skills"

# Removed surfaces (CLAUDE.md "Removed" + dropped MCP groups).
REMOVED_CLIS = ["fd-akshare", "fd-yfinance", "fd-dartlab", "fd-edgar", "fd-edinet", "fd-world"]
REMOVED_SKILLS = [
    "fd-daas-workflow-creator", "fd-daas-scraw-scrapling",
    "fd-daas-scrapling-scraw-creator", "fd-daas-cli-datasource-entities-builder",
]
DROPPED_MCP_GROUPS = ["scrapling-mcp", "firecrawl-mcp", "massive-mcp"]
OLD_DB_HINTS = ["sqlite:///mcp/", "localhost:5432/finddata"]  # old/foreign DB URLs

# A line that mentions a removed surface in a do-not-reference / negative context
# (e.g. "No `fd-akshare` CLI", "the removed workflow-creator", "mcp__* is gone")
# is documentation, not usage. Skip those.
NEG_CUE = re.compile(
    r"\b(no|not|removed?|do\s+not|don't|never|gone|without|instead|dropped?|avoid|forbidden|deprecated|replace[ds]?)\b",
    re.I,
)


def _stale_hits(text: str, token: str, is_regex: bool = False) -> list[int]:
    """Line numbers where `token` appears OUTSIDE a negative-cue line.

    A negative cue on the line OR the previous line counts - do-not-reference
    lists commonly wrap across lines (e.g. "... no deleted CLIs,\\n ... or
    `fd-daas-workflow-creator`.").
    """
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines, 1):
        found = bool(re.search(token, line)) if is_regex else (token in line)
        if not found:
            continue
        prev = lines[i - 2] if i >= 2 else ""
        if NEG_CUE.search(line) or NEG_CUE.search(prev):
            continue
        out.append(i)
    return out

# Scripts referenced in SKILL.md: either an absolute-from-repo `.claude/skills/.../scripts/x.py`
# or a skill-relative `scripts/x.py` (the `scripts/` must be at a token start so it does not
# match a sibling-skill path like `fd-daas-skill-review/scripts/...`).
SCRIPT_RE = re.compile(r"(?:\.claude/skills/[^/\s`\"']+/(?:scripts/)?|(?<![\w/.-])scripts/)[A-Za-z0-9_./-]+\.py")
SQL_TABLE_RE = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([A-Za-z_][A-Za-z0-9_]*)")


def load_env_db_url() -> Path | None:
    """Resolve DAAS_DATABASE_URL (sqlite:///...) from repo-root .env, relative to repo root."""
    url = os.environ.get("DAAS_DATABASE_URL")
    if not url:
        env = REPO / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DAAS_DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip("'\"")
                    break
    if not url:
        url = "sqlite:///daas.db"
    if url.startswith("sqlite:///"):
        rel = url[len("sqlite:///"):]
        p = Path(rel)
        return p if p.is_absolute() else (REPO / p)
    return None


def db_tables(db_path: Path) -> set[str] | None:
    if not db_path or not db_path.exists():
        return None
    try:
        import sqlite3
        con = sqlite3.connect(str(db_path))
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        con.close()
        return {r[0] for r in rows}
    except Exception:
        return None


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end].strip()
    fm: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def find_skill_dirs() -> list[Path]:
    out = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if d.name.startswith("fd-daas-"):
            out.append(d)
    return out


def referenced_scripts(text: str, skill_dir: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for m in SCRIPT_RE.findall(text):
        raw = m
        if raw.startswith(".claude/"):
            p = REPO / raw
        else:  # scripts/...
            p = skill_dir / raw
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        found.append(p)
    return found


def best_effort_run(script: Path) -> tuple[bool, str]:
    """Return (ok, detail). ok=False only on ImportError/ModuleNotFoundError."""
    for args in (["--help"], ["--list-ops"], ["--resolve", "__nonexistent__"], []):
        try:
            r = subprocess.run(
                ["uv", "run", "python", str(script), *args],
                capture_output=True, text=True, timeout=20, cwd=str(REPO),
            )
        except FileNotFoundError:
            return True, "uv not found; run-check skipped"
        except subprocess.TimeoutExpired:
            continue
        err = (r.stderr or "") + (r.stdout or "")
        if "ImportError" in err or "ModuleNotFoundError" in err:
            return False, f"ImportError on `{' '.join(args)}`: {err.strip()[:200]}"
        # click --help exits 0; argparse --help exits 0; missing-arg exits 2 - all fine.
        return True, f"ran `{' '.join(args)}` (rc={r.returncode})"
    return True, "no run surface responded"


def check_skill(skill_dir: Path, tables: set[str] | None, do_run: bool) -> dict:
    name = skill_dir.name
    defects: list[dict] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"name": name, "l1_pass": False,
                "defects": [{"class": "malformed", "detail": "SKILL.md missing"}]}
    text = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if fm is None:
        defects.append({"class": "malformed", "detail": "frontmatter block missing/malformed"})
        fm = {}
    if not fm.get("name"):
        defects.append({"class": "malformed", "detail": "frontmatter missing `name`"})
    if not fm.get("description"):
        defects.append({"class": "malformed", "detail": "frontmatter missing `description`"})

    # scripts
    for p in referenced_scripts(text, skill_dir):
        if not p.exists():
            defects.append({"class": "script-bug", "detail": f"referenced script missing: {p}"})
            continue
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            defects.append({"class": "script-bug", "detail": f"syntax error in {p.name}: {e}"})
            continue
        if do_run:
            ok, detail = best_effort_run(p)
            if not ok:
                defects.append({"class": "script-bug", "detail": f"{p.name}: {detail}"})

    # stale removed-surface references - skip do-not-reference (negative-cue) lines
    for token in REMOVED_CLIS:
        pat = rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])"
        hits = _stale_hits(text, pat, is_regex=True)
        if hits:
            defects.append({"class": "stale-ref", "detail": f"references removed CLI `{token}` (line {hits[0]})"})
    for token in REMOVED_SKILLS:
        hits = _stale_hits(text, token)
        if hits:
            defects.append({"class": "stale-ref", "detail": f"references removed skill `{token}` (line {hits[0]})"})
    for token in DROPPED_MCP_GROUPS:
        hits = _stale_hits(text, token)
        if hits:
            defects.append({"class": "stale-ref", "detail": f"references dropped MCP group `{token}` (line {hits[0]})"})
    for hint in OLD_DB_HINTS:
        hits = _stale_hits(text, hint)
        if hits:
            defects.append({"class": "stale-ref", "detail": f"old/foreign DB URL `{hint}` (line {hits[0]})"})
    # mcp__ tool names: real per-source shape only, outside negative-cue lines.
    mcp_hits = _stale_hits(text, r"mcp__[a-z0-9]+__[a-z0-9_]+", is_regex=True)
    if mcp_hits:
        defects.append({"class": "stale-ref", "detail": f"references `mcp__*` tool name (line {mcp_hits[0]})"})

    # stale daas.db table references
    if tables is not None:
        referenced = set()
        for m in SQL_TABLE_RE.findall(text):
            referenced.add(m)
        for tbl in sorted(referenced):
            if tbl.lower() in {"sqlite_master", "dual"} or tbl.startswith("scraw_") or tbl.startswith("zz_test_"):
                continue
            if tbl not in tables:
                defects.append({"class": "stale-ref", "detail": f"daas.db table `{tbl}` not found in schema"})

    return {"name": name, "l1_pass": not defects, "defects": defects}


def routing_collisions(skills: list[dict]) -> list[dict]:
    """Flag description pairs with heavy word overlap (manual-confirm routing-drift)."""
    descs = []
    for s in skills:
        fm = parse_frontmatter((SKILLS_DIR / s["name"] / "SKILL.md").read_text(encoding="utf-8")) or {}
        words = set(re.findall(r"[A-Za-z_]{4,}", (fm.get("description") or "").lower()))
        descs.append((s["name"], words))
    out = []
    for i in range(len(descs)):
        for j in range(i + 1, len(descs)):
            a, wa = descs[i]
            b, wb = descs[j]
            inter = wa & wb
            union = wa | wb
            if not union:
                continue
            jacc = len(inter) / len(union)
            if jacc >= 0.6:
                out.append({"class": "routing-drift",
                            "detail": f"`{a}` and `{b}` descriptions overlap (jaccard={jacc:.2f}); confirm triggers are distinct"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", help="single skill name to check")
    ap.add_argument("--no-run", action="store_true", help="skip best-effort script run check")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    tables = db_tables(load_env_db_url())
    dirs = find_skill_dirs()
    if args.skill:
        d = SKILLS_DIR / args.skill
        dirs = [d] if d.exists() and d.is_dir() else []
    skills = [check_skill(d, tables, not args.no_run) for d in dirs]

    # excluded fd-coding-* (not fd-daas-* data skills) - flag the known workspace
    excluded = []
    ws = SKILLS_DIR / "fd-coding-daas-datasource-builder-workspace"
    if ws.exists():
        excluded.append({"name": ws.name, "reason": "non-skill eval workspace; flagged for removal decision"})

    report = {
        "skills": skills,
        "excluded": excluded,
        "routing_drift_candidates": routing_collisions(skills),
        "daas_db_checked": bool(tables),
        "summary": {
            "total": len(skills),
            "l1_pass": sum(1 for s in skills if s["l1_pass"]),
            "l1_fail": sum(1 for s in skills if not s["l1_pass"]),
        },
    }
    print(json.dumps(report, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0 if report["summary"]["l1_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
