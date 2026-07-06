#!/usr/bin/env bash
# Gate: is Jira integration ACTIVE for a project?
# Prints "active" + exit 0 only if .secrets/jira.env exists AND the required connection
# fields are filled with real (non-placeholder) values. Otherwise prints "inactive" + exit 1.
#
# The agent MUST call this before any Jira action; if inactive, do NO Jira work
# (no filing, transitions, comments, or recordings-to-Jira) — just local QA + run.md.
#
# Usage: scripts/jira_status.sh <slug>
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:?slug}"
ENVF="$ROOT/projects/$SLUG/.secrets/jira.env"

[[ -f "$ENVF" ]] || { echo "inactive (no .secrets/jira.env)"; exit 1; }
# shellcheck disable=SC1090
set -a; . "$ENVF" 2>/dev/null; set +a

bad() { echo "inactive ($1)"; exit 1; }
[[ -n "${JIRA_BASE_URL:-}" && "$JIRA_BASE_URL" != *your-company* ]] || bad "JIRA_BASE_URL unset/placeholder"
[[ -n "${JIRA_EMAIL:-}" && "$JIRA_EMAIL" != *your-company* ]] || bad "JIRA_EMAIL unset/placeholder"
[[ -n "${JIRA_API_TOKEN:-}" && "$JIRA_API_TOKEN" != paste-* ]] || bad "JIRA_API_TOKEN unset/placeholder"
[[ -n "${JIRA_PROJECT_KEY:-}" && "$JIRA_PROJECT_KEY" != "ABC" ]] || bad "JIRA_PROJECT_KEY unset/placeholder"

echo "active ($JIRA_PROJECT_KEY @ $JIRA_BASE_URL)"
exit 0
