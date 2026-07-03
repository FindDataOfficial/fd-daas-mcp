"""HKEXnews HTTP client — keyless, hand-rolled.

All network I/O is funneled through `_get_client()` so tests can mock with
`respx`. Public functions raise typed errors (`LookupError`, `httpx.HTTPError`);
the server translates them to structured `{error, hint}` dicts.

ponytail: parse-functions are pure (response-dict -> records), so unit tests
mock at the HTTP boundary, not at internal seams.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Optional

import httpx

# ── Endpoints ─────────────────────────────────────────────────────────

_BASE = "https://www1.hkexnews.hk"
_INSTRUMENT_SEARCH = f"{_BASE}/ncms/script/eds/instrument_search.json"
_TITLE_SEARCH = f"{_BASE}/search/titleSearchServlet.aspx"
_CALENDAR = "https://www.hkex.com.hk/eng/services/timesandqueries/Issuer/Calendar.aspx"

_USER_AGENT = "cli-anything/hkreport-mcp"
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_MAX_RETRIES = 3


# ── HTTP plumbing ─────────────────────────────────────────────────────


def _get_client() -> httpx.Client:
    """Build a fresh httpx.Client. Honors HTTP(S)_PROXY env."""
    return httpx.Client(
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json, text/html"},
        follow_redirects=True,
    )


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    """Make one HTTP request, retrying 5xx up to _MAX_RETRIES with backoff."""
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            with _get_client() as client:
                resp = client.request(method, url, **kwargs)
            if resp.status_code < 500:
                return resp
            last_exc = httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )
        except httpx.HTTPError as e:
            last_exc = e
        time.sleep(0.5 * (2**attempt))
    assert last_exc is not None
    raise last_exc


# ── Ticker normalization (task 2.1) ───────────────────────────────────


_TICKER_RE = re.compile(r"^\s*0*(\d{1,5})(?:\.HK)?\s*$", re.IGNORECASE)


def _normalize_ticker(value: str) -> Optional[str]:
    """Accept '00700', '700', '0700.HK', '700.HK' → '00700'. None if not a code."""
    if not isinstance(value, str):
        return None
    m = _TICKER_RE.match(value)
    if not m:
        return None
    digits = m.group(1)
    n = int(digits)
    if not (1 <= n <= 99999):
        return None
    return f"{n:05d}"


# ── Company lookup (task 2.2) ─────────────────────────────────────────


def lookup_company(query: str) -> dict[str, Any]:
    """Resolve a HK company by code or name. Raises LookupError on no match."""
    code = _normalize_ticker(query)
    params = {"type": "A", "stockId" if code else "name": code or query}
    resp = _request("GET", _INSTRUMENT_SEARCH, params=params)
    resp.raise_for_status()
    try:
        rows = resp.json()
    except ValueError as e:
        raise LookupError(f"instrument_search returned non-JSON: {e}") from None
    return _parse_instrument_search(rows, query, code)


def _parse_instrument_search(
    rows: Any, query: str, code: Optional[str]
) -> dict[str, Any]:
    """Pick the best match from an instrument_search response."""
    if not isinstance(rows, list) or not rows:
        raise LookupError(f"No match for query={query!r}")

    def normalize(row: dict) -> dict:
        # HKEXnews returns mixed casing across endpoints; tolerate both.
        raw_code = str(row.get("stockId") or row.get("sid") or row.get("code") or "")
        norm = _normalize_ticker(raw_code) or raw_code.zfill(5)
        return {
            "stock_code": norm,
            "name": row.get("name_en") or row.get("nameEn") or row.get("name") or "",
            "name_zh": row.get("name_zh") or row.get("nameZh") or row.get("name_cn") or "",
            "board": row.get("board") or row.get("market") or "Main",
            "sector": row.get("sector") or row.get("industry_group") or "",
            "industry": row.get("industry") or "",
        }

    if code:
        for row in rows:
            n = normalize(row)
            if n["stock_code"] == code:
                return n
        raise LookupError(f"No match for stock_code={code}")
    # Name search — take the first row.
    return normalize(rows[0])


# ── Disclosure list (task 2.3 + 2.4) ──────────────────────────────────


# HKEXnews t2gcode/t2code values, abbreviated for the doc types we expose.
_FORM_CODES = {
    "Annual Report": ("40000", "40100"),
    "Interim Report": ("40000", "40200"),
    "Quarterly Report": ("40000", "40300"),
    "Announcement": ("10000", "-2"),
    "Circular": ("20000", "-2"),
    "Listing Document": ("60000", "-2"),
}


def list_announcements(
    stock_code: str,
    doc_type: Optional[str] = None,
    year: Optional[int] = None,
    language: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List HKEXnews disclosures for a stock code. Returns collapsed records."""
    code = _normalize_ticker(stock_code) or stock_code
    # Accept "Annual Report" or "Annual_Report" — routing grammar disallows spaces.
    if doc_type:
        doc_type = doc_type.replace("_", " ")
    t2gcode, t2code = _FORM_CODES.get(doc_type, ("-2", "-2"))
    from_date = f"{year}0101" if year else ""
    to_date = f"{year}1231" if year else ""
    lang = {"en": "EN", "zh": "ZH", "both": "EN"}.get(language or "both", "EN")

    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": "SEHK",
        "stockId": code,
        "documentType": "-1",
        "fromDate": from_date,
        "toDate": to_date,
        "t1code": "-2",
        "t2gcode": t2gcode,
        "t2code": t2code,
        "searchType": "0",
        "t3code": "-2",
        "t3code3": "-2",
        "lang": lang,
    }
    resp = _request("GET", _TITLE_SEARCH, params=params)
    resp.raise_for_status()
    raw = _parse_title_search(resp.text)
    return _collapse_duplicates(raw, limit=limit)


