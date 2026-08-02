#!/usr/bin/env bash
# Tracker-aware handoff read.
# Usage: scripts/qa_handoff.sh <slug> <key> [--log] [--json]
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLUG="${1:?slug}"; KEY="${2:?key}"; shift 2 || true
PROJ="$SCRIPT_DIR/../projects/$SLUG"
PROVIDER="$(python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
from github_tracker import tracker_provider
print(tracker_provider('${PROJ}'))
")"
if [[ "$PROVIDER" == "github_issues" ]]; then
  exec bash "$SCRIPT_DIR/github_handoff.sh" "$SLUG" "$KEY" "$@"
fi
exec bash "$SCRIPT_DIR/jira_handoff.sh" "$SLUG" "$KEY" "$@"
