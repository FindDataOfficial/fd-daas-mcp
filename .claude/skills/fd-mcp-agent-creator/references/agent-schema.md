# Agent Schema Reference

## Fields

| Field | Required | Type | Description |
|---|---|---|---|
| `id` | yes | string | Unique kebab-case identifier |
| `description` | yes | string | One-line summary of what this agent does |
| `model_tier` | yes | high\|middle\|low | Fallback model tier |
| `model_env` | no | string | Env var name for per-deployment model override |
| `tools` | yes | list | Allowed tools (Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch) |
| `rules` | yes | map | max_turns, timeout_seconds, allow_parallel, read_only |
| `use_cases` | yes | list | Concrete example tasks |

## Model tier guidelines

| Tier | Use for | Example agents |
|---|---|---|
| `high` | Architecture, debugging, security, complex reasoning | plan, bug-hunter |
| `middle` | General coding, testing, migration, review | general-purpose, test-writer, code-reviewer, migrator |
| `low` | Search, docs, exploration, simple transforms | explore, doc-writer |

## Tool guidelines

| Agent type | Typical tools |
|---|---|
| Read-only search | Read, Glob, Grep, Bash, WebSearch, WebFetch |
| Code writer | Read, Write, Edit, Bash, Glob, Grep |
| Reviewer | Read, Glob, Grep, Bash |
| Full access | Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch |

## Rule defaults by agent type

| Type | max_turns | timeout | allow_parallel | read_only |
|---|---|---|---|---|
| Search/explore | 10-12 | 120-180 | true | true |
| Code writer | 15-30 | 300-600 | false | false |
| Reviewer/planner | 10-15 | 180-300 | false | true |
| Debugger | 25 | 600 | false | false |
| General | 20 | 300 | true | false |
