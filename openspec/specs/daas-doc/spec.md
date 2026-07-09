# daas-doc Specification

## Purpose
TBD - created by archiving change add-indicators-collection-and-daas-doc. Update Purpose after archive.
## Requirements
### Requirement: daas-doc directory convention

The system SHALL use a top-level `daas-doc/` directory at the repo root as the home for skill-generated human-readable documentation. Skills SHALL create `daas-doc/` and any needed subdirectories on first use. `daas-doc/` is distinct from the Next.js `dashboard/` app and from `dashboard/my-charts-dashboard/` (the standalone-HTML charts index); it holds markdown plan/instruction docs, not HTML dashboards.

#### Scenario: daas-doc created on first use

- **WHEN** a skill writes its first `daas-doc/` artifact and `daas-doc/` does not exist
- **THEN** the skill creates `daas-doc/` (and the relevant subdirectory) before writing

### Requirement: Standalone doc paths

When a creator skill runs standalone (not nested inside `fd-daas-workflow-creator`), it SHALL write its doc to the path determined by its role:

- `fd-daas-workflow-creator`: `daas-doc/<workflow-name>/plan.md`
- `fd-daas-dashboard-creator`: `daas-doc/dashboard/<custom-name>-dashboard.md`
- `fd-daas-indicators-collection-creator`: `daas-doc/indicators/<collection>.md`

#### Scenario: Standalone dashboard instruction path

- **WHEN** `fd-daas-dashboard-creator` runs standalone (no `workflow-name` token in `args`)
- **THEN** its instruction md is written to `daas-doc/dashboard/<custom-name>-dashboard.md`

#### Scenario: Standalone indicators introduction path

- **WHEN** `fd-daas-indicators-collection-creator` runs standalone
- **THEN** its introduction md is written to `daas-doc/indicators/<collection>.md`

### Requirement: Workflow-scoped nesting paths

When a creator skill runs nested inside `fd-daas-workflow-creator` (signaled by a `workflow-name <X>` token in its `args`), it SHALL write its doc under `daas-doc/<X>/` so the workflow's docs co-locate:

- `fd-daas-dashboard-creator`: `daas-doc/<X>/<custom-name>-dashboard.md`
- `fd-daas-indicators-collection-creator`: `daas-doc/<X>/indicators-<collection>.md`

#### Scenario: Nested dashboard instruction

- **WHEN** `fd-daas-dashboard-creator` is invoked with `workflow-name my-flow`
- **THEN** its instruction md is written to `daas-doc/my-flow/<custom-name>-dashboard.md`

#### Scenario: Nested indicators introduction

- **WHEN** `fd-daas-indicators-collection-creator` is invoked with `workflow-name my-flow`
- **THEN** its introduction md is written to `daas-doc/my-flow/indicators-<collection>.md`

### Requirement: Nesting context passed via skill args

`fd-daas-workflow-creator` SHALL pass the workflow-name to nested child skills by including a `workflow-name <X>` token in the `args` string of the `Skill` invocation. Child skills SHALL detect this token to switch from the standalone path to the workflow-scoped path. No env var or sentinel file is used — the token is the only nesting signal.

#### Scenario: Workflow-name token triggers nesting

- **WHEN** a child skill's `args` contains `workflow-name my-flow`
- **THEN** the child writes its doc under `daas-doc/my-flow/`

#### Scenario: Absent token means standalone

- **WHEN** a child skill's `args` does not contain a `workflow-name` token
- **THEN** the child writes its doc to its standalone default path