# Match a row that titleSearchServlet emits as a JSON-array entry. The
# endpoint returns a small wrapper-JSON with `rows` containing JSON-stringified
# objects; we accept either the wrapper or the inner list to keep tests easy.
def _parse_title_search(body: str) -> list[dict[str, Any]]:
    """Extract a list of raw row dicts from the titleSearchServlet response."""
    import json

    body = body.strip()
    if not body:
        return []
    try:
        data = json.loads(body)
    except ValueError:
        # Some HKEXnews variants wrap the payload in HTML; pull the first
        # JSON-array we can find.
        m = re.search(r"\[\s*\{.*?\}\s*\]", body, re.DOTALL)
        if not m:
            return []
        data = json.loads(m.group(0))

    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        doc_id = str(
            row.get("FILE_ID") or row.get("fileId") or row.get("doc_id") or ""
        )
        published = str(
            row.get("DATE_TIME") or row.get("dateTime") or row.get("published") or ""
        )[:10]
        title = str(row.get("TITLE") or row.get("title") or "").strip()
        # Always canonicalize to an English form label so EN and ZH variants
        # of the same disclosure collapse together downstream.
        form_raw = str(
            row.get("LONG_TEXT") or row.get("doctype") or row.get("form") or ""
        ).strip()
        form = _guess_form(form_raw or "")
        stock = str(
            row.get("STOCK_CODE") or row.get("stockId") or row.get("stock_code") or ""
        )
        url = row.get("FILE_LINK") or row.get("fileLink") or row.get("url") or ""
        if url and not url.startswith("http"):
            url = _BASE + url if url.startswith("/") else f"{_BASE}/{url}"
        lang_raw = (row.get("FILE_TYPE") or row.get("language") or row.get("lang") or "").lower()
        lang = "zh" if "c" in lang_raw or "zh" in lang_raw else "en"

        if not doc_id and not url:
            continue
        out.append({
            "doc_id": doc_id,
            "title": title,
            "form": form or _guess_form(title),
            "form_raw": form_raw,
            "published": _iso_date(published),
            "language": lang,
            "stock_code": _normalize_ticker(stock) or stock,
            "url": url,
        })
    return out


_FORM_KEYWORDS = (
    ("Annual Report", re.compile(r"annual report|年報|年度報告", re.IGNORECASE)),
    ("Interim Report", re.compile(r"interim report|中期報告|半年", re.IGNORECASE)),
    ("Quarterly Report", re.compile(r"quarterly|季度|first quarter|third quarter", re.IGNORECASE)),
    ("Circular", re.compile(r"circular|通函", re.IGNORECASE)),
    ("Listing Document", re.compile(r"listing document|招股", re.IGNORECASE)),
)


def _guess_form(title: str) -> str:
    for label, rx in _FORM_KEYWORDS:
        if rx.search(title or ""):
            return label
    return "Announcement"


_DATE_PATTERNS = (
    (re.compile(r"^(\d{4})-(\d{2})-(\d{2})"), "{0}-{1}-{2}"),
    (re.compile(r"^(\d{2})/(\d{2})/(\d{4})"), "{2}-{1}-{0}"),
    (re.compile(r"^(\d{4})(\d{2})(\d{2})"), "{0}-{1}-{2}"),
)


def _iso_date(raw: str) -> str:
    """Normalize HKEXnews timestamps to ISO-8601 dates."""
    raw = (raw or "").strip()
    for rx, fmt in _DATE_PATTERNS:
        m = rx.match(raw)
        if m:
            return fmt.format(*m.groups())
    return raw  # fall through unchanged; tests will surface if widespread


