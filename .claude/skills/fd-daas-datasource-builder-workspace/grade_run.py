#!/usr/bin/env python3
"""Grade a single eval run's outputs against the 17 assertions.

Writes grading.json (with text/passed/evidence per assertion) into the run dir.

Usage:
    python grade_run.py <run_dir>   # e.g. .../eval-1-tiny-econ-end-to-end/with_skill
"""
from __future__ import annotations

import ast
import json
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = "/Users/chengsishi/code/cli-anything/daas.db"


def _load_descriptor(run_dir: Path):
    p = run_dir / "outputs" / "_out" / "daas.descriptor.json"
    if not p.exists():
        return None, f"missing {p}"
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"invalid JSON: {e}"


def _cli_commands(run_dir: Path):
    """Return (list_of_command_names, syntax_ok, err)."""
    p = run_dir / "outputs" / "_out" / "daas_cli.py"
    if not p.exists():
        return [], False, "missing daas_cli.py"
    src = p.read_text(encoding="utf-8")
    try:
        ast.parse(src)
        syntax_ok = True
    except SyntaxError as e:
        syntax_ok = False
    # capture command names from @<grp>.command("name") / @click.command("name")
    names = re.findall(r'\.command\(\s*(?:name=)?["\']([\w-]+)["\']', src)
    return names, syntax_ok, None


def _existing_indicator_names() -> set[str]:
    try:
        conn = sqlite3.connect(DB_PATH)
        return {r[0] for r in conn.execute("SELECT DISTINCT indicator_name FROM indicator_rules")}
    except Exception:
        return set()


