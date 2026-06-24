# MCP PAAS — MCP Server Hosting Platform

## Description
Build a full-stack platform to deploy, host, and manage MCP servers as a service. After `code/create-mcp` generates an MCP server, this platform takes over: deploy it (locally or in Docker), manage its lifecycle, route traffic to it, and monitor its health — all through a web dashboard. This is the "run" side, complementing the "build" side from `code/create-mcp.md`.

## Steps

1. **Design the server registry** — Define the data model for registered MCP servers (name, source path, runtime config, port, health URL, status). Each server is tracked in a registry file (YAML or SQLite). Create the schema at `template/config/template.paas.yaml`.

2. **Build the lifecycle manager** — A Python module that manages MCP server processes: start (subprocess/uvicorn), stop (graceful shutdown), restart, and status check. Handles port allocation and process group tracking. Must work for both local subprocess and Docker modes.

3. **Implement routing & discovery** — A reverse proxy (or simple port router) that assigns each MCP server a unique endpoint. Clients discover servers via a `/api/servers` registry endpoint. Support SSE transport (the MCP default).

4. **Add monitoring & health checks** — Per-server health endpoint polling, log collection (stdout/stderr capture), and basic metrics (uptime, request count, last error). Expose via `/api/servers/:id/health` and `/api/servers/:id/logs`.

5. **Build the web dashboard** — Extend the existing dashboard pattern (`dashboard/`) or create a new SPA to: list registered servers, deploy new ones (point to a YAML config or generated `server.py`), start/stop/restart, view logs and health status. Vanilla JS + Tailwind CDN, no build step.

6. **Add Docker deployment support** — When a server is deployed, optionally package it as a Docker container (generate Dockerfile, build, run). The lifecycle manager should detect Docker availability and offer it as a deployment mode.

7. **Write tests** — Integration tests for lifecycle manager (start/stop/restart cycles), routing tests (endpoint reachability), and API tests for the dashboard. Use pytest + tempfile pattern.

8. **Document the full workflow** — Document the end-to-end flow: `code/create-mcp` generates server → PAAS platform deploys and hosts it → dashboard monitors it.

## Success Criteria
- Deploy a generated MCP server with one CLI command or dashboard click, and it's reachable at its endpoint
- Start/stop/restart works without orphaned processes
- Dashboard shows real-time status of all servers
- Health checks detect down servers within 30 seconds
- Docker mode: a `docker-compose up` equivalent launches the server containerized
- All tests pass

## Constraints
- Local-first: works on a single machine without cloud dependencies
- Docker support is optional (gracefully degrade if Docker not installed)
- Dashboard follows the same pattern as the existing dashboard (vanilla JS, no bundler)
- Generated servers from `code/create-mcp` should be deployable with zero manual config changes
- Port range for MCP servers: 8100-8199 (configurable)
