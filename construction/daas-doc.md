# daas-doc — skill documentation convention

A top-level `daas-doc/` directory at the repo root holds **human-readable markdown** produced by the `fd-daas-*` creator skills. It is distinct from:

- `dashboard/` — the Next.js dashboard app.
- `dashboard/my-charts-dashboard/` — standalone HTML dashboards + their `index.html` / `daas.md` charts index.
- `openspec/` — change proposals + capability specs.

`daas-doc/` is plain markdown (plan/instruction/introduction docs), created on first use by whichever skill runs first. Commit it as documentation (do NOT add to `.gitignore`).

## Layout

```
daas-doc/
├── <workflow-name>/                 # created by fd-daas-workflow-creator
│   ├── plan.md                      # the workflow's plan
│   ├── <custom-name>-dashboard.md   # dashboard instruction (when dashboard-creator is nested)
│   ├── indicators-<collection>.md   # indicators introduction (when indicators-collection-creator is nested)
│   └── indicators-<collection>.csv   # indicators export (CSV, sibling of the .md)
├── dashboard/
│   └── <custom-name>-dashboard.md   # dashboard instruction (standalone)
└── indicators-collections/
    ├── <collection>.md              # indicators introduction (standalone)
    └── <collection>.csv             # indicators export (CSV, sibling of the .md)
```

## Standalone vs nested

A creator skill runs **standalone** by default and writes to its standalone path. When it runs **nested inside `fd-daas-workflow-creator`**, it writes under the workflow's folder instead.

The nesting signal is a `workflow-name <X>` token in the child skill's `args` string (passed by `fd-daas-workflow-creator` when it invokes the child via the `Skill` tool). No env var, no sentinel file — the token is the only signal.

| Skill | Standalone path | Nested path |
|---|---|---|
| `fd-daas-workflow-creator` | `daas-doc/<workflow-name>/plan.md` | (it is the parent) |
| `fd-daas-dashboard-creator` | `daas-doc/dashboard/<custom-name>-dashboard.md` | `daas-doc/<X>/<custom-name>-dashboard.md` |
| `fd-daas-indicators-collection-creator` | `daas-doc/indicators-collections/<collection>.md` + `.csv` | `daas-doc/<X>/indicators-<collection>.md` + `.csv` |

## Workflow-name derivation

`fd-daas-workflow-creator` derives a kebab-case `<workflow-name>` from the summarized goal (slugify, truncate ~40 chars). Fallback on empty goal or folder collision: `workflow-<YYYYMMDD>-<HHMMSS>`. The timestamp is computed in-skill (the skill layer is not subject to the `Workflow` JS sandbox's `Date.now` restriction).

## Rollback

`rm -rf daas-doc/<workflow-name>/` removes one workflow's doc set. `rm -rf daas-doc/` removes everything. No DB rows, no server state — `daas-doc/` is documentation only.
