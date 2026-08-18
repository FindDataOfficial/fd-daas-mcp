---
name: fd-coding-daas-reset-project
description: Reset the DAAS project to a clean state. Use this skill whenever the user wants to wipe test artifacts, drop fetched/scraped data, or restore the project to a clean baseline before a fresh run - phrases like "reset the daas project to clean", "把项目重置干净", "drop all the test data", "clear scraw tables", "start fresh", "clean up daas.db". This skill runs scripts/reset_project.py at three guarded levels (test-artifacts / data-only / full-baseline), backs up daas.db first, defaults to a dry-run preview, and requires explicit confirmation before mutating. It is non-destructive by default. Do NOT use this for a single indicator/dashboard/collection deletion (use the relevant creator skill) - this skill resets the whole project.
---

# fd-coding-daas-reset-project

Reset `daas.db` to a clean state at one of three levels. **Always** dry-run
preview first, **always** back up before mutating, **always** require explicit
confirmation. The skill drives `scripts/reset_project.py`.

## Levels

- **`test-artifacts`** (safe) - drop `scraw_zz_test_*` tables, `*_test` /
  `zz_test*` entity + indicator collections (cascades to items/changes), and
  `zz-test-*` dashboards (row + HTML file). Real data untouched. Use after a
  test pass to clean throwaway artifacts.
- **`data-only`** - drop every `scraw_*` table + `observations` + `data_snapshots`.
  Keeps the catalog and all user artifacts (collections, researches, dashboards,
  rules, pipelines, schedules). Use to re-fetch from scratch without rebuilding
  the registry.
- **`full-baseline`** (destructive) - data-only PLUS user artifacts:
  `entity_collections`(+items+changes), `indicator_collections`(+items+changes),
  `researches`, `dashboards`, `rules`, `process_results`, `pipeline_collections`
  (+items), `schedules`, `tasks`, `executions`, `alert_rules`, `alert_events`,
  `pdf_*`, `workflow_runs`, `workflow_step_results`. **Keeps the reference
  catalog** (sources/daas_functions/daas_function_columns/entities/
  entity_datasource_links/categories/datasource_forms/datasource_sections/
  indicator_rules + leader/composite registry). This keep-set is the design's
  Q1 default - **show the user the dry-run preview and confirm before `--yes`**.

## Workflow

1. **Ask which level.** If the user just says "reset", default to
   `test-artifacts` (the only non-destructive-to-real-data level) and confirm.
2. **Dry-run preview** - run without `--yes` so the user sees exactly what would
   be removed:

   ```bash
   uv run python .claude/skills/fd-coding-daas-reset-project/scripts/reset_project.py --level <level>
   ```

3. **Confirm** - show the preview table list to the user. Do not proceed to
   `--yes` without an explicit "yes".
4. **Apply** - run with `--yes`. The script backs up `daas.db` to
   `daas.db.bak-<timestamp>` first and refuses to mutate if the backup fails.
5. **Surface the run-notification** the script prints (level, backup path,
   dropped-table count) and remind the user how to restore from the backup.

## Safety guarantees (in the script)

- **Dry-run by default.** No `--yes` -> preview only, exit 0, nothing mutated.
- **`--yes` required to mutate.**
- **Backup first.** `shutil.copy2` to `daas.db.bak-<timestamp>` before any drop;
  on backup failure the script aborts.
- **FK-safe drops.** `PRAGMA foreign_keys=OFF` for the drop pass, then re-enabled.
- **Per-table resilience.** A drop that errors is reported, not fatal; the rest
  still applies.

## Boundaries

- **Whole-project reset only.** For deleting one indicator/dashboard/collection,
  use the relevant `fd-daas-*` creator skill, not this one.
- **`full-baseline` is destructive and its keep-set is a judgment call** (design
   Q1). Always preview + confirm. If the user wants a different keep-set (e.g.
   also drop the leader/composite registry, or keep collections), tell them the
   script keeps the reference catalog by default and they should edit the level
   or drop those tables manually.
- **Never run without a backup.** If the backup step fails, stop and report.
- **Restore:** `cp daas.db.bak-<ts> daas.db` rolls back everything from this run.
