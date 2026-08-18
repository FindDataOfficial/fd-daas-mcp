# daas skill review rubric

The checklist `fd-daas-skill-review` applies to every `fd-daas-*` skill. Each
check maps to exactly one defect class from the `fd-daas-skills-test-suite`
vocabulary. The automated L1 part is `scripts/skill_smoke_test.py`; the rest is
judgment applied by the reviewer (human or AI).

## L1 - static (automated via `skill_smoke_test.py`)

| Check | Defect class | How |
| --- | --- | --- |
| `SKILL.md` exists with `---` frontmatter | `malformed` | parse frontmatter block |
| Frontmatter has non-empty `name` and `description` | `malformed` | parse frontmatter |
| Every referenced script (`scripts/x.py` or `.claude/skills/.../scripts/x.py`) exists | `script-bug` | resolve path |
| Every referenced script parses (syntax) | `script-bug` | `py_compile` |
| Every referenced script runs without `ImportError` on `--help`/`--list-ops`/`--resolve`/no-arg | `script-bug` | `uv run python <script> ...` (best-effort; `--no-run` to skip) |
| No reference to a removed CLI (`fd-akshare`/`fd-yfinance`/`fd-dartlab`/`fd-edgar`/`fd-edinet`/`fd-world`) | `stale-ref` | grep |
| No reference to a removed skill (`fd-daas-workflow-creator`/`fd-daas-scraw-scrapling`/...) | `stale-ref` | grep |
| No reference to a dropped MCP group (`scrapling-mcp`/`firecrawl-mcp`/`massive-mcp`) | `stale-ref` | grep |
| No `mcp__*` tool name | `stale-ref` | grep `mcp__` |
| No old/foreign DB URL (`sqlite:///mcp/`, `localhost:5432/finddata`) | `stale-ref` | grep |
| Every non-`scraw_*`/non-`zz_test_*` `daas.db` table named in SQL exists in the schema | `stale-ref` | query `sqlite_master` |
| Two skills' `description` fields overlap heavily (jaccard >= 0.6) | `routing-drift` | manual confirm |

## L1 - static (judgment)

| Check | Defect class |
| --- | --- |
| Markdown is well-formed; internal links resolve; no dead `references/`/`scripts/` pointers | `malformed` |
| `description` triggers on the skill's intent AND names the skill's distinct job (not just generic verbs) | `routing-drift` |
| `description` does not collide with another `fd-daas-*` skill's triggers (see `fd-daas-skill-creator/references/daas-concepts.md` §9) | `routing-drift` |
| If the skill runs a workflow, it inlines the `skill-run-notification` block with the four required fields (`**Skill:**`/`**Status:**`/`**Produced:**`/`**Next:**`) | `malformed` (missing convention) |

## L2 - functional (judgment, on a known test input)

| Check | Defect class |
| --- | --- |
| The documented happy-path runs end-to-end on `daas.db` and produces the promised artifact (`observations` row / `scraw_<slug>` table / registered dashboard / collection member / search hit / plan doc) | `script-bug` (if it errors) |
| The skill's skip-if-already-done checks actually skip (no duplicate artifacts) | `script-bug` |
| Test isolation uses throwaway names (`zz_test_*`/`*_test`/`zz-test-*`) and cleans up | `script-bug` (if it pollutes) |
| Network/install-gated steps are relaxed to a code-path check and the relaxation is recorded | (not a defect) |

## Clean exit

A skill passes when L1 + L2 are both clean (zero open defects). A defect that
survives a fix attempt stays open and blocks completion. Every fix is applied
through `fd-daas-skill-creator` / `fd-coding-skill-creator`, scoped to the
defect (no bundled edits), and the failing tier is re-run afterward.