def grade(run_dir: Path) -> list[dict]:
    run_dir = run_dir.resolve()
    results = []
    desc, derr = _load_descriptor(run_dir)
    existing_names = _existing_indicator_names()

    def add(text, passed, evidence):
        results.append({"text": text, "passed": bool(passed), "evidence": evidence})

    # 1
    add("daas.descriptor.json exists and is valid JSON",
        desc is not None, derr or "loaded OK")

    # 2 + 3
    cmds, syntax_ok, cerr = _cli_commands(run_dir)
    add("daas_cli.py exists and is syntactically valid Python (ast.parse succeeds)",
        syntax_ok and not cerr, cerr or ("ast.parse OK" if syntax_ok else "SyntaxError"))
    expected_cmds = {"get-cpi-series", "fetch-gdp-quarterly", "list-countries"}
    got = set(cmds)
    add('daas_cli.py commands are exactly {get-cpi-series, fetch-gdp-quarterly, list-countries} (3); fetch_holidays skipped',
        got == expected_cmds,
        f"got={sorted(got)} expected={sorted(expected_cmds)} fetch_holidays_present={'holidays' in ' '.join(cmds).lower()}")

    # 4
    sp = run_dir / "outputs" / "_out" / "daas-skill" / "SKILL.md"
    fm_ok = False
    if sp.exists():
        t = sp.read_text(encoding="utf-8")
        fm_ok = t.startswith("---") and "name:" in t.split("---", 2)[1] and "description" in t.split("---", 2)[1]
    add("daas-skill/SKILL.md exists with YAML frontmatter (name + description)",
        fm_ok, "frontmatter OK" if fm_ok else f"missing/invalid: {sp}")

    # 5
    dp = run_dir / "outputs" / "_out" / "daas-skill" / "dispatch.json"
    dp_ok = False
    if dp.exists():
        try:
            json.loads(dp.read_text(encoding="utf-8")); dp_ok = True
        except Exception:
            pass
    add("daas-skill/dispatch.json exists and is valid JSON", dp_ok,
        "valid JSON" if dp_ok else f"missing/invalid: {dp}")

    # 6
    ip = run_dir / "outputs" / "import_report.txt"
    ip_ok = False
    ip_ev = "missing"
    if ip.exists():
        t = ip.read_text(encoding="utf-8").lower()
        bad = any(b in t for b in ("integrityerror", "unique constraint", "constraint failed"))
        good = any(g in t for g in ("import-ready", "would import", "ok", "no collision", "clean", "success"))
        ip_ok = (not bad) and good
        ip_ev = f"bad_signals={bad} good_signals={good} len={len(t)}"
    add("import_report.txt indicates import-ready, no unique-constraint collisions",
        ip_ok, ip_ev)

    if desc is None:
        # remaining assertions can't be checked; mark all fail with the descriptor error
        for text in [
            "descriptor contains exactly the 4 fetchers and excludes _normalize",
            "get_cpi_series columns include date, cpi_yoy, country",
            "fetch_gdp_quarterly columns include date, gdp_current_usd, gdp_growth_yoy, country",
            "the cpi_yoy column has >=1 proposed_indicator_rule",
            "macro metric columns have a non-empty indicator_match (candidate_new_metric or existing_metric)",
            "proposed indicator_names checked vs daas.db (no unflagged collisions with existing names)",
            "no two proposed_indicator_rules share the same indicator_name (within-file uniqueness)",
            "country entity has matched_existing=true (or a justified note)",
            "every function has a non-empty frequency",
            "every function has confidence in [0,1] AND non-empty confidence_reasoning",
            "get_cpi_series frequency=monthly; fetch_gdp_quarterly frequency=quarterly",
        ]:
            add(text, False, f"descriptor not loadable: {derr}")
        return results

    funcs = {f.get("name"): f for f in desc.get("daas_functions", [])}
    fnames = set(funcs)

    # 7
    add("descriptor contains exactly the 4 fetchers and excludes _normalize",
        fnames == {"get_cpi_series", "fetch_gdp_quarterly", "list_countries", "fetch_holidays"} and "_normalize" not in fnames,
        f"functions={sorted(fnames)}")

    def colnames(fn):
        return {c.get("name") for c in funcs.get(fn, {}).get("columns", [])}

    # 8
    c = colnames("get_cpi_series")
    add("get_cpi_series columns include date, cpi_yoy, country",
        {"date", "cpi_yoy", "country"} <= c, f"columns={sorted(c)}")

    # 9
    c = colnames("fetch_gdp_quarterly")
    add("fetch_gdp_quarterly columns include date, gdp_current_usd, gdp_growth_yoy, country",
        {"date", "gdp_current_usd", "gdp_growth_yoy", "country"} <= c, f"columns={sorted(c)}")

    # 10
    cpi_rules = []
    for col in funcs.get("get_cpi_series", {}).get("columns", []):
        if col.get("name") == "cpi_yoy":
            cpi_rules = col.get("proposed_indicator_rules", [])
    add("the cpi_yoy column has >=1 proposed_indicator_rule",
        len(cpi_rules) >= 1, f"cpi_yoy proposed_rules={len(cpi_rules)}")

    # 11 (reframed: non-empty indicator_match on macro metrics, reflecting a real classification)
    macro_ok = True
    macro_ev = []
    for fn in ("get_cpi_series", "fetch_gdp_quarterly"):
        for col in funcs.get(fn, {}).get("columns", []):
            nm = col.get("name", "")
            if nm in ("date", "country", "market", "name", "code"):
                continue
            m = col.get("indicator_match", "")
            if m not in ("candidate_new_metric", "existing_metric"):
                macro_ok = False
                macro_ev.append(f"{fn}.{nm} indicator_match='{m}'")
    add("macro metric columns have a non-empty indicator_match (candidate_new_metric or existing_metric)",
        macro_ok, "all classified" if macro_ok else "; ".join(macro_ev))

    # 12 (proxy: no proposed name collides with an existing daas.db name UNLESS dedup_status=exists)
    collisions = []
    for fn, f in funcs.items():
        for col in f.get("columns", []):
            for ind in col.get("proposed_indicator_rules", []):
                nm = ind.get("indicator_name", "")
                ds = ind.get("dedup_status", "")
                if nm in existing_names and ds != "exists":
                    collisions.append(f"{nm} (dedup_status={ds})")
    add("proposed indicator_names checked vs daas.db (no unflagged collisions with existing names)",
        not collisions, f"unflagged_collisions={collisions}" if collisions else f"checked against {len(existing_names)} existing names")

    # 13 within-file uniqueness
    all_names = []
    for f in funcs.values():
        for col in f.get("columns", []):
            for ind in col.get("proposed_indicator_rules", []):
                all_names.append(ind.get("indicator_name", ""))
    dups = {n for n in all_names if all_names.count(n) > 1}
    add("no two proposed_indicator_rules share the same indicator_name (within-file uniqueness)",
        not dups, f"duplicates={sorted(dups)}" if dups else "all unique")

    # 14 country entity matched_existing=true
    country_ok = False
    country_ev = "no country entity found"
    for f in funcs.values():
        for e in f.get("entities", []):
            if e.get("entity_type") == "country":
                country_ok = e.get("matched_existing") is True
                country_ev = f"matched_existing={e.get('matched_existing')} note={e.get('note','')}"
    add("country entity has matched_existing=true (or a justified note)",
        country_ok, country_ev)

    # 15 frequency non-empty
    freq_ok = all(f.get("frequency") for f in funcs.values())
    add("every function has a non-empty frequency", freq_ok,
        {fn: f.get("frequency") for fn, f in funcs.items()})

    # 16 confidence + reasoning
    conf_ok = True
    conf_ev = []
    for fn, f in funcs.items():
        c = f.get("confidence")
        r = f.get("confidence_reasoning", "")
        if c is None or not (0.0 <= float(c) <= 1.0) or not r:
            conf_ok = False
            conf_ev.append(f"{fn}: confidence={c} reasoning_len={len(r)}")
    add("every function has confidence in [0,1] AND non-empty confidence_reasoning",
        conf_ok, "all OK" if conf_ok else "; ".join(conf_ev))

    # 17 CPI=monthly, GDP=quarterly
    cpi_f = funcs.get("get_cpi_series", {}).get("frequency", "")
    gdp_f = funcs.get("fetch_gdp_quarterly", {}).get("frequency", "")
    add("get_cpi_series frequency=monthly; fetch_gdp_quarterly frequency=quarterly",
        cpi_f == "monthly" and gdp_f == "quarterly",
        f"cpi={cpi_f} gdp={gdp_f}")

    return results


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: grade_run.py <run_dir>")
    run_dir = Path(sys.argv[1])
    results = grade(run_dir)
    out = run_dir / "grading.json"
    out.write_text(json.dumps({"expectations": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(1 for r in results if r["passed"])
    print(f"{run_dir.name}: {passed}/{len(results)} passed")
    for r in results:
        print(f"  [{'PASS' if r['passed'] else 'FAIL'}] {r['text']}")
        print(f"        -> {str(r['evidence'])[:160]}")


if __name__ == "__main__":
    main()
