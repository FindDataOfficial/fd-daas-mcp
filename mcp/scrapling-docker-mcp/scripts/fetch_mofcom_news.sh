#!/bin/bash
# Fetch MOFCOM news using scrapling-mcp Docker image.
# Usage: ./fetch_mofcom_news.sh [--json]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

docker run -i --rm \
  -v "$SCRIPT_DIR/fetch_mofcom_news.py:/app/fetch_mofcom_news.py:ro" \
  -v "$SCRIPT_DIR/../data:/app/data" \
  --entrypoint python \
  scrapling-mcp \
  /app/fetch_mofcom_news.py "$@"
