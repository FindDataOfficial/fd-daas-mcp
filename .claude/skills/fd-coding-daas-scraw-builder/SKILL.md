---
name: fd-coding-daas-scraw-builder
description: Scaffold a new scraw-* Scrapy project conforming to the finddata DaaS standard stack (scrapy + scrapy-redis + scrapyd + scrapyd-web). Use when creating a new scraw-* crawler project, or when bootstrapping a data source crawler onto the shared scraw-ops service. Generates the canonical directory layout, redis-ready settings, deploy/schedule scripts, and the standard docs set with consistent tech stack and documentation structure.
---

# fd-daas-scraw-builder

Scaffolds a new `scraw-*` Scrapy project that conforms to the finddata DaaS standard stack: **scrapy + scrapy-redis + scrapyd + scrapyd-web**, deployed into the shared `scraw-ops` service. The generated project has a fixed directory layout, a fixed `settings.py` baseline, fixed deploy/schedule entry points, and a fixed documentation set - so every `scraw-*` project looks and behaves the same.

The single source of truth for what a conforming project looks like is [`references/standard-structure.md`](references/standard-structure.md). The `templates/` directory is the renderable skeleton.

## When to trigger

- "create a new scraw project" / "scaffold scraw-*" / "add a scraw crawler for <source>"
- "generate a scraw project for the <source> data source"
- Bootstrapping a new data source onto the shared scraw-ops scrapyd/scrapyd-web/redis service.

## What the skill produces

A directory `scraw-<src>/` containing the canonical layout (see `references/standard-structure.md`): `pyproject.toml`, `scrapy.cfg`, `README.md`, `deploy.sh`, `schedule.py`, `.env.example`, `config/scope.yaml`, `docs/{ARCHITECTURE,DEPLOY,CONFIG}.md`, `migrations/README.md`, the importable `scraw_<src>/` package (`settings.py`, `items.py`, `pipelines.py`, `middlewares.py`, `db.py`, `config.py`, `cli.py`, `spiders/`), and `tests/test_smoke.py`.

## Workflow

### 1. Capture inputs

Ask the user for (fill gaps from context, confirm before proceeding):

1. **Source slug** `<src>` - kebab-case, e.g. `world-bank-data`, `ckan-data`. Derives:
   - folder / dist name: `scraw-<src>` (dashes)
   - importable package: `scraw_<src>` (underscores: `-` -> `_`)
   - console script: `scraw-<src>`
   - redis namespace: `scraw_<src>:start_urls`
2. **Data source URL/API** - e.g. `https://api.worldbank.org/v2`.
3. **Source description** - one line, e.g. "World Bank open data indicators".
4. **Primary item shape** - the fields the source yields (used to flesh out `items.py` and `docs/ARCHITECTURE.md`). If unknown, keep the generic `RecordItem`.

### 2. Render the skeleton

Copy `templates/` into `scraw-<src>/`, performing these string substitutions in **every** file's contents and in the one template directory name:

| Placeholder | Replaced with | Example |
|-------------|---------------|---------|
| `__SRC_DASH__` | the slug (`<src>`) | `world-bank-data` |
| `__SRC_UNDERSCORE__` | slug with `-` -> `_` | `world_bank_data` |
| `__SOURCE_DESC__` | source description | `World Bank open data indicators` |
| `__SOURCE_URL__` | source URL/API | `https://api.worldbank.org/v2` |

The template package directory is literally named `scraw___SRC_UNDERSCORE__` (i.e. `scraw_` + `__SRC_UNDERSCORE__`); after substitution it becomes `scraw_<src>`. The project root `scraw-<src>/` is created fresh and is NOT part of `templates/`.

### 3. Flesh out the source-specific bits

- **`items.py`**: if the user gave an item shape, replace the generic `RecordItem` fields with the source's fields (keep a `crawl_time` + `source` provenance field).
- **`spiders/`**: add an initial spider stub for the source (a `scrapy.Spider` that reads targets from `config/scope.yaml` via `config.py`). Name it after the source.
- **`docs/ARCHITECTURE.md`**: fill the Data source section with the URL/description/item shape.

### 4. Smoke test

From inside `scraw-<src>/`:

```bash
python -c "import scraw_<src>"            # package imports
python -m scrapy list                      # spiders discovered (>= the stub)
python -m pytest tests/test_smoke.py       # import + settings + scrapy list
```

`settings.py` reads `REDIS_URL` from env with a `redis://localhost:6379/0` default, so the smoke test runs without redis running. Report any failure and fix the template before declaring success.

### 5. Hand off

Tell the user:

- The shared service: `cd scraw-ops && docker compose up -d --build` (scrapyd :6800, scrapyd-web :5000, redis :6379).
- Deploy: `SCRAPYD_URL=http://localhost:6800 ./deploy.sh`.
- Schedule: `python schedule.py <spider>`.
- Manage: open http://localhost:5000 (scrapyd-web).

## Conformance checklist

A generated project MUST (see `references/standard-structure.md` and the `scraw-project-template` spec):

- [ ] folder/dist `scraw-<src>` (dashes), importable package `scraw_<src>` (underscores), console script `scraw-<src>`.
- [ ] `settings.py` has `scrapy_redis.scheduler.Scheduler` + `scrapy_redis.dupefilter.RFPDupeFilter`, `SCHEDULER_PERSIST=True`, `REDIS_URL` from env, `REDIS_KEY=scraw_<src>:start_urls`.
- [ ] `ITEM_PIPELINES` wires `SqlitePipeline` (300) + `JsonLinesPipeline` (400).
- [ ] `deploy.sh` (build egg + `scrapyd-deploy production`) and `schedule.py` (dedup guard + `/schedule.json` + records job id) exist.
- [ ] `scrapy.cfg` has `[deploy:production]` -> shared scrapyd `:6800`.
- [ ] `README.md` has the fixed sections; `docs/ARCHITECTURE.md`, `docs/DEPLOY.md`, `docs/CONFIG.md` exist with the fixed outlines.
- [ ] `tests/test_smoke.py` passes.

## Notes

- Do NOT bundle infra into a generated project - infra lives in `scraw-ops/`.
- The existing `scraw` skill (`~/.claude/skills/scraw/`) is a separate general-purpose scraping tool-selector; this skill only generates `scraw-*` projects.
- To migrate an EXISTING crawler onto this template, generate a fresh project then port the source's spiders/parsers/config into it rather than copying the whole old tree.
