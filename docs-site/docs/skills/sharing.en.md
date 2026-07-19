# Sharing Dashboards

Two `fd-coding-*` skills expose a local service (a dashboard or this docs site)
to the internet. Use them when you need to share something running on
`localhost` with someone outside your WiFi.

## fd-coding-bore-tunnel (bore)

Simple, fast tunnels via [bore](https://github.com/ekzhang/bore) and `bore.pub`.

**Triggers:** "内网穿透", "外网访问", "expose local service", "share over the
internet".

**Typical use:**

```bash
# Serve the dashboard (or docs) locally on port 8000
cd dashboards && python3 -m http.server 8000 --bind 0.0.0.0
# (or) uv run mkdocs serve --dev-addr 0.0.0.0:8000

# Expose it via bore -> prints a public bore.pub URL
uv run python -m bore local 8000 --to bore.pub
```

The skill manages starting/stopping/managing the tunnel.

## fd-coding-cloudflare-tunnel (cloudflared)

HTTPS tunnels via Cloudflare (`cloudflared`) - no client install needed for a
quick tunnel.

**Triggers:** "内网穿透", "外网访问", "expose local service over HTTPS".

**Typical use:**

```bash
cloudflared tunnel --url http://localhost:8000
# -> prints a public https://<random>.trycloudflare.com URL
```

## When to use which

| Need | Pick |
| --- | --- |
| Quick, no account, HTTP or TCP | `fd-coding-bore-tunnel` |
| HTTPS, Cloudflare-managed, stable hostname | `fd-coding-cloudflare-tunnel` |

## WiFi/LAN-only sharing (no tunnel)

If everyone is on the same WiFi, you don't need a tunnel - just bind to
`0.0.0.0`:

```bash
uv run mkdocs serve --dev-addr 0.0.0.0:8000
# others browse http://<your-LAN-IP>:8000
```

See [Share a Dashboard](../examples/share-dashboard.md) for the full walkthrough.

## Security note

A tunnel publishes your local service to the public internet. Only expose what
you intend to share, and do not leave the tunnel running unattended if the
content is sensitive. Dashboards read from `daas.db` - they expose whatever data
you've fetched.
