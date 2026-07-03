# Auto-decide the category level

daas-mcp has **no `level` field** — a datasource's "level" is its depth in the
category tree, derived from `parent_id`. The existing seed places datasources at
depth 2 (a leaf under a root). So "decide the level automatically" = decide
which category node (→ depth) to attach the new datasource to, with no user
prompt.

## The rule

1. `get_category_tree()` → walk the nested tree (each node has `id`, `name`,
   `parent_id`, `children`, `datasource_count`).
2. Find-or-create a root category named **`Web Scraped`**:
   - If a node with `name == "Web Scraped"` and `parent_id == None` exists, use
     its `id`.
   - Else `create_category(name="Web Scraped")` → use the returned `id`.
3. Find-or-create a **child of `Web Scraped`** named after the URL's registered
   domain (e.g. `example.com`):
   - Among `Web Scraped`'s `children`, if one has `name == <domain>`, use its `id`.
   - Else `create_category(name=<domain>, parent_id=<Web Scraped id>)` → use its
     `id`.
4. Pass that domain leaf's `id` as `category_id` to `create_datasource` /
   `update_datasource`. The datasource lands at depth 2.

## Domain extraction

```python
from urllib.parse import urlparse
host = urlparse(url).hostname or ""          # "www.example.com" or "example.com"
domain = host.removeprefix("www.").lower()   # "example.com"
```

Strip a leading `www.`; lowercase. Use the full registrable host as the category
name — it is a stable, derivable key needing no inference.

`ponytail:` this uses the bare hostname, not eTLD-aware registrable-domain
parsing (no `tldextract`). For `sub.example.co.uk` this yields
`sub.example.co.uk` as the leaf name, which is fine for grouping; if finer
domain normalization matters later, swap in `tldextract` at this one spot.

## Why domain, not topic

A domain key is deterministic and free (derived from the URL the user already
gave). Topic inference (e.g. "News", "Finance") would need an LLM call and is
speculative until someone wants to browse the catalog by topic — at which point
a topic subcategory can be added under the domain leaf without changing this
rule.

## Idempotency

Find-or-create matches an existing same-named category before calling
`create_category`, so re-running the skill for the same site reuses the
`Web Scraped` root and the `<domain>` leaf without creating duplicates.
`create_category` itself doesn't dedupe on name, so **always look first**.
