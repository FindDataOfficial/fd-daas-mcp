# Workflow Schema Reference

## Fields

| Field | Required | Type | Description |
|---|---|---|---|
| `id` | yes | string | Unique kebab-case identifier |
| `description` | yes | string | One-line summary of what this workflow does |
| `model_tier` | yes | high\|middle\|low | Fallback model tier for all agents in this workflow |
| `model_env` | no | string | Env var name for per-deployment model override |
| `phases` | yes | list | Ordered list of {title, detail} objects |
| `rules` | yes | map | require_approval_before_implement, max_parallel_agents, timeout_per_phase_seconds |
| `use_cases` | yes | list | Concrete example tasks |

## Phase design principles

- **2-4 phases** is the sweet spot — fewer feels incomplete, more becomes hard to track
- **Each phase should produce something** the next phase consumes (a map, a set of findings, generated code)
- **Parallel phases** (fan-out within a phase) should be used when work is independent (reviewing 10 files, searching 5 sources)
- **Sequential phases** are for pipelines where each step depends on the previous (understand → design → implement)

## Rule defaults by workflow type

| Type | Approval | Max parallel | Timeout/phase |
|---|---|---|---|
| Code generation | true | 8 | 600 |
| Review/audit | false | 12 | 300-1200 |
| Research | false | 10 | 900 |
| Migration | true | 16 | 1200 |
| Testing | false | 8 | 600 |
| Debugging | false | 6 | 900 |
| Documentation | false | 10 | 600 |

## Common anti-patterns

- **Too many phases**: 6+ phases usually means you're over-decomposing. Merge adjacent phases.
- **Single-phase workflow**: if there's only one phase, it should just be an agent, not a workflow.
- **Wrong approval setting**: workflows that write code without `require_approval_before_implement: true` risk destructive changes.
- **Unbalanced parallelism**: setting `max_parallel_agents: 50` when the workflow only fans out to 3 things wastes the config.
