# Scraper template

The script the skill emits for `<SCRAPLING_SCRIPTS_DIR>/<slug>.py`. It is
self-contained (imports `scrapling`), prints extracted records as JSON to stdout
(so both `run_script` and cron capture it uniformly), and accepts an optional
`--out <path>` to also write the JSON to a file for scheduled runs.

Adapt the SELECTORS and the row-building logic to the actual page; keep the
structure (docstring first line, `main()`, JSON-to-stdout, `--out`) unchanged so
`find_scripts` shows a useful summary and `run_script`/cron behave predictably.

```python
#!/usr/bin/env python3
"""<slug> scraper — <one-line description of what it extracts>.

Prints records as JSON to stdout. Optional: --out <path> also writes the JSON
to a file (useful for scheduled runs that need a durable artifact).
"""

import argparse
import json
import sys

from scrapling.fetchers import Fetcher

URL = "<URL>"


def fetch_records():
    page = Fetcher().get(URL)
    records = []
    for node in page.css("<REPEAT_SELECTOR>"):
        records.append({
            # <column_name>: <extraction expression>
            "title": node.css_first("<TITLE_SELECTOR>") or "",
            "date": node.css_first("<DATE_SELECTOR>") or "",
            "url": node.css_first("<LINK_SELECTOR>") or "",
        })
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="also write JSON to this path")
    args = parser.parse_args(argv)

    records = fetch_records()
    out = json.dumps(records, ensure_ascii=False, indent=2)
    print(out)
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Notes:
- Use `Fetcher().get(url)` for plain pages; for anti-bot pages use
  `StealthyFetcher().fetch(url)` instead (matching the `stealthy_fetch` tool).
- Keep the module docstring — its first line is what `find_scripts` returns as
  the script `summary`.
- Selector API: scrapling nodes support `.css()`, `.css_first()`, `.xpath()`,
  `.text`, `.attrib`. Match the columns agreed with the user in Step 1.
