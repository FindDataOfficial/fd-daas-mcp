"""Scrape the Ministry of Agriculture (农业农村部) open-info portal.

Extracts every document listed on https://www.moa.gov.cn/gk/, grouped by the
10 category blocks on the page (通知公告 / 政策法规 / ... / 政府网站年度报告).
For each document: category, full title, publish date (full YYYY-MM-DD derived
from the URL's t<date> token, falling back to the MM-DD shown), and absolute URL.

Run:  uv run --directory mcp/scrapling-uv-mcp python scripts/moa_gk.py
"""
import json
import re
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

BASE = "https://www.moa.gov.cn/gk/"
# ponytail: relative URLs (../govpublic/...) resolved against the /gk/ page root
ROOT = "https://www.moa.gov.cn/"


def main():
    page = Fetcher().get(BASE)
    html = page.html_content

    blocks = []  # (category, block_html)
    for m in re.finditer(r'class="content_list"\s*>(.*?)(?:</div>\s*</div>|</ul>)', html, re.DOTALL):
        # heading <p> is in the ~700 chars before this block's start
        before = html[max(0, m.start() - 800):m.start()]
        heads = re.findall(r'<a[^>]*>([^<]{2,12})</a></p>', before)
        category = heads[-1].strip() if heads else "未分类"
        blocks.append((category, m.group(1)))

    records = []
    seen = set()
    for category, block in blocks:
        for li in re.finditer(
            r'<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?(<span[^>]*>(\d{2}-\d{2})</span>)?',
            block, re.DOTALL,
        ):
            href, title, _, mmdd = li.group(1), li.group(2), li.group(3), li.group(4)
            # derive full date from URL token t20251011 -> 2025-10-11
            d = re.search(r't(\d{4})(\d{2})(\d{2})_', href)
            if d:
                y, mo, day = d.groups()
                # sanity: month/day valid; else keep MM-DD
                if 1 <= int(mo) <= 12 and 1 <= int(day) <= 31:
                    date = f"{y}-{mo}-{day}"
                else:
                    date = mmdd or ""
            else:
                date = mmdd or ""

            # keep real document links (.htm/.html/.pdf), drop nav/pagination
            low = href.lower()
            if not (low.endswith(".htm") or low.endswith(".html") or low.endswith(".pdf")):
                continue
            url = urljoin(ROOT, href)
            key = (url, title)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "category": category,
                "title": title.strip(),
                "date": date,
                "url": url,
            })

    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
