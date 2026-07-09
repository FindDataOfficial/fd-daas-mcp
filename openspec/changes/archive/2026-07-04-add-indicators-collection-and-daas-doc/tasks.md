## 1. New skill: fd-daas-indicators-collection-creator

- [x]1.1 Create `.claude/skills/fd-daas-indicators-collection-creator/SKILL.md` with YAML frontmatter (`name`, `description`) that triggers on indicator-collection-creation intent in EN+ZH ("把这几个指标存成一个 collection" / "create an indicators collection for these"). Per spec req: Skill exists and triggers.
- [x]1.2 Add Step 1 — Propose: collect a name + member indicator list, show the proposed collection to the user, and gate on confirmation (no daas-mcp writes before consent).
- [x]1.3 Add Step 2 — Create: call `mcp__daas-mcp__create_indicator_collection(name, description?)` then `mcp__daas-mcp__add_indicator_to_collection(collection_name, indicator_name, score?, reason?)` per member; surface daas-mcp errors for unknown indicators and skip without creating.
- [x]1.4 Add Step 3 — Surface scores: call `mcp__daas-mcp__list_indicator_collection_items(collection_name)`, render each member's resolved `score`, `item_score`, `indicator_default_score`, `source_default_score` verbatim (no recompute — the 3-level resolution already inherits the datasource default).
- [x]1.5 Add Step 4 — Write introduction md `indicators-<collection>.md` (collection name + description, member table with op/params/source_table/value_column + the four score fields, created date, refresh note). Standalone → `daas-doc/indicators/<collection>.md`; nested → `daas-doc/<X>/indicators-<collection>.md` when `args` contains a `workflow-name <X>` token.
- [x]1.6 (Optional) Add `references/introduction-template.md` showing the introduction md shape for the model to adapt.

## 2. daas-doc convention

- [x]2.1 Add a short `construction/daas-doc.md` (or a CLAUDE.md section) documenting the `daas-doc/` layout, standalone vs nested paths, and the `workflow-name <X>` nesting-token convention shared by the three creator skills.
- [x]2.2 Decide `daas-doc/` git tracking: commit as documentation (do NOT add to `.gitignore`). Note the decision in the construction doc.

## 3. Modify fd-daas-workflow-creator

- [x]3.1 Add a step to derive a kebab-case `<workflow-name>` from the summarized goal (slugify, truncate ~40 chars); fall back to `workflow-<YYYYMMDD>-<HHMMSS>` when the goal is empty or `daas-doc/<workflow-name>/` already exists. Create `daas-doc/<workflow-name>/`.
- [x]3.2 Add a step to write `daas-doc/<workflow-name>/plan.md` after persisting the workflow in leader-mcp (LLM path or manual fallback): capture workflow-name, composed goal, persisted leader-mcp workflow name + step list (upstream MCP, tool, arguments per step), chosen tier, created date. Report the path.
- [x]3.3 Add a step: when delegating to a child creator skill (`fd-daas-dashboard-creator` / `fd-daas-indicators-collection-creator`) via the `Skill` tool during a workflow run, include a `workflow-name <X>` token in the child's `args` string.
- [x]3.4 Update `fd-daas-workflow-creator/SKILL.md` frontmatter `description` to mention it writes a `plan.md` under `daas-doc/`.
- [x]3.5 Update the `fd-daas-workflow-creator` section of `CLAUDE.md` if it enumerates the skill's outputs.

## 4. Modify fd-daas-dashboard-creator

- [x]4.1 Add Step 6 — Write instruction md: after building the standalone HTML and registering in `index.html` + `daas.md`, write a companion `<custom-name>-dashboard.md` containing the dashboard slug, source `scraw_*` / `observations` tables + columns, refresh cadence (static vs cron, naming the cron if wired), the `file://` URL, and a one-line refresh note.
- [x]4.2 Path resolution: standalone → `daas-doc/dashboard/<custom-name>-dashboard.md`; when `args` contains a `workflow-name <X>` token → `daas-doc/<X>/<custom-name>-dashboard.md`. Create the dir on first use.
- [x]4.3 Update `fd-daas-dashboard-creator/SKILL.md` Gotchas/notes to mention the instruction md + the `workflow-name` nesting token (alongside the existing charts-render-offline + dashboard-mcp-DB gotchas).
- [x]4.4 Update the `fd-daas-dashboard-creator` section of `CLAUDE.md` if it enumerates the skill's outputs.

## 5. Verification

- [x]5.1 Dry-run `fd-daas-indicators-collection-creator` against a couple of existing indicators: confirm the collection is created, members added, and `daas-doc/indicators/<collection>.md` is written with resolved scores inheriting the datasource default.
- [x]5.2 Dry-run `fd-daas-workflow-creator` on a small flow: confirm `daas-doc/<workflow-name>/plan.md` is written with goal + step list + tier.
- [x]5.3 Dry-run `fd-daas-dashboard-creator`: confirm `daas-doc/dashboard/<slug>-dashboard.md` is written alongside the HTML.
- [x]5.4 Nesting dry-run: invoke `fd-daas-dashboard-creator` inside a `fd-daas-workflow-creator` run: confirm the instruction md lands under `daas-doc/<workflow-name>/` (not `daas-doc/dashboard/`).
- [x]5.5 Run `openspec validate add-indicators-collection-and-daas-doc --strict` (or `openspec status --change add-indicators-collection-and-daas-doc`) and confirm all artifacts are done / apply-ready.
