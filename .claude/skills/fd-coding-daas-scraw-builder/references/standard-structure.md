# Standard scraw-* project structure

The authoritative structure every `scraw-*` project (new or migrated) conforms to. The `fd-daas-scraw-builder` skill renders `templates/` into this layout.

## Stack

`scrapy` + `scrapy-redis` + `scrapyd` + `scrapyd-web`, deployed into the shared `scraw-ops` service (one scrapyd :6800, one scrapyd-web :5000, one redis :6379). Projects ship only eggs + client config - never infra.

## Naming

| Thing | Form | Example |
|-------|------|---------|
| Folder / dist name | `scraw-<src>` (dashes) | `scraw-world-bank-data` |
| Importable package | `scraw_<src>` (underscores) | `scraw_world_bank_data` |
| Console script | `scraw-<src>` | `scraw-world-bank-data` |
| Redis namespace | `scraw_<src>:start_urls` | `scraw_world_bank_data:start_urls` |

## Layout

```
scraw-<src>/
├── pyproject.toml          # name="scraw-<src>", script scraw-<src>, deps: scrapy, scrapy-redis, scrapyd, scrapyd-client, redis, pyyaml
├── scrapy.cfg              # [settings] default + [deploy:production] -> http://localhost:6800, project = scraw_<src>
├── README.md               # fixed sections: Overview, Architecture, Quickstart, Configuration, Deploy & Schedule, Tests, Project layout
├── deploy.sh               # build egg + scrapyd-deploy production
├── schedule.py             # scrapyd /schedule.json client w/ duplicate-run guard; records job id
├── .env.example            # REDIS_URL, SCRAPYD_URL, SQLITE_PATH, JSONL_PATH, source keys
├── config/
│   └── scope.yaml          # curated crawl scope (indicators/countries/portals)
├── docs/
│   ├── ARCHITECTURE.md     # package map, data flow, data source, role of the stack
│   ├── DEPLOY.md           # prerequisites, build/deploy egg, schedule.py, scrapyd-web, queue cleanup
│   └── CONFIG.md           # env vars, scrapy-redis settings, throttling, scope overrides
├── migrations/
│   └── README.md           # numbered SQL/schema migration convention
├── scraw_<src>/
│   ├── __init__.py
│   ├── settings.py         # baseline + scrapy-redis scheduler/dupefilter/persist + REDIS_KEY + pipelines
│   ├── items.py            # source item(s) + provenance fields
│   ├── pipelines.py        # SqlitePipeline (300) + JsonLinesPipeline (400)
│   ├── middlewares.py
│   ├── db.py               # sqlite connection + WAL
│   ├── config.py           # load config/scope.yaml + env overrides
│   ├── cli.py              # scraw-<src> console script: list/crawl/schedule
│   └── spiders/
│       └── __init__.py
└── tests/
    └── test_smoke.py       # import package, load settings, scrapy list
```

## settings.py baseline

```python
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_KEY = "scraw_<src>:start_urls"

ITEM_PIPELINES = {
    "scraw_<src>.pipelines.SqlitePipeline": 300,
    "scraw_<src>.pipelines.JsonLinesPipeline": 400,
}
```

Throttling defaults: `CONCURRENT_REQUESTS=8`, `DOWNLOAD_DELAY=0.25`, `DOWNLOAD_TIMEOUT=60`, `RETRY_TIMES=3`.

## Docs outlines (fixed)

- **README.md**: Overview, Architecture (link), Quickstart (local), Configuration (link), Deploy & Schedule (link), Tests, Project layout (link).
- **docs/ARCHITECTURE.md**: Package map, Data flow, Data source (URL/desc/item shape), Role of the stack.
- **docs/DEPLOY.md**: Prerequisites (scraw-ops running), Build & deploy egg, Schedule a run, Manage from scrapyd-web, Clean up a stuck queue.
- **docs/CONFIG.md**: Environment variables table, scrapy-redis settings table, Throttling, Scope overrides.

## Conformance (from the scraw-project-template spec)

- Layout matches the above.
- Naming uses dashes for folder/dist, underscores for the package.
- `pyproject.toml` declares `[project.entry-points."scrapy"] settings = "scraw_<src>.settings"` (required for scrapyd egg activation).
- `settings.py` has the scrapy-redis scheduler + dupefilter + persist + per-project `REDIS_KEY` + standard pipelines.
- `deploy.sh` + `schedule.py` exist with the standard behavior.
- `scrapy.cfg` `[deploy:production]` points at the shared scrapyd.
- Fixed docs set exists.
- `tests/test_smoke.py` passes.
