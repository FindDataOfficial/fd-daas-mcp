# Share a Dashboard

DAAS dashboards are standalone HTML files registered in the `dashboards` table.
This example shows how to build one and share it over **WiFi/LAN** or a **public
tunnel**.

## 1. Build the dashboard

**Skill:** the `fd-daas-dashboard-creator` skill builds a standalone-HTML
dashboard from your data and registers it:

> Build a dashboard for the `momentum` indicator collection and register it as `my-momentum`.

It writes HTML to repo-root `dashboards/` and a row to the `dashboards` table
(slug, name, source_tables, chart_config, file_path, file_url), then
regenerates `dashboards/index.html` + `daas.md`.

**MCP:**

```text
dashboard_register(slug="my-momentum",
                   name="Momentum Dashboard",
                   intro="RSI + MA signals for my watchlist",
                   source_tables=["observations"],
                   refresh_cadence="daily",
                   file_path="dashboards/my-momentum/index.html",
                   file_url="/dashboards/my-momentum/index.html")
```

**Browse:** `dashboard_list()` / `dashboard_search(keyword="momentum")`.

## 2. Share over WiFi / LAN

Serve the `dashboards/` directory (or this docs site) on your LAN so anyone on
the same WiFi can open it.

```bash
# Option 1: Python's built-in static server
cd dashboards && python3 -m http.server 8000 --bind 0.0.0.0

# Option 2: serve this docs site too
uv run mkdocs serve --dev-addr 0.0.0.0:8000
```

Then from another device on the same WiFi, browse:

```text
http://<this-machine-LAN-IP>:8000
```

Find your LAN IP with `ipconfig getifaddr en0` (macOS) or `hostname -I` (Linux).

!!! warning "WiFi sharing is local-only"
    Devices must be on the same network. For sharing outside your LAN, use a
    tunnel (below).

## 3. Share over a public tunnel

Expose the local port to the public internet with one of the tunnel skills:

**`fd-coding-bore-tunnel`** (bore - simple, fast):

```bash
# expose local port 8000 -> gives you a public bore.pub URL
uv run python -m bore local 8000 --to bore.pub
```

**`fd-coding-cloudflare-tunnel`** (Cloudflare - no client install via
`cloudflared` quick tunnel):

```bash
cloudflared tunnel --url http://localhost:8000
```

Both hand you a public URL you can send to anyone. See
[Sharing Dashboards](../skills/sharing.md) for the full skill walkthrough.

## 4. Refresh the data

Dashboards read from `daas.db`, so to refresh, recompute the underlying
indicators (or `research_refresh` if the dashboard belongs to a research). The
HTML stays the same; the data updates on the next render.

## Next

- Full sharing skill docs: [Sharing Dashboards](../skills/sharing.md).
- Dashboard skill docs: [fd-daas-dashboard](../skills/dashboard.md).
