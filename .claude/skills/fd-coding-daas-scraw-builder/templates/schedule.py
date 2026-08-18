#!/usr/bin/env python3
"""Schedule a scraw-__SRC_DASH__ spider on the shared scrapyd service.

Checks listjobs.json first and skips scheduling if a run of the spider is
already pending or running (duplicate-run guard), then calls /schedule.json
and prints the scrapyd job id.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SCRAPYD_URL = os.environ.get("SCRAPYD_URL", "http://localhost:6800")
PROJECT = "scraw___SRC_UNDERSCORE__"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode())


def _post(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _pending_or_running(spider: str) -> bool:
    try:
        jobs = _get(f"{SCRAPYD_URL}/listjobs.json?project={PROJECT}")
    except Exception as e:  # noqa: BLE001
        print(f"warn: could not query listjobs.json ({e}); proceeding", file=sys.stderr)
        return False
    for state in ("pending", "running"):
        for job in jobs.get(state, []):
            if job.get("spider") == spider:
                return True
    return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Schedule a scraw-__SRC_DASH__ spider on scrapyd")
    p.add_argument("spider")
    p.add_argument("-s", "--setting", action="append", default=[],
                   help="extra -s KEY=VAL spider settings")
    args = p.parse_args(argv)

    if _pending_or_running(args.spider):
        print(f"skip: a run of '{args.spider}' is already pending or running on scrapyd",
              file=sys.stderr)
        return 0

    data = {"project": PROJECT, "spider": args.spider}
    if args.setting:
        data["setting"] = args.setting
    try:
        resp = _post(f"{SCRAPYD_URL}/schedule.json", data)
    except Exception as e:  # noqa: BLE001
        print(f"error: schedule failed ({e})", file=sys.stderr)
        return 1

    jobid = resp.get("jobid")
    ts = datetime.now(timezone.utc).isoformat()
    print(f"scheduled: project={PROJECT} spider={args.spider} jobid={jobid} at={ts}")
    # Record the scrapyd job id on the crawl-run row here (project-specific).
    return 0


if __name__ == "__main__":
    sys.exit(main())
