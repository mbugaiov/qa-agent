#!/usr/bin/env bash
# Query Jira retest scope for a QA loop tick (Validate/Testing + In Progress).
#
# Usage:
#   scripts/jira_scope.sh <slug>                    # prints keys= count= jql=
#   scripts/jira_scope.sh <slug> --log --shell      # TICK STEP 1: log scope_check + eval exports
#   scripts/jira_scope.sh <slug> --shell            # eval "$(jira_scope.sh <slug> --shell)" → count, SCOPE_COUNT, keys, SCOPE_KEYS
#   scripts/jira_scope.sh <slug> --json
#
# JQL: JIRA_SCOPE_JQL in projects/<slug>/.secrets/jira.env, or epic-derived default.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLUG="${1:?slug}"; shift || true
PROJ="$SCRIPT_DIR/../projects/$SLUG"
exec python3 "$SCRIPT_DIR/jira_scope.py" --project "$PROJ" "$@"
