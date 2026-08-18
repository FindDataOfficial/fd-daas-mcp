#!/bin/sh
# DAAS one-click install.
#   curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-daas-mcp/master/install.sh | sh
# Clones DAAS + the fd-open-data-mcp/-protocol upstreams, provisions venvs,
# initializes daas.db, and rewrites .mcp.json to the local paths.
# Env overrides: DAAS_DEST (default ~/code/DAAS), DAAS_BRANCH (default master),
# FINDDATA_HOME (default ~/finddata).
set -e

REPO_URL="https://github.com/FindDataTechnology/fd-daas-mcp.git"
BRANCH="${DAAS_BRANCH:-master}"
DEST="${DAAS_DEST:-$HOME/code/DAAS}"
FINDDATA="${FINDDATA_HOME:-$HOME/finddata}"

say() { printf '\n== %s\n' "$*"; }

# 1. uv
if ! command -v uv >/dev/null 2>&1; then
  say "installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || { echo "uv not on PATH; install https://docs.astral.sh/uv/ and rerun" >&2; exit 1; }

# 2. clone DAAS
say "clone DAAS ($BRANCH) -> $DEST"
if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$(dirname "$DEST")"
  git clone -b "$BRANCH" "$REPO_URL" "$DEST"
fi
cd "$DEST"
[ -d fd-daas-mcp ] || { echo "fd-daas-mcp/ missing on branch '$BRANCH' — not a DAAS monorepo branch" >&2; exit 1; }

# 3. clone the data-fetch upstreams (fd-daas-mcp path-depends on fd-open-data-mcp,
#    which itself path-depends on ../fd-open-data-protocol — keep the sibling layout)
say "clone fd-open-data-mcp + fd-open-data-protocol -> $FINDDATA"
mkdir -p "$FINDDATA"
[ -d "$FINDDATA/fd-open-data-mcp/.git" ] || \
  git clone https://github.com/FindDataTechnology/fd-open-data-mcp.git "$FINDDATA/fd-open-data-mcp"
[ -d "$FINDDATA/fd-open-data-protocol/.git" ] || \
  git clone https://github.com/FindDataTechnology/fd-open-data-protocol.git "$FINDDATA/fd-open-data-protocol"

# 4. repoint fd-daas-mcp's machine-local path dep at our clone
sed -i.bak "s|path = \"/Users/chengsishi/finddata/fd-open-data-mcp\"|path = \"$FINDDATA/fd-open-data-mcp\"|" \
  fd-daas-mcp/pyproject.toml && rm -f fd-daas-mcp/pyproject.toml.bak

# 5. venvs
say "uv sync (root + fd-daas-mcp)"
uv sync
(cd fd-daas-mcp && uv sync)

# 6. database + health check
say "init daas.db + doctor"
fd-daas-mcp/.venv/bin/fd-daas-mcp init
fd-daas-mcp/.venv/bin/fd-daas-mcp doctor

# 7. localize .mcp.json (absolute launcher + db paths)
sed -i.bak "s|/Users/chengsishi/code/DAAS|$DEST|g" .mcp.json && rm -f .mcp.json.bak

# 8. handoff — paste this block to your AI assistant if it needs to wire things manually
say "done: $DEST"
cat <<EOF

Deployed. Open $DEST in Claude Code — .mcp.json is already localized.

Paste to your AI assistant for manual wiring / verification:

  MCP server : $DEST/fd-daas-mcp/bin/fd-daas-mcp-server   (stdio)
  Database   : sqlite:///$DEST/daas.db
  Health     : $DEST/fd-daas-mcp/.venv/bin/fd-daas-mcp doctor
  Selfcheck  : $DEST/fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck

Optional keys (repo-root .env): HTTP_PROXY, EDGAR_IDENTITY, EDINET_API_KEY,
LLM_*/LEADER_MODEL*, ALERTS_FEISHU_WEBHOOK_URL
Docs: README.md + docs-site/ (uv run mkdocs serve)
EOF
