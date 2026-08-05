#!/usr/bin/env bash
# GitHub Issues QA scope.
# Priority: open validate-testing (handoff retests); if empty → open impl-qa charters.
# Usage: scripts/github_scope.sh <slug> [--log] [--shell] [--json]
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLUG="${1:?slug}"; shift || true
PROJ="$SCRIPT_DIR/../projects/$SLUG"
exec python3 "$SCRIPT_DIR/github_scope.py" --project "$PROJ" "$@"
