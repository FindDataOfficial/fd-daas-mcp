# Install & Deploy

DAAS runs locally with **uv** and Python 3.10+. Everything reads/writes a single
SQLite file (`daas.db`) at the repo root.

## 1. Clone & install

```bash
git clone https://github.com/chengsishi/DAAS.git
cd DAAS
uv sync            # provisions the root venv (data libs + mkdocs-material)
```

`uv sync` installs runtime dependencies (`akshare`, `yfinance`, `edgar`,
`edinet-tools`, `world_bank_data`, `ckanapi`) and the `dev` group (which
includes `mkdocs-material` for this docs site).

!!! note "Python version"
    The root venv is Python 3.10+. The `dartlab` datasource needs 3.12 - run it
    ad-hoc with `uv run --python 3.12 --with dartlab ...` (it is not a root dep).

## 2. Configure `.env`

Copy the template and fill in only the keys you use:

```bash
cp .env.example .env   # if a template exists; otherwise create .env
```

The single repo-root `.env` holds:

| Key | Purpose |
| --- | --- |
| `DAAS_DATABASE_URL` | `sqlite:///daas.db` (the repo-root DB). |
| `HTTP_PROXY` | Outbound proxy if your network needs one. |
| `EDGAR_IDENTITY` | Your SEC EDGAR user agent. |
| `EDINET_API_KEY` | Japan EDINET API key. |
| `ALERTS_FEISHU_WEBHOOK_URL` | Feishu webhook for alert delivery. |
| `LLM_*` / `LEADER_MODEL*` | Leader agent (CrewAI workflow) model config. |
| `DASHBOARD_PORT` | Port for the dashboard server. |
| `CKAN_PORTAL_URL` | CKAN portal base URL. |

!!! warning "Never commit real secrets"
    `.env` is git-ignored. Examples in this site use placeholders like
    `<YOUR_API_KEY>` - never paste a real key into a doc or commit.

## 3. Launch the MCP server

The consolidated `fd-daas-mcp` server is the sole entry in repo-root
`.mcp.json`. Claude Code picks it up automatically. To launch it manually
(for testing or another MCP client):

```bash
fd-daas-mcp/bin/fd-daas-mcp-server        # the .mcp.json `command`
```

## 4. Self-check

Run the offline invariants to confirm the server is wired correctly:

```bash
fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck
```

## 5. Query `daas.db` directly

From the repo root, the canonical DB is `daas.db` (not `mcp/daas.db`):

```bash
sqlite3 daas.db "SELECT count(*) FROM entities;"
sqlite3 daas.db "SELECT name, op, indicator_name FROM indicator_rules LIMIT 5;"
```

Use `PRAGMA foreign_keys=ON;` when you need FK cascade behavior.

## 6. (Optional) Serve this docs site locally

```bash
uv run mkdocs serve               # http://127.0.0.1:8000
```

See [Contributor Guide -> Deploy the Docs](../contributor/deploy-docs.md) for
GitHub Pages deployment and WiFi/tunnel sharing.

## Next

Continue to [First Fetch in 5 Minutes](first-fetch.md).
