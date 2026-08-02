#!/usr/bin/env bash
# Read Dev handoff from a GitHub Issue.
# Usage: scripts/github_handoff.sh <slug> <key> [--log] [--json]
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLUG="${1:?slug}"; KEY="${2:?key}"; shift 2 || true
PROJ="$SCRIPT_DIR/../projects/$SLUG"
exec python3 "$SCRIPT_DIR/github_handoff.py" --project "$PROJ" --key "$KEY" "$@"
