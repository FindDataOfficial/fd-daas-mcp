## Context

`mcp/cnreport-mcp/` exposes an edgartools-style company API backed by CNINFO (`cninfo.com.cn`). Today the disclosure taxonomy is a hardcoded 4-entry Python dict (`cninfo_client._FORM_CATEGORIES`: 年度 / 半年度 / 第一季度 / 第三季度报告). CNINFO's `hisAnnouncement` endpoint accepts a `category` parameter covering dozens of disclosure types (prospectus, refinancing, earnings forecast, M&A, equity incentives, related-party transactions, …), but the MCP can neither discover nor address them. The taxonomy also lives in code, so each new report type needs a code change — exactly the scalability gap the user wants closed.

Existing building blocks the design reuses:
- `cninfo_client.query_announcements(stock_code, org_id, *, form, year, limit)` — already builds the `hisAnnouncement` POST payload, already over-fetches then post-filters.
- `cnreport_tools.fetch_source → parse_outline → resolve_selector → extract_section_text` — the section-extraction pipeline used by `extract_section` and `get_section`.
- The `_tool_safe` decorator + `{"error": ...}` return convention — every new wrapper follows it.

## Goals / Non-Goals

**Goals:**
- Make the CNINFO disclosure taxonomy **discoverable** (`list_report_types`) and **addressable** (`list_filings(category=…)`, `get_special_report`).
- Make adding a report type a **data edit** (JSON), not a code change — the explicit "scalable development" ask.
- Preserve full backward compatibility: `form` param, all five existing tools, all existing tests.
- Reuse the existing outline pipeline for special-report section extraction — no PDF logic duplicated.

**Non-Goals:**
- Live-fetching CNINFO's category tree at runtime (no stable documented endpoint; the taxonomy is static enough to ship as data).
- Persisting the catalog in `daas.db` (overkill for a static registry; the JSON file is the source of truth).
- Covering every CNINFO category code on day one — ship a curated, useful subset; the registry is extensible.
- Changing `get_section`'s contract (it stays annual-report-scoped with `form="年度报告"` default).

## Decisions

### Decision 1: Category taxonomy as a JSON registry file
Ship `mcp/cnreport-mcp/cninfo_categories.json` — a grouped list of `{name, code, description}` entries. `cninfo_client.load_categories()` reads it once at import and caches it; `_FORM_CATEGORIES` is derived from (and replaced by) this registry.

**Why JSON over code:** the user's "scalable development" requirement is the deciding factor — non-engineers can add a report type by appending an entry, and the change is reviewable as data. **Why a file over `daas.db`:** the taxonomy is static reference data, not transactional state; a JSON file avoids DB coupling and a migration. **Why a file over live-fetching CNINFO:** CNINFO exposes no stable, documented category-list endpoint, and a startup network dependency would make the MCP fragile.

Shape:
```json
{
  "groups": [
    {"name": "定期报告", "categories": [
      {"name": "年度报告", "code": "category_ndbg_szsh", "description": "Annual report"},
      {"name": "半年度报告", "code": "category_bndbg_szsh", "description": "Semi-annual report"},
      {"name": "第一季度报告", "code": "category_yjdbg_szsh", "description": "Q1 report"},
      {"name": "第三季度报告", "code": "category_sjdbg_szsh", "description": "Q3 report"}
    ]},
    {"name": "融资", "categories": [
      {"name": "招股说明书", "code": "category_zgsm_szsh", "description": "IPO prospectus"},
      {"name": "增发", "code": "category_zf_szsh", "description": "Additional issuance"},
      {"name": "配股", "code": "category_pf_szsh", "description": "Rights issue"},
      {"name": "可转债", "code": "category_kzz_szsh", "description": "Convertible bond"}
    ]}
    // … 业绩, 股权变动, 公司治理, 担保, 其他
  ]
}
```

### Decision 2: Dual category acceptance (code or Chinese name)
`list_filings(category=…)` and `get_special_report(category=…)` accept EITHER a raw CNINFO code (`category_ndbg_szsh`) OR a Chinese name from the registry (`年度报告`). A `resolve_category(category)` helper normalizes: name → code via registry; code already a code → as-is; unknown → `None` (caller returns `{"error": …}`).

**Why:** agent-friendliness. `list_report_types` returns names + codes; whatever the agent passes back resolves. **Alternative rejected:** accepting only codes — forces agents to carry a lookup table; only names — loses the escape hatch for codes not yet in the registry.

