from __future__ import annotations

import argparse
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scraw-__SRC_DASH__")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list available spiders")

    p_crawl = sub.add_parser("crawl", help="run a spider locally")
    p_crawl.add_argument("spider")
    p_crawl.add_argument("args", nargs="*")

    p_sched = sub.add_parser("schedule", help="schedule a spider on scrapyd")
    p_sched.add_argument("spider")

    args = parser.parse_args(argv)

    if args.cmd == "list":
        return subprocess.call(["scrapy", "list"])
    if args.cmd == "crawl":
        return subprocess.call(["scrapy", "crawl", args.spider, *args.args])
    if args.cmd == "schedule":
        return subprocess.call([sys.executable, "schedule.py", args.spider])
    return 0


if __name__ == "__main__":
    sys.exit(main())
