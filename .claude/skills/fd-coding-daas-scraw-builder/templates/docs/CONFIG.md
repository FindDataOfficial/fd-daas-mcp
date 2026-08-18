# Configuration - scraw-__SRC_DASH__

## Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `REDIS_URL` | `redis://localhost:6379/0` | shared redis for scrapy-redis scheduler/dupefilter |
| `SCRAPYD_URL` | `http://localhost:6800` | scrapyd service for deploy/schedule |
| `SQLITE_PATH` | `data/scraw.db` | SQLite output path |
| `JSONL_PATH` | `output/items.jl` | JSON Lines output path |
| `SCOPE_CONFIG` | `config/scope.yaml` | curated scope file |

Copy `.env.example` to `.env` and adjust.

## scrapy-redis settings

| Setting | Value | Notes |
|---------|-------|-------|
| `SCHEDULER` | `scrapy_redis.scheduler.Scheduler` | redis-backed queue |
| `DUPEFILTER_CLASS` | `scrapy_redis.dupefilter.RFPDupeFilter` | redis dedup |
| `SCHEDULER_PERSIST` | `True` | queue survives restart (pause/resume) |
| `REDIS_KEY` | `scraw___SRC_UNDERSCORE__:start_urls` | per-project namespace |

## Throttling

Defaults: `CONCURRENT_REQUESTS=8`, `DOWNLOAD_DELAY=0.25`, `DOWNLOAD_TIMEOUT=60`, `RETRY_TIMES=3`. Override per run via `-s KEY=VAL` on `schedule.py`.

## Scope overrides

Edit `config/scope.yaml` or pass `SCOPE_CONFIG=/path/to/override.yaml` to change the crawl target set per run (see `major-scope-config` spec).
