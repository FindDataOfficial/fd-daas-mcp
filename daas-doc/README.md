# daas-doc index

Skill-generated human-readable documentation for the DAAS project. Markdown only
(not the Next.js `dashboard/` app, not the standalone-HTML charts index).

## Contents

- `mcp-test-suite.md` - how to run the `fd-daas-mcp` pytest suite, what it
  covers, the offline constraint, how optional extras are stubbed.
- `skills-test-report/` - per-skill L1+L2 test+repair reports from the
  `fd-daas-skill-review` harness (`<timestamp>-report.md`).
- `research/` - research-plan markdowns written by `fd-daas-brainstorm`
  (`<plan-slug>.md`), consumed by `fd-daas-research` to pre-fill a study.
- `dashboard/` - dashboard instruction docs written by `fd-daas-dashboard-creator`
  (`<custom-name>-dashboard.md`).

## Convention

Skills create `daas-doc/` and the relevant subdirectory on first use. Doc paths
are determined by the producing skill's role (see the `daas-doc` spec).
`fd-daas-workflow-creator` nesting paths are removed (that skill was deleted) -
creator skills always write to their standalone default path.
