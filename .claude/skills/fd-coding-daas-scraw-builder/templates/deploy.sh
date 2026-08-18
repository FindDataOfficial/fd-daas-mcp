#!/usr/bin/env bash
# Standard deploy: build egg + scrapyd-deploy to the shared scraw-ops scrapyd.
set -euo pipefail

SCRAPYD_URL="${SCRAPYD_URL:-http://localhost:6800}"
PROJECT="scraw___SRC_UNDERSCORE__"
EGG_FILE="${PROJECT}.egg"

echo "=== Building egg ==="
scrapyd-deploy --build-egg "$EGG_FILE"
echo "Egg built: $EGG_FILE"

echo "=== Deploying to $SCRAPYD_URL ==="
scrapyd-deploy production --project "$PROJECT" --version "$(date +%Y%m%d%H%M%S)"

echo "=== Deployment complete ==="
echo "Project: $PROJECT"
echo "URL: $SCRAPYD_URL"
echo ""
echo "Available spiders:"
curl -s "$SCRAPYD_URL/listspiders.json?project=$PROJECT" | python3 -m json.tool 2>/dev/null || echo "(scrapyd not reachable)"
