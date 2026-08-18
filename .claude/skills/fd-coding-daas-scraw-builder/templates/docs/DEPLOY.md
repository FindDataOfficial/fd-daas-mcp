# Deploy & Schedule - scraw-__SRC_DASH__

## Prerequisites

The shared `scraw-ops` service must be running (scrapyd :6800, scrapyd-web :5000, redis :6379):

```bash
cd ../scraw-ops && docker compose up -d --build
```

## Build & deploy the egg

```bash
export SCRAPYD_URL=http://localhost:6800
./deploy.sh
```

`deploy.sh` builds an egg with `scrapyd-deploy --build-egg` then deploys to the `[deploy:production]` target in `scrapy.cfg`. The project appears in scrapyd-web's project list.

## Schedule a run

```bash
python schedule.py <spider>
python schedule.py <spider> -s DOWNLOAD_DELAY=0.5
```

`schedule.py` checks `listjobs.json` and skips scheduling if a run of `<spider>` is already pending/running, then calls `/schedule.json` and prints the scrapyd job id.

## Manage from scrapyd-web

Open http://localhost:5000 to schedule, stop, and view logs for this project alongside every other scraw-* project.

## Clean up a stuck queue

```bash
redis-cli --scan --pattern 'scraw___SRC_UNDERSCORE__:*' | xargs -r redis-cli del
```
