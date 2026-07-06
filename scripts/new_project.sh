#!/usr/bin/env bash
# Create a new per-project QA workspace from projects/_template.
# Usage: scripts/new_project.sh <slug> [base_url] ["Project Name"]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$ROOT/projects/_template"

SLUG="${1:-}"
BASE_URL="${2:-https://staging.example.com}"
NAME="${3:-$SLUG}"

if [[ -z "$SLUG" ]]; then
  echo "Usage: scripts/new_project.sh <slug> [base_url] [\"Project Name\"]" >&2
  exit 1
fi
if [[ ! "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Error: slug must be lowercase letters, digits, and hyphens (e.g. acme-shop)." >&2
  exit 1
fi

DEST="$ROOT/projects/$SLUG"
if [[ -e "$DEST" ]]; then
  echo "Error: $DEST already exists." >&2
  exit 1
fi

cp -R "$TEMPLATE" "$DEST"
mkdir -p "$DEST/.secrets"
# Seed gitignored secrets stubs
if [[ -f "$DEST/jira.env.example" ]]; then
  cp "$DEST/jira.env.example" "$DEST/.secrets/jira.env.example"
fi
if [[ -f "$DEST/server.env.example" ]]; then
  cp "$DEST/server.env.example" "$DEST/.secrets/server.env.example"
fi

# Fill in the obvious placeholders in project.yaml
TODAY="$(date +%Y-%m-%d)"
if command -v sed >/dev/null 2>&1; then
  sed -i '' \
    -e "s|name: \"<Project Name>\"|name: \"$NAME\"|" \
    -e "s|slug: \"<slug>\"|slug: \"$SLUG\"|" \
    -e "s|base_url: https://staging.example.com|base_url: $BASE_URL|" \
    -e "s|app_name: \"<App>\"|app_name: \"$NAME\"|" \
    "$DEST/project.yaml" 2>/dev/null || \
  sed -i \
    -e "s|name: \"<Project Name>\"|name: \"$NAME\"|" \
    -e "s|slug: \"<slug>\"|slug: \"$SLUG\"|" \
    -e "s|base_url: https://staging.example.com|base_url: $BASE_URL|" \
    -e "s|app_name: \"<App>\"|app_name: \"$NAME\"|" \
    "$DEST/project.yaml"
fi

echo "Created project: projects/$SLUG"
echo "  - project.yaml      (name=$NAME, url=$BASE_URL)"
echo "  - project-memory.md (persistent context)"
echo "  - requirements/ test-cases/ runs/ reports/ automation/specs/ .secrets/"
echo ""
echo "Next:"
echo "  1. Add requirements to projects/$SLUG/requirements/"
echo "  2. Put credentials in projects/$SLUG/.secrets/ (gitignored)"
echo "  3. Ask the agent: \"Run a QA engagement on projects/$SLUG\""
