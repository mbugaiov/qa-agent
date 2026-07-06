#!/usr/bin/env bash
# Create a new run (task) inside an existing project.
# One project (slug) = many runs. Does NOT create a new project.
#
# Usage: scripts/new_run.sh <slug> <type> "<task title>"
#   type: targeted | exploratory | regression | smoke | uat | full
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATES="$ROOT/templates"

SLUG="${1:-}"
TYPE="${2:-}"
TASK="${3:-}"

VALID_TYPES="targeted exploratory regression smoke uat full"

usage() {
  echo "Usage: scripts/new_run.sh <slug> <type> \"<task title>\"" >&2
  echo "  type: $VALID_TYPES" >&2
  exit 1
}

[[ -z "$SLUG" || -z "$TYPE" || -z "$TASK" ]] && usage
[[ " $VALID_TYPES " == *" $TYPE "* ]] || { echo "Error: invalid type '$TYPE'." >&2; usage; }

PROJECT="$ROOT/projects/$SLUG"
if [[ ! -d "$PROJECT" ]]; then
  echo "Error: project 'projects/$SLUG' does not exist." >&2
  echo "Create it first: scripts/new_project.sh $SLUG <base_url> \"<Name>\"" >&2
  exit 1
fi

TODAY="$(date +%Y-%m-%d)"
# task slug: lowercase, spaces/punct -> hyphens, trimmed
TASK_SLUG="$(printf '%s' "$TASK" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-40)"
RUN_ID="${TODAY}-${TYPE}-${TASK_SLUG}"
RUN_DIR="$PROJECT/runs/$RUN_ID"

if [[ -e "$RUN_DIR" ]]; then
  RUN_ID="${RUN_ID}-$(date +%H%M)"
  RUN_DIR="$PROJECT/runs/$RUN_ID"
fi

mkdir -p "$RUN_DIR/screenshots"

# run manifest
sed -e "s|<task title>|$TASK|" \
    -e "s|<YYYY-MM-DD>-<type>-<task-slug>|$RUN_ID|" \
    -e "s|targeted \| exploratory \| regression \| smoke \| uat \| full|$TYPE|" \
    -e "s|<YYYY-MM-DD>|$TODAY|" \
    "$TEMPLATES/run.md" > "$RUN_DIR/run.md"

# type-specific starting artifact
case "$TYPE" in
  exploratory)
    sed -e "s|<Target>|$SLUG|; s|<date>|$TODAY|" "$TEMPLATES/exploratory-session.md" > "$RUN_DIR/exploratory-session.md"
    ;;
  full|uat)
    sed -e "s|<Target Name>|$SLUG|; s|<date>|$TODAY|" "$TEMPLATES/execution-log.md" > "$RUN_DIR/execution-log.md"
    cp "$TEMPLATES/traceability-matrix.md" "$RUN_DIR/traceability-matrix.md"
    cp "$TEMPLATES/manual-test-plan.md"   "$RUN_DIR/manual-test-plan.md"
    cp "$TEMPLATES/risk-register.md"      "$RUN_DIR/risk-register.md"
    cp "$TEMPLATES/acceptance-report.md"  "$RUN_DIR/acceptance-report.md"
    ;;
  *)  # targeted | regression | smoke
    sed -e "s|<Target Name>|$SLUG|; s|<date>|$TODAY|" "$TEMPLATES/execution-log.md" > "$RUN_DIR/execution-log.md"
    ;;
esac

echo "Created run: projects/$SLUG/runs/$RUN_ID  (type=$TYPE)"
echo "  task: $TASK"
ls -1 "$RUN_DIR"
echo ""
echo "Next: fill the scope in run.md, then execute per AGENTS.md."
