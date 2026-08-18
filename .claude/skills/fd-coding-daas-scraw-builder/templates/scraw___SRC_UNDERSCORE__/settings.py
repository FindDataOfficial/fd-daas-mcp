from __future__ import annotations

import os

BOT_NAME = "scraw___SRC_UNDERSCORE__"

SPIDER_MODULES = ["scraw___SRC_UNDERSCORE__.spiders"]
NEWSPIDER_MODULE = "scraw___SRC_UNDERSCORE__.spiders"

ROBOTSTXT_OBEY = False
FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"

# --- Throttling (tune per source; see docs/CONFIG.md) ---
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.25
DOWNLOAD_TIMEOUT = 60
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

# --- scrapy-redis: distributed-ready scheduler + dupefilter ---
# Backed by the shared scraw-ops redis. SCHEDULER_PERSIST=True gives pause/resume
# across restarts; the per-project REDIS_KEY namespace isolates this project's
# queue from other scraw-* projects sharing the same redis.
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_KEY = "scraw___SRC_UNDERSCORE__:start_urls"

ITEM_PIPELINES = {
    "scraw___SRC_UNDERSCORE__.pipelines.SqlitePipeline": 300,
    "scraw___SRC_UNDERSCORE__.pipelines.JsonLinesPipeline": 400,
}