### Decision 3: `form` and `category` coexist, mutually exclusive
`form` stays as the backward-compatible alias for the four periodic reports (and its free-text title-substring behavior). `category` is the new general parameter for any registry code/name. Supplying both is an error returned as `{"error": "specify either form or category, not both"}`.

**Why not merge into one param:** `form`'s free-text behavior and `get_section`'s `form="年度报告"` default are existing contracts; merging would break them. Mutually-exclusive keeps both clean and unambiguous.

### Decision 4: `query_announcements` gains a `category` pass-through
`cninfo_client.query_announcements(stock_code, org_id, *, form=None, category=None, year=None, limit=20)`:
- If `category` resolved to a code → set `data["category"] = code`, skip the post-hoc `form` filter.
- If `form` given (no `category`) → existing behavior (registry lookup for the four names, else free-text post-hoc title filter).
- If neither → list all disclosures (current behavior).

The tool layer (`cnreport_tools.list_filings`) enforces mutual exclusion and resolves `category` before calling down.

### Decision 5: `get_special_report` as a parallel tool, not a `get_section` generalization
Signature: `get_special_report(ticker_or_name, category, year=None, section=None, limit=5)`.

Flow: resolve company → `query_announcements(category=…, year=…, limit=…)` → pick first filing → if `section` given, run `fetch_source(pdf) → parse_outline → resolve_selector → extract_section_text` and return `{stock_code, company_name, category, year, section, pdf_url, outline_entry, text, char_count}`; else return `{stock_code, company_name, category, filings: [...], pdf_url}` (metadata + URL, like a category-scoped `list_filings` returning the top hit).

**Why a new tool over generalizing `get_section`:** `get_section` requires `year` and defaults `form="年度报告"` — its contract is annual-report-scoped. Special reports (e.g. 招股说明书) may have one filing ever and no meaningful "fiscal year". A dedicated tool gives agents a clear, separately-discoverable entry point and leaves `get_section` untouched. **Section extraction reuses the identical pipeline** — no PDF logic is duplicated.

### Decision 6: `list_report_types(group=None)` shape
Returns `{"groups": [{name, categories: [{name, code, description}]}], "count": N}`. With `group` set, returns only that group's categories. Unknown `group` → `{"error": …}`.

## Risks / Trade-offs

- **[CNINFO category codes are undocumented and may change]** → Mitigation: codes live in a JSON file, updatable without a code release. The four periodic codes are long-stable. Unknown codes passed verbatim still hit CNINFO (graceful degradation); resolution only affects the registry-backed path.
- **[Curated subset is incomplete]** → Mitigation: `list_filings` with no `category` still lists all disclosures, so agents aren't blocked by a missing entry; `list_report_types` is honest about what's cataloged. The registry is explicitly extensible — a non-goal to be exhaustive on day one.
- **[Backward-compat risk in the `form` path]** → Mitigation: `form` semantics (four-name registry lookup + free-text title filter) are preserved verbatim; existing `test_list_filings_*` tests must pass unchanged. The registry is seeded so the four names resolve to the same codes `_FORM_CATEGORIES` held.
- **[Special categories can return many filings]** → Mitigation: `limit` parameter + the existing over-fetch/post-filter pattern; `get_special_report` picks the first (most recent) by default.
- **[`form` + `category` both passed]** → Mitigation: explicit error at the tool layer before any network call.

## Migration Plan

- **No database migration** — the catalog is a static JSON file; `daas.db` is untouched.
- **Backward compatible by construction** — `form` param preserved, existing tools unchanged, existing tests must pass.
- **Rollout order:** (1) add `cninfo_categories.json`; (2) add `load_categories` + `resolve_category` in `cninfo_client`, derive the four-form lookup from the registry; (3) add `category` to `query_announcements`; (4) add `list_report_types` + `get_special_report` wrappers in `cnreport_tools`; (5) register the two new `@app.tool`s; (6) tests + selfcheck + docs.
- **Rollback:** revert the commit — the JSON file is additive and the code changes are isolated to `cnreport-mcp/`. No external state to unwind.

## Open Questions

- Exact CNINFO category codes for the curated special types (招股说明书, 收购报告书, 权益变动报告书, …) — to be confirmed during implementation by inspecting CNINFO's frontend request payloads (the SPA sends the `category` field verbatim). If a code can't be confirmed, that entry is omitted from the initial registry rather than guessed; the registry is extensible.
- Whether to surface a `group` filter on `list_filings` (list all categories within a group) — deferred; agents can call `list_report_types(group=…)` then `list_filings(category=…)` per category.
