---
name: fd-daas-skill-creator
description: Create, edit, inspect, and validate daas-mcp skills. Use this skill whenever the user wants to create a new fd-daas-* skill, edit or optimize an existing one, or inspect/validate a daas skill against the daas conventions (architecture, daas.db tables, dispatch prefixes, daas-doc paths, run-notification, defect vocabulary). Trigger on phrases like "create a daas skill", "build a skill for X using daas", "inspect the fd-daas-foo skill", "帮我建一个 daas skill", "检查一下这个 daas skill 写得对不对". This skill wraps fd-coding-skill-creator and injects daas-mcp domain knowledge so created skills are daas-correct by default. Do NOT use fd-coding-skill-creator directly for a daas skill - use this skill so the daas guardrails are applied.
---

# fd-daas-skill-creator

A daas-domain wrapper around `fd-coding-skill-creator`. The skill-creator
handles the generic craft (draft -> evals -> review -> iterate -> description
optimization); this skill layers the **daas-mcp domain guardrails** on top so a
new `fd-daas-*` skill is correct by default: it references only live surfaces,
uses the right `daas.db` tables and dispatch prefixes, writes docs to
`daas-doc/`, and adopts the `skill-run-notification` convention where relevant.

## The daas domain knowledge

Before creating or editing, read **`references/daas-concepts.md`** (in this
skill). It is the single source of truth for: the skill+sqlite architecture,
the `daas.db` table list, the dispatch prefixes, the `daas-doc/` path
conventions, the `skill-run-notification` block, the defect vocabulary, the
removed-surfaces do-not-reference list, and the `fd-daas-*` skill family with
routing boundaries. Inject these as guardrails; do not copy them into the new
skill verbatim - link `daas-concepts.md` and inline only what the new skill
needs.

## Workflow

### Create / edit / optimize a daas skill

1. **Capture intent** - what the skill should do, when it triggers (EN+ZH
   phrasing), expected output, whether it needs test cases. For a daas skill
   also pin down: which `daas.db` tables it reads/writes, which dispatch prefix
   (if it fetches), which `daas-doc/` path it writes, whether it should adopt
   `skill-run-notification`.
2. **Delegate the craft to `fd-coding-skill-creator`** - invoke it for the
   draft -> evals -> review -> iterate -> (optional) description-optimization
   loop. Do not reimplement that loop here.
3. **Apply the daas guardrails** to the draft (this is what this skill adds):
   - The new skill's `description` triggers on its intent **without colliding**
     with the existing `fd-daas-*` family (see `daas-concepts.md` §9) - avoid
     `routing-drift`.
   - It references **no removed surface** (§8) - no deleted CLIs, dropped MCP
     groups, `mcp__*` tool names, old DB URLs, or `fd-daas-workflow-creator`.
   - It uses the correct `daas.db` table names (§2) and dispatch prefixes (§3).
   - Any doc it writes goes under `daas-doc/` at the right path (§5).
   - If it runs a workflow, it inlines the `skill-run-notification` block (§6).
   - It uses **uv** + the repo-root `.env` (§4); `sqlite3 daas.db "..."` from
     repo root for reads; `PRAGMA foreign_keys=ON` for FK cascade.
4. **Verify** with the inspect/validate flow below before handing back.

### Inspect / validate an existing daas skill

Run the same L1 static checks that `fd-daas-skill-review` uses (you can invoke
`fd-daas-skill-review/scripts/skill_smoke_test.py --skill <name>` for the
automated part), then report findings tagged with the defect vocabulary (§7):

- **malformed** - missing `SKILL.md`, bad/missing frontmatter (`name`,
  `description`), broken markdown.
- **script-bug** - a referenced script path is absent, has a syntax/import
  error, or crashes on its `--help`/`--resolve`/`--list-ops`/no-arg surface.
- **stale-ref** - reference to a removed CLI / MCP group / `mcp__*` tool / old
  DB URL / deleted file (§8), or a `daas.db` table/column that does not exist.
- **routing-drift** - trigger description collides with another `fd-daas-*`
  skill.

Report each finding as `<defect-class>: <skill>: <detail>` and propose a fix;
the actual fix is applied through `fd-coding-skill-creator` (edit path), kept
scoped to the defect.

## Guardrails

- **Compose, don't fork.** Always delegate the skill-creation mechanics to
  `fd-coding-skill-creator`; this skill only adds daas guardrails.
- **Link, don't duplicate.** Point the new skill at `daas-concepts.md` for the
  shared background; inline only what it needs.
- **No removed surfaces.** A created skill that references a deleted CLI or
  dropped MCP group is a `stale-ref` defect - catch it before hand-off.
- **No routing collisions.** Two skills claiming the same trigger is
  `routing-drift` - check the family list in `daas-concepts.md` §9.
- **Adopt run-notification where it runs a workflow.** Skills like research,
  brainstorm, dashboard-creator emit the block; one-shot helpers need not.

## Reference files

- `references/daas-concepts.md` - the daas-mcp domain knowledge (architecture,
  tables, prefixes, daas-doc, run-notification, defect vocabulary, removed
  surfaces, skill family).
- `fd-daas-skill-review` (sibling skill) - the review rubric + the
  `skill_smoke_test.py` L1 harness used by the inspect flow.
