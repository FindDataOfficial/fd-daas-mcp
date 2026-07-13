---
name: fd-daas-pdf
description: Ingest a PDF or text document into a LOCAL vector store and search it semantically - extract text, chunk, embed with sentence-transformers, store vectors in daas.db (sqlite-vec), then run KNN "ask questions over the document" searches with doc/page citations. Use this skill whenever the user wants to embed a PDF/text and search it by meaning - phrases like "把这个PDF存进去然后能搜索", "ingest this PDF and search it", "embed this 10-K and ask questions", "搜索这个年报里的内容", "把这个文本向量化然后检索", or any PDF/text + "ingest/embed/存/向量化 + 搜索/search/ask/检索". Do NOT use this skill for structured-field extraction from text (use fd-daas-fetch-data + daas_extract_text) or for cnreport keyword/BM25 search - this is local semantic vector search. Requires the [pdf] extra (sqlite-vec + sentence-transformers); the first ingest downloads the embedding model once. No API key, no document egress.
---

# fd-daas-pdf

Ingest a PDF (or raw text) into a **local** vector store, then search it
semantically. Embeddings are computed on-machine by `sentence-transformers`;
vectors live in the `pdf_chunks_vec` `vec0` table in `daas.db` (via the
`sqlite-vec` extension). No document content ever leaves the machine - there is
no API key and no third-party RAG service.

This skill drives the `pdf` tool group on the `fd-daas-mcp` consolidated
server/CLI (the single implementation). Read-only listing also works via a
`sqlite3` helper script.

## Prerequisites

- The `[pdf]` extra must be installed in the `fd-daas-mcp` venv:
  ```bash
  fd-daas-mcp/.venv/bin/python -m pip install sqlite-vec   # uv pip install sqlite-vec also works
  ```
  (`sentence-transformers`, `pdfplumber`, `pypdf` are already in the venv.)
- `PDF_EMBEDDING_MODEL` / `PDF_EMBEDDING_BACKEND` are optional in the repo-root
  `.env` (default `BAAI/bge-m3` via `sentence-transformers`). The **first**
  ingest downloads the model once from HuggingFace (a model fetch, not document
  egress). For a smaller/faster model set `PDF_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- **`uv run` is broken for fd-daas-mcp** - always invoke the CLI via
  `fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli ...`.

## Mental model

1. **Resolve the source** - a local PDF path, an HTTP URL, or raw text. Existing
   fetched filings (cnreport cache, edgar/edinet URLs) plug in directly as
   `file_path=` / `url=`.
2. **Ingest** - `pdf_ingest_document` (path/URL) or `pdf_ingest_text` (raw text):
   extract -> chunk (1000 chars, 200 overlap, page-aware) -> embed -> persist to
   `pdf_documents` + `pdf_chunks` + `pdf_chunks_vec`. SHA-256 dedup makes
   re-ingest a no-op. Returns `doc_id`, `chunk_count`, `status`.
3. **Search** - `pdf_search(query, top_k=5, doc_id=None)`: embeds the query,
   runs KNN over `pdf_chunks_vec`, returns ranked chunks with `doc_name`,
   `page_number`, `score`. Optional `doc_id` restricts to one document.

## Commands (via the fd-daas-mcp CLI)

All run from the repo root with `fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli`:

```bash
# Ingest a local PDF
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf ingest_document file_path=/path/to/filing.pdf --json

# Ingest from a URL (edgar/cnreport/edinet filing URL)
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf ingest_document url=https://www.sec.gov/.../10-K.pdf --json

# Ingest raw text
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf ingest_text text="..." name=transcript --json

# Search
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf search query="revenue growth" top_k=5 --json

# Search within one document
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf search query="dividend policy" doc_id=3 --json

# List / get / delete
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf list_documents --json
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf get_document doc_id=3 --json
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli pdf delete_document doc_id=3 --json
```

### Cron one-shot branches (for cron-mcp batch indexing / periodic queries)

```bash
fd-daas-mcp/.venv/bin/python fd-daas-mcp/pdf-mcp/server.py --pdf-ingest /path/to/filing.pdf
fd-daas-mcp/.venv/bin/python fd-daas-mcp/pdf-mcp/server.py --pdf-search "revenue growth"
# also reachable via the consolidated CLI:
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli --pdf-ingest /path/to/filing.pdf
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.cli --pdf-search "revenue growth"
```

## Read-only listing via sqlite3 (no extra deps)

`scripts/db.py` reads `DAAS_DATABASE_URL` from the repo-root `.env` and lists
ingested documents directly from `daas.db`:

```bash
uv run python .claude/skills/fd-daas-pdf/scripts/db.py            # list all
uv run python .claude/skills/fd-daas-pdf/scripts/db.py --doc 3    # one doc + its chunks
```

## No-egress guarantee

Embeddings run on local CPU/GPU. The only network access is the one-time model
download from HuggingFace on first ingest (a model fetch, **not** document
egress). No API key is read. Ingesting a sensitive filing is safe - its text
never leaves the machine.

## Integration with existing fetched filings

Feed fetched PDFs straight in - a local PDF path, or an edgar/edinet filing URL:
- local PDF -> `file_path=/path/to/filing.pdf`
- edgar/edinet filing URLs -> `url=https://...`

This complements (does not replace) `daas_extract_text`/`daas_extract_file`
(structured-field extraction).

## Notes / limitations (v1)

- **Scanned PDFs** (image-only) yield `status="no_text"` with `chunk_count=0`;
  OCR is a future extra.
- **Model swap**: changing `PDF_EMBEDDING_MODEL` to a different-dim model makes
  existing vectors incompatible - `pdf_search` returns a clear dim-mismatch
  error directing re-ingest.
- **No RAG synthesis/chat tool** in v1 - `pdf_search` returns ranked chunks; feed
  them to `daas_extract_text` for synthesis.
- **Per-doc search** fetches a wider KNN window and filters by `doc_id` (vec0 has
  no per-partition filter in this schema); fine for moderate corpora.
