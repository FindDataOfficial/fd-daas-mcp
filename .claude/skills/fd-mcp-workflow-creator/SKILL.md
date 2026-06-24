---
name: fd-mcp-workflow-creator
description: >
  Create multi-phase workflow definitions following this project's YAML conventions.
  Use this skill whenever the user asks to create a workflow, define a pipeline,
  set up a multi-step process, add a new workflow type, or mentions putting a
  workflow in the registry. Also use it when the user talks about "workflow YAML",
  "phases", "fan-out", "adversarial verification", or needs a structured multi-agent
  process for a task like code review, research, migration, or testing.
---

# Create Workflow

Create multi-phase workflow definitions that follow this project's YAML conventions.

## Where things live

- **Full registry**: `save/template.workflows.yaml` (all workflows, for bootstrapping)
- **Single template**: `template/workflow/template.workflow.yaml` (minimal skeleton)
- **Single entry**: paste into the `registry` array of any workflows YAML file

## Before you start

Read `template/workflow/template.workflow.yaml` for the exact single-entry skeleton. Read `template/workflow/template.workflows.yaml` to see the existing 8 workflows and understand the naming/style conventions.

## Workflow structure

```yaml
- id: <kebab-case-name>
  description: <one-line summary>
  model_tier: high|middle|low         # model for all agents in this workflow
  model_env: <ENV_VAR_NAME>           # optional: override via env var
  phases:
    - title: <Phase Name>
      detail: <what happens in this phase>
    - title: <Phase Name>
      detail: <what happens in this phase>
  rules:
    require_approval_before_implement: true|false
    max_parallel_agents: <int>
    timeout_per_phase_seconds: <int>
  use_cases:
    - <use case 1>
    - <use case 2>
```

## Phase design

A good workflow typically has 2-4 phases. Each phase should be a distinct, independently-describable step. Common patterns:

| Pattern | Phases | Example |
|---|---|---|
| Understand → Build | Understand, Design, Implement, Review | understand-and-implement |
| Find → Verify | Review/Scan, Verify | code-review-pipeline, security-audit |
| Search → Synthesize | Search, Fetch, Verify, Synthesize | deep-research |
| Discover → Transform | Discover, Transform, Verify | migrate-codebase |
| Analyze → Generate | Analyze, Generate, Verify | test-coverage-sweep |
| Diagnose → Fix | Reproduce, Isolate, Fix, Regression Check | bug-triage |

## Conventions

- **id**: lowercase with hyphens, describes the overall goal (e.g. `code-review-pipeline`, `deep-research`)
- **model_tier**: pick based on the workflow's cognitive demands — `high` for security audits and deep research, `middle` for migrations and test generation, `low` for documentation sweeps
- **model_env**: name it `WORKFLOW_<UPPER_SNAKE>_MODEL`
- **phases**: each phase title is a single verb or short noun phrase (Understand, Design, Implement, Review). The detail expands on what agents do in that phase.
- **require_approval_before_implement**: `true` for workflows that modify code (understand-and-implement, migrate-codebase). `false` for read-only workflows (review, research, audit).
- **max_parallel_agents**: higher for fan-out work (migrate: 16, review: 12), lower for sequential debugging (bug-triage: 6)
- **timeout_per_phase_seconds**: longer for complex phases (security audit: 1200), shorter for simple ones (code review: 300)

## Workflow

1. Read `template/workflow/template.workflow.yaml` for the skeleton
2. Read `template/workflow/template.workflows.yaml` to see existing workflows and avoid duplicates
3. Understand what the user wants the workflow to accomplish — ask clarifying questions if the phases, approval requirements, or parallelism aren't clear
4. Write the workflow entry. If the user wants to add to the registry, edit `save/template.workflows.yaml` (and `template/workflow/template.workflows.yaml`) to add the new entry. If they just want the definition, output it directly.
