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

# Fill placeholders in scaffolded files
subst_placeholders() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  if sed -i '' \
    -e "s|<Project Name>|$NAME|g" \
    -e "s|<slug>|$SLUG|g" \
    -e "s|<App>|$NAME|g" \
    -e "s|name: \"<Project Name>\"|name: \"$NAME\"|" \
    -e "s|slug: \"<slug>\"|slug: \"$SLUG\"|" \
    -e "s|base_url: https://staging.example.com|base_url: $BASE_URL|" \
    -e "s|app_name: \"<App>\"|app_name: \"$NAME\"|" \
    -e "s|\"<slug>-qa-automation\"|\"$SLUG-qa-automation\"|" \
    "$f" 2>/dev/null; then
    return 0
  fi
  sed -i \
    -e "s|<Project Name>|$NAME|g" \
    -e "s|<slug>|$SLUG|g" \
    -e "s|<App>|$NAME|g" \
    -e "s|name: \"<Project Name>\"|name: \"$NAME\"|" \
    -e "s|slug: \"<slug>\"|slug: \"$SLUG\"|" \
    -e "s|base_url: https://staging.example.com|base_url: $BASE_URL|" \
    -e "s|app_name: \"<App>\"|app_name: \"$NAME\"|" \
    -e "s|\"<slug>-qa-automation\"|\"$SLUG-qa-automation\"|" \
    "$f"
}

for f in \
  "$DEST/project.yaml" \
  "$DEST/project-memory.md" \
  "$DEST/README.md" \
  "$DEST/automation/README.md" \
  "$DEST/automation/package.json"; do
  subst_placeholders "$f"
done

echo "Created project: projects/$SLUG"
echo "  - project.yaml      (name=$NAME, url=$BASE_URL)"
echo "  - project-memory.md (persistent context)"
echo "  - requirements/ test-cases/ runs/ reports/ automation/specs/ .secrets/"
echo ""
echo "Next:"
echo "  1. Add requirements to projects/$SLUG/requirements/"
echo "  2. Put credentials in projects/$SLUG/.secrets/ (gitignored)"
echo "  3. Ask the agent: \"Run a QA engagement on projects/$SLUG\""
