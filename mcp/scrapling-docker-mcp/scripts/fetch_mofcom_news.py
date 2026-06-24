#!/usr/bin/env python3
"""Fetch MOFCOM news list from https://www.mofcom.gov.cn/xwfb/index.html.

Uses scrapling for HTTP fetching + HTML parsing.

Usage:
  python3 fetch_mofcom_news.py          # print table
  python3 fetch_mofcom_news.py --json   # JSON output
"""

import json
import sys
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

BASE = "https://www.mofcom.gov.cn/xwfb/index.html"


def fetch():
    page = Fetcher().get(BASE)

    news = {}
    container = page.css('[ergodic="view"]')[0]

    for h4 in container.css('h4.sTitle_02'):
        name = h4.css('a')[0].get_all_text(strip=True) if h4.css('a') else h4.get_all_text(strip=True).split("\n")[0].strip()

        # h4 may be wrapped in an <a> — walk up to find the ul that follows
        anchor = h4.parent if h4.parent.tag == 'a' else h4
        ul = anchor.next
        if ul is None or ul.tag != 'ul':
            continue

        items = []
        for li in ul.css('li'):
            a = li.css('a')[0]
            title = a.attrib.get('title') or a.get_all_text(strip=True)
            href = urljoin(BASE, a.attrib.get('href', ''))
            span = li.css('span')
            date = span[0].get_all_text(strip=True) if span else ""
            items.append({"title": title, "url": href, "date": date})
        news[name] = items

    return news


def print_table(news):
    for cat, items in news.items():
        print(f"\n{'=' * 60}")
        print(f"  {cat}")
        print(f"{'=' * 60}")
        for i, item in enumerate(items, 1):
            print(f"  {i:2d}. [{item['date']}] {item['title']}")
            print(f"      {item['url']}")


def main():
    news = fetch()

    if "--json" in sys.argv:
        json.dump(news, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return

    print_table(news)
    print(f"\n共 {sum(len(v) for v in news.values())} 条新闻, {len(news)} 个分类")


if __name__ == "__main__":
    main()
