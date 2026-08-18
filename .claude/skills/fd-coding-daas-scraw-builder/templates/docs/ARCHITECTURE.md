# Architecture - scraw-__SRC_DASH__

## Package map

```
scraw-__SRC_DASH__/
├── pyproject.toml          # dist name scraw-__SRC_DASH__, console script scraw-__SRC_DASH__
├── scrapy.cfg              # [deploy:production] -> shared scrapyd :6800
├── deploy.sh               # build egg + scrapyd-deploy production
├── schedule.py             # scrapyd /schedule.json client w/ dedup guard
├── .env.example
├── config/scope.yaml       # curated crawl scope
├── docs/                   # ARCHITECTURE, DEPLOY, CONFIG
├── migrations/             # numbered SQL/schema migrations
├── scraw___SRC_UNDERSCORE__/        # importable package
│   ├── settings.py         # scrapy-redis scheduler + dupefilter baseline
│   ├── items.py            # source item(s) + provenance fields
│   ├── pipelines.py        # SqlitePipeline + JsonLinesPipeline
│   ├── middlewares.py
│   ├── db.py
│   ├── config.py           # load config/scope.yaml + overrides
│   ├── cli.py              # scraw-__SRC_DASH__ console script
│   └── spiders/
└── tests/test_smoke.py
```

## Data flow

1. A spider enumerates crawl targets (from `config/scope.yaml`, a DB, or a redis queue).
2. scrapy-redis serializes the pending request queue and the dupefilter into the shared redis (`scraw___SRC_UNDERSCORE__:*` keys).
3. `SqlitePipeline` writes records to `data/scraw.db`; `JsonLinesPipeline` appends to `output/items.jl`.
4. `schedule.py` submits jobs to scrapyd; scrapyd-web shows status/logs.

## Data source

- URL/API: __SOURCE_URL__
- Description: __SOURCE_DESC__
- Item shape: see `items.py`

## Role of the stack

- **scrapy-redis**: distributed-ready scheduler + dupefilter; pause/resume across restarts; per-project redis namespace.
- **scrapyd**: runs deployed eggs as managed jobs.
- **scrapyd-web**: one UI (port 5000) managing this and every other scraw-* project.
