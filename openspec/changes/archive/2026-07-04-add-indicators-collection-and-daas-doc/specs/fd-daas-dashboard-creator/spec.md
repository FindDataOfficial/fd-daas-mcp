## ADDED Requirements

### Requirement: Write a dashboard instruction markdown

After building the standalone HTML, the skill SHALL also write an instruction `<custom-name>-dashboard.md` companion doc containing: the dashboard slug, the source `scraw_*` / `observations` tables + columns backing each chart, the refresh cadence (static snapshot vs cron, naming the cron if wired), the `file://` URL of the built HTML, and a one-line "how to refresh" note. The HTML build and the `index.html` / `daas.md` registration (per the existing requirements) are unchanged; the instruction md is additional.

#### Scenario: Standalone instruction md written

- **WHEN** the skill runs standalone (no `workflow-name` token in `args`)
- **THEN** the instruction md is written to `daas-doc/dashboard/<custom-name>-dashboard.md` and its path is reported to the user

#### Scenario: Instruction md content

- **WHEN** the instruction md is written
- **THEN** it lists the dashboard slug, source tables, refresh cadence, and the `file://` URL of the built HTML

### Requirement: Nest under the workflow dir when invoked inside workflow-creator

When the skill's `args` contain a `workflow-name <X>` token, the skill SHALL write the instruction md to `daas-doc/<X>/<custom-name>-dashboard.md` instead of the standalone `daas-doc/dashboard/` path.

#### Scenario: Nested instruction md

- **WHEN** the skill is invoked with `args` containing `workflow-name my-flow`
- **THEN** the instruction md is written to `daas-doc/my-flow/<custom-name>-dashboard.md`
