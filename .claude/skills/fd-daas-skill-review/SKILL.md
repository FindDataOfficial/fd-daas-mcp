---
name: fd-daas-skill-review
description: Review, check, test, and repair daas-mcp skills. Use this skill whenever the user wants to review a daas skill, run the fd-daas-* skill smoke tests, check skills for staleness/routing problems, or test-and-repair the skill family. Trigger on phrases like "review the fd-daas skills", "check the daas skills", "test and repair the skills", "检查修复一下 daas skills", "审一下这个 skill", "跑一下 skill 的冒烟测试". This skill runs the L1 static smoke harness (scripts/skill_smoke_test.py), applies the review rubric, performs L2 functional checks, classifies defects with the fixed vocabulary, and routes every fix through fd-coding-skill-creator / fd-daas-skill-creator. It also verifies the skill-run-notification convention for adopting skills. Do NOT use this for creating a new skill (use fd-daas-skill-creator) - this skill reviews/repairs existing ones.
---

# fd-daas-skill-review

Review + test + repair loop for the `fd-daas-*` skill family. It owns the
review rubric AND orchestrates the `fd-daas-skills-test-suite` L1+L2 contract:
the deterministic L1 part is `scripts/skill_smoke_test.py`; L2 functional +
repair are AI-driven through `fd-daas-skill-creator` / `fd-coding-skill-creator`.

## Mental model

1. **L1 (automated)** - run `scripts/skill_smoke_test.py` over every in-scope
   skill. It flags `malformed` / `script-bug` / `stale-ref` / `routing-drift`
   candidates deterministically (offline, no network).
2. **L1 (judgment)** - apply `references/review-rubric.md` by hand: markdown
   well-formedness, trigger quality/collisions, run-notification adoption.
3. **L2 (functional)** - for each skill, run its documented happy-path on a
   known test input against `daas.db`; confirm the promised artifact appears.
   Relax network/install-gated steps to a code-path check and record it.
4. **Repair** - every confirmed defect is fixed via `fd-daas-skill-creator` /
   `fd-coding-skill-creator` (description-optimization path for `routing-drift`),
   each fix scoped to the defect, then re-run the failing tier.
5. **Report** - write the per-skill report to
   `daas-doc/skills-test-report/<timestamp>-report.md`.

## Scope

In scope: every `.claude/skills/fd-daas-*` dir that ships a `SKILL.md`.
Out of scope: `fd-coding-*` (not data skills). The harness auto-excludes
`fd-coding-*`; `fd-coding-daas-datasource-builder-workspace` (no `SKILL.md`) is
flagged in the report for a removal decision, not tested as a skill.

## Step 1 - Run the L1 harness

```bash
uv run python .claude/skills/fd-daas-skill-review/scripts/skill_smoke_test.py --pretty
# single skill:
uv run python .claude/skills/fd-daas-skill-review/scripts/skill_smoke_test.py --skill fd-daas-research --pretty
# skip the best-effort script-run check (if uv/deps unavailable):
uv run python .claude/skills/fd-daas-skill-review/scripts/skill_smoke_test.py --no-run
```

The JSON report has `skills[].{name,l1_pass,defects[]}`, `excluded[]`,
`routing_drift_candidates[]`, and `summary`. Parse it; the `defects[].class` is
already the fixed vocabulary.

## Step 2 - Apply the rubric (L1 judgment + run-notification)

Read `references/review-rubric.md`. For each skill, confirm:
- markdown is well-formed; internal links resolve (`malformed`);
- the `description` triggers on the skill's distinct job without colliding
  with another `fd-daas-*` skill (`routing-drift`) - cross-check the family
  list in `fd-daas-skill-creator/references/daas-concepts.md` §9;
- if the skill runs a workflow, it inlines the `skill-run-notification` block
  with the four required fields (`**Skill:**`/`**Status:**`/`**Produced:**`/
  `**Next:**`) (`malformed` if missing).

## Step 3 - L2 functional

For each skill, execute its documented happy-path on a known test input. Use
throwaway names (`zz_test_*` slugs, `*_test` collections, `zz-test-*`
dashboards) and clean up after. Confirm the promised artifact appears:
- fetch skill -> an `observations` row or `scraw_<slug>` table;
- indicators-creator -> a `scraw_<slug>` table + `indicator_rules` row;
- dashboard-creator -> a `dashboards` registry row + HTML;
- collection-creator -> a collection member row;
- research -> a `researches` row + `researches/<name>.md`;
- brainstorm -> a `daas-doc/research/<plan>.md` (and no `daas.db` state).

Relax network/install-gated L2 (akshare/yfinance/edgar live calls) to a
code-path check (read the script, confirm the call shape) and record the
relaxation in the report.

## Step 4 - Repair

For every confirmed defect, fix via `fd-daas-skill-creator` (create/edit path)
or `fd-coding-skill-creator` (use the description-optimization path for
`routing-drift`). Keep each fix scoped to the defect - no bundled edits. After
each fix, re-run the failing tier (L1 via the harness, L2 via the happy-path)
until the skill is clean.

## Step 5 - Report

Write `daas-doc/skills-test-report/<timestamp>-report.md` (create the dir on
first use). One entry per in-scope skill: final L1/L2 status, defect classes
found, fixes applied (and via which `fd-coding-skill-creator` path), known
limitations (e.g. network-gated L2 relaxed). The change is complete only when
every in-scope skill passes L1+L2 with zero open defects.

## Run-notification

Emit this block at the end of every review/test+repair run:

```
## Run Complete

**Skill:** fd-daas-skill-review
**Status:** <N>/<M> skills clean; <K> defects fixed
**Produced:** daas-doc/skills-test-report/<timestamp>-report.md
**Next:** re-run after any skill edit; archive the change when all green.
```

(Use `## Run Paused` if a defect survives a fix attempt and needs a decision,
or `## Run Failed` if the harness itself errors.) See the `skill-run-notification`
spec for the full convention.
