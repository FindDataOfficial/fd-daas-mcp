# Author a Skill

DAAS skills live in `.claude/skills/`. Two meta-skills handle creation - use the
domain wrapper, not the generic one, for a daas skill.

## Which creator to use

| You are creating | Use |
| --- | --- |
| An `fd-daas-*` data skill | `fd-daas-skill-creator` (wraps `fd-coding-skill-creator`, injects daas guardrails) |
| An `fd-coding-*` infra/builder skill | `fd-coding-skill-creator` directly (or a domain wrapper if one exists) |
| A docs-site skill | `fd-coding-documents-builder` / `fd-coding-documents-add` |

**Do not** use `fd-coding-skill-creator` directly for a daas skill - you'd skip
the daas guardrails (live-surface check, `daas.db` tables, dispatch prefixes,
`daas-doc/` paths, run-notification, defect vocabulary).

## The creation loop

`fd-coding-skill-creator` runs: **draft -> evals -> review -> iterate ->
(optional) description optimization**. `fd-daas-skill-creator` delegates the
mechanics to it and layers daas correctness on top.

1. **Capture intent** - what the skill does, when it triggers (EN+ZH phrasing),
   expected output, whether it needs test cases. For a daas skill also pin:
   which `daas.db` tables it reads/writes, which dispatch prefix (if it fetches),
   which `daas-doc/` path it writes, whether it adopts `skill-run-notification`.
2. **Delegate the craft** to `fd-coding-skill-creator`.
3. **Apply the daas guardrails** - the new skill's `description` triggers without
   colliding with the existing family (`routing-drift`); references no removed
   surface (`stale-ref`); uses correct table names + dispatch prefixes; writes
   docs under `daas-doc/`; adopts `skill-run-notification` if it runs a workflow.
4. **Verify** with the inspect/validate flow.

## Anatomy of a skill

```
.claude/skills/<name>/
  SKILL.md            # frontmatter (name, description) + instructions
  scripts/            # helper scripts (optional)
  references/         # domain-knowledge markdown (optional)
```

The `description` is the routing key - it must trigger on the right intent and
**not** collide with sibling skills.

## Inspect / review an existing skill

```bash
uv run python .claude/skills/fd-daas-skill-review/scripts/skill_smoke_test.py --skill <name>
```

Defect vocabulary: `malformed`, `script-bug`, `stale-ref`, `routing-drift`.
Report each as `<defect-class>: <skill>: <detail>` and fix through
`fd-coding-skill-creator` (edit path).

## Reference

- `fd-daas-skill-creator` -> `references/daas-concepts.md` - the single source
  of truth for architecture, tables, prefixes, `daas-doc/`, run-notification,
  defect vocabulary, removed surfaces, and the skill family routing boundaries.
