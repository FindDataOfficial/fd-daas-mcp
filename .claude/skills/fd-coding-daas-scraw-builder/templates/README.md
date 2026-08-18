# scraw-__SRC_DASH__

Scrapy crawler for __SOURCE_DESC__ (__SOURCE_URL__).

Built on the finddata DaaS standard stack: **scrapy** + **scrapy-redis** + **scrapyd** + **scrapyd-web**, deployed into the shared `scraw-ops` service.

## Overview

Crawls __SOURCE_DESC__ from __SOURCE_URL__ and persists records to SQLite + JSON Lines, scheduled and managed via the shared scrapyd / scrapyd-web service.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the package map, data flow, and how redis/scrapyd/scrapyd-web fit together.

## Quickstart (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
export REDIS_URL=redis://localhost:6379/0
scrapy list
scrapy crawl <spider>
```

## Configuration

See [docs/CONFIG.md](docs/CONFIG.md) for settings knobs, scope overrides, and env vars.

## Deploy & Schedule

See [docs/DEPLOY.md](docs/DEPLOY.md) for egg build, scrapyd-deploy, scrapyd-web, and `schedule.py`.

## Tests

```bash
pip install pytest
pytest
```

## Project layout

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
