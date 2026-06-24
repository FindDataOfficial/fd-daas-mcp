#!/bin/bash
# install.sh — Install all fd-coding skills
# Usage:
#   ./install.sh                          → install to ~/.claude/skills/
#   ./install.sh /path/to/project         → install to project's .claude/skills/
#   ./install.sh --global                 → install to ~/.claude/skills/

set -euo pipefail

# Resolve target directory
if [ "${1:-}" = "--global" ] || [ -z "${1:-}" ]; then
  TARGET="$HOME/.claude/skills"
else
  TARGET="$1/.claude/skills"
fi

# Find the source directory (where this script and the skills live)
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Installing fd-coding skills to: $TARGET"
mkdir -p "$TARGET"

# Copy all fd-coding-* skill directories
for dir in "$SOURCE"/fd-coding-*; do
  name="$(basename "$dir")"
  echo "    Copying $name..."
  rm -rf "$TARGET/$name"
  cp -r "$dir" "$TARGET/$name"
done

echo ""
echo "==> Done! Installed $(ls -d "$SOURCE"/fd-coding-* | wc -l | tr -d ' ') skills:"
ls -d "$TARGET"/fd-coding-* | while read d; do
  echo "    $(basename "$d")"
done

echo ""
echo "==> Available slash commands:"
echo "    /fd-coding-goal-clear        — Brainstorm and refine goals"
echo "    /fd-coding-diagram-creator   — Design class diagrams"
echo "    /fd-coding-schema-creator    — Generate SQLAlchemy models"
echo "    /fd-coding-plan-creator      — Plan pages and services"
echo "    /fd-coding-code-creator      — Generate implementations"
echo "    /fd-coding-project-builder   — TDD project builder"
