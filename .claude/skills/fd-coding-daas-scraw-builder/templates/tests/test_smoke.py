from __future__ import annotations

import subprocess
import sys


def test_import_package():
    import scraw___SRC_UNDERSCORE__  # noqa: F401


def test_settings_load():
    import os

    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    from scraw___SRC_UNDERSCORE__ import settings  # noqa: F401

    assert settings.BOT_NAME == "scraw___SRC_UNDERSCORE__"
    assert settings.SCHEDULER == "scrapy_redis.scheduler.Scheduler"
    assert settings.DUPEFILTER_CLASS == "scrapy_redis.dupefilter.RFPDupeFilter"
    assert settings.REDIS_KEY == "scraw___SRC_UNDERSCORE__:start_urls"


def test_scrapy_list():
    rc = subprocess.call([sys.executable, "-m", "scrapy", "list"])
    assert rc == 0