def _collapse_duplicates(rows: list[dict], limit: int) -> list[dict[str, Any]]:
    """Group rows that share (stock_code, published, form, normalized_title)."""
    grouped: dict[tuple, dict] = {}
    order: list[tuple] = []
    for row in rows:
        key = (
            row.get("stock_code", ""),
            row.get("published", ""),
            row.get("form", ""),
        )
        existing = grouped.get(key)
        if existing is None:
            entry = {
                "doc_id": row["doc_id"],
                "title": row["title"],
                "form": row["form"],
                "published": row["published"],
                "language": row["language"],
                "stock_code": row["stock_code"],
                "documents": [],
            }
            grouped[key] = entry
            order.append(key)
            existing = entry
        if row.get("url"):
            existing["documents"].append({"lang": row["language"], "url": row["url"]})
        # If multiple languages co-exist, report `both`.
        langs = {d["lang"] for d in existing["documents"]} | {row["language"]}
        existing["language"] = "both" if {"en", "zh"} <= langs else next(iter(langs))

    return [grouped[k] for k in order[:limit]]


_NORM_TITLE_RE = re.compile(r"\s+|[\(（].*?[\)）]")


def _norm_title(t: str) -> str:
    return _NORM_TITLE_RE.sub("", (t or "")).lower()


# ── Single filing fetch (task 2.5) ────────────────────────────────────


def fetch_announcement(
    doc_id_or_url: str,
    with_text: bool = True,
    text_cap_bytes: int = 200_000,
) -> dict[str, Any]:
    """Download a HKEXnews PDF (by doc_id or URL) and return metadata + text."""
    url = _resolve_doc_url(doc_id_or_url)
    if not url:
        raise LookupError(f"Could not resolve doc_id_or_url={doc_id_or_url!r}")

    resp = _request("GET", url)
    if resp.status_code == 404:
        raise LookupError(f"Filing not found at {url}")
    resp.raise_for_status()
    pdf_bytes = resp.content

    out: dict[str, Any] = {
        "doc_id": _extract_doc_id(url),
        "title": "",
        "form": "",
        "published": "",
        "stock_code": "",
        "documents": [{"lang": "en", "url": url}],
        "size_bytes": len(pdf_bytes),
    }
    if not with_text or text_cap_bytes == 0:
        return out

    try:
        import pypdf  # lazy import
    except ImportError as e:
        raise ImportError("pypdf is not installed") from e

    from io import BytesIO
    reader = pypdf.PdfReader(BytesIO(pdf_bytes))
    chunks: list[str] = []
    running = 0
    truncated = False
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        running += len(text.encode("utf-8", errors="ignore"))
        if running > text_cap_bytes:
            chunks.append(text[: max(0, text_cap_bytes // 2)])  # tail-trim last page
            truncated = True
            break
        chunks.append(text)
    out["text"] = "\n".join(chunks)
    out["truncated"] = truncated
    out["pages"] = len(reader.pages)
    return out


_DOC_ID_RE = re.compile(r"/(\d{4})/(\d{4})/([^/]+)\.pdf$", re.IGNORECASE)


def _resolve_doc_url(value: str) -> Optional[str]:
    if not value:
        return None
    if value.startswith("http"):
        return value
    # Treat as a doc_id; HKEXnews puts it directly in the canonical path.
    # We don't always know the year/date, so honor it only when caller passes
    # the canonical filename including the directory hint.
    if "/" in value:
        return f"{_BASE}/listedco/listconews/sehk/{value.lstrip('/')}"
    return None


def _extract_doc_id(url: str) -> str:
    m = _DOC_ID_RE.search(url)
    if m:
        return m.group(3)
    return url.rsplit("/", 1)[-1].rsplit(".", 1)[0]


# ── Disclosure calendar (task 2.6) ────────────────────────────────────


def list_calendar(stock_code: str, kind: Optional[str] = None) -> list[dict[str, Any]]:
    """Return upcoming results-announcement / AGM dates for a stock code."""
    code = _normalize_ticker(stock_code) or stock_code
    resp = _request("GET", _CALENDAR, params={"sc_lang": "en", "stockcode": code})
    if resp.status_code >= 400:
        # Calendar feed is best-effort; return empty rather than raising.
        return []
    return _parse_calendar(resp.text, stock_code=code, kind=kind)


_CAL_ROW_RE = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>",
    re.IGNORECASE | re.DOTALL,
)


def _parse_calendar(html: str, stock_code: str, kind: Optional[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for date_raw, _code, event in _CAL_ROW_RE.findall(html or ""):
        ev = event.strip()
        k = _classify_event(ev)
        if kind and k != kind:
            continue
        entries.append({
            "date": _iso_date(date_raw.strip()),
            "kind": k,
            "event": ev,
            "stock_code": stock_code,
        })
    return entries


def _classify_event(event: str) -> str:
    e = event.lower()
    if "agm" in e or "annual general meeting" in e:
        return "agm"
    return "results"
