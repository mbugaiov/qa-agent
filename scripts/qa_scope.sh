#!/usr/bin/env bash
# Tracker-aware QA scope: Jira or GitHub Issues.
# Usage: scripts/qa_scope.sh <slug> [--log] [--shell] [--json]
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLUG="${1:?slug}"; shift || true
PROJ="$SCRIPT_DIR/../projects/$SLUG"
PROVIDER="$(python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
from github_tracker import tracker_provider
print(tracker_provider('${PROJ}'))
")"
if [[ "$PROVIDER" == "github_issues" ]]; then
  exec bash "$SCRIPT_DIR/github_scope.sh" "$SLUG" "$@"
fi
exec bash "$SCRIPT_DIR/jira_scope.sh" "$SLUG" "$@"
