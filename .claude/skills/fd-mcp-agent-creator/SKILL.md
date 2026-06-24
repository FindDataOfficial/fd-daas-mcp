---
name: fd-mcp-agent-creator
description: >
  Create AI agent definitions following this project's YAML conventions.
  Use this skill whenever the user asks to create an agent, define an agent,
  add a new agent type, set up an agent with specific tools, or mentions
  putting an agent in the registry. Also use it when the user talks about
  "agent configuration", "agent YAML", or needs help picking the right
  model_tier and tools for a task.
---

# Create Agent

Create AI agent definitions that follow this project's YAML conventions.

## Where things live

- **Full registry**: `save/template.agents.yaml` (all agents, for bootstrapping)
- **Single template**: `template/agents/template.agent.yaml` (minimal skeleton)
- **Single entry**: paste into the `registry` array of any agents YAML file

## Before you start

Read `template/agents/template.agent.yaml` for the exact single-entry skeleton. Read `template/agents/template.agents.yaml` to see the existing 8 agents and understand the naming/style conventions.

## Agent structure

Every agent has these fields:

```yaml
- id: <kebab-case-name>         # unique, used as the reference key
  description: <one-line>       # what this agent does
  model_tier: high|middle|low   # fallback model tier
  model_env: <ENV_VAR_NAME>     # optional: override via env var
  tools:                        # allowed tools
    - Read
    - Write
    - ...
  rules:                        # behavioral constraints
    max_turns: <int>
    timeout_seconds: <int>
    allow_parallel: true|false
    read_only: true|false       # optional
  use_cases:                    # example tasks this agent handles
    - <use case 1>
    - <use case 2>
```

## Conventions

- **id**: lowercase with hyphens, descriptive of the role (e.g. `general-purpose`, `bug-hunter`)
- **model_tier**: pick based on task complexity — `high` for architecture/debugging/security, `middle` for general coding, `low` for search/docs/exploration
- **model_env**: name it `AGENT_<UPPER_SNAKE>_MODEL` so it's easy to find and set
- **tools**: list only what the agent actually needs — fewer tools = fewer permission prompts. Read-only agents should not have Write/Edit
- **rules**: `read_only: true` for agents that should never modify files; `allow_parallel: true` for fan-out agents (explore, migrator)
- **use_cases**: concrete examples of what this agent would be asked to do

## Workflow

1. Read `template/agents/template.agent.yaml` for the skeleton
2. Read `template/agents/template.agents.yaml` to see existing agents and avoid duplicates
3. Understand what the user wants the agent to do — ask clarifying questions if the role, tools, or model tier aren't clear
4. Write the agent entry. If the user wants to add to the registry, edit `save/template.agents.yaml` (and `template/agents/template.agents.yaml`) to add the new entry. If they just want the definition, output it directly.
