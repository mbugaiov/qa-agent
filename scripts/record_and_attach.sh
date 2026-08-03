#!/usr/bin/env bash
# Record a retest flow, compress, attach to the tracker ticket, discard local copy.
#
# Usage: scripts/record_and_attach.sh <slug> <TICKET-KEY> <stepsJsonFile> [caption]
# Tracker:
#   Jira  → multipart MP4 attach (≤10MB)
#   GitHub Issues → convert to GIF + inline ``![…](url)`` comment (not MP4 packs on qa-evidence)
# Requires: app repo with playwright (SERVER_CWD from .secrets/server.env), ffmpeg.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:?slug}"; KEY="${2:?ticket key}"; STEPS="${3:?steps json}"; CAPTION="${4:-QA retest recording}"
MAX_MB=10
PROJ="$ROOT/projects/$SLUG"
ENVF="$PROJ/.secrets/server.env"
JENV="$PROJ/.secrets/jira.env"
GENV="$PROJ/.secrets/github.env"

[[ -f "$ENVF" ]] || { echo "Missing $ENVF (SERVER_CWD)" >&2; exit 1; }

PROVIDER=$(python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from github_tracker import tracker_provider
print(tracker_provider('$PROJ'))
" 2>/dev/null || echo jira)

# shellcheck disable=SC1090
set -a
# shellcheck source=/dev/null
. "$ENVF"
if [[ "$PROVIDER" == "github_issues" ]]; then
  [[ -f "$GENV" ]] && . "$GENV"
else
  # Per-project isolation (same as create_jira_issue.py): jira.env is mandatory and
  # the ONLY source of attach credentials — never fall back to ambient JIRA_*.
  [[ -f "$JENV" ]] || {
    echo "Missing $JENV — cannot attach recording to Jira (ambient JIRA_* ignored)" >&2
    exit 1
  }
  unset JIRA_BASE_URL JIRA_EMAIL JIRA_API_TOKEN
  # shellcheck source=/dev/null
  . "$JENV"
fi
set +a

APP_CWD="${SERVER_CWD:?SERVER_CWD needed (app repo with playwright)}"

TMP="$(mktemp -d /tmp/qa-rec-XXXX)"
trap 'rm -rf "$TMP"' EXIT

PW_NODE="$APP_CWD/node_modules"
if [[ ! -d "$PW_NODE/playwright" && -d "$PROJ/automation/node_modules/playwright" ]]; then
  PW_NODE="$PROJ/automation/node_modules"
fi
echo "Recording retest for $KEY (tracker=$PROVIDER)…"
RAW="$( NODE_PATH="$PW_NODE" node "$SCRIPT_DIR/record_retest.cjs" "$STEPS" "$TMP" | tail -n1 )"
[[ -f "$RAW" ]] || { echo "recording failed" >&2; exit 1; }

# Sanitize key for filesystem (# not allowed in some contexts)
SAFE_KEY="${KEY//#/-}"
OUT="$TMP/${SAFE_KEY}-retest.mp4"
size_mb() { echo $(( ($(stat -f%z "$1" 2>/dev/null || stat -c%s "$1")) / 1048576 + 1 - 1 )); }
size_kb() { echo $(( ($(stat -f%z "$1" 2>/dev/null || stat -c%s "$1")) / 1024 )); }
ffmpeg -y -loglevel error -i "$RAW" -vf "scale=1024:-2,fps=12" -c:v libx264 -preset veryfast -crf 30 -pix_fmt yuv420p -an "$OUT" 2>/dev/null || cp "$RAW" "$OUT"
if [[ "$(size_mb "$OUT")" -gt "$MAX_MB" ]]; then
  ffmpeg -y -loglevel error -i "$RAW" -vf "scale=854:-2,fps=10" -c:v libx264 -preset veryfast -crf 34 -pix_fmt yuv420p -an "$OUT" 2>/dev/null
fi
MB="$(size_mb "$OUT")"
KB="$(size_kb "$OUT")"
echo "video size: ${KB}KB (${MB}MB)"
BYTES=$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT")
if [[ "$BYTES" -lt 10240 ]]; then echo "ERROR: video too small (${BYTES} bytes); not attaching" >&2; exit 1; fi
if [[ "$MB" -gt "$MAX_MB" ]]; then echo "ERROR: still > ${MAX_MB}MB after compression; not attaching" >&2; exit 1; fi

if [[ "$PROVIDER" == "github_issues" ]]; then
  ATTACH_OUT=$(python3 "$SCRIPT_DIR/github_attach_evidence.py" \
    --project "$PROJ" \
    --key "$KEY" \
    --file "$OUT" \
    --caption "$CAPTION") || exit $?
  echo "$ATTACH_OUT"
  echo "$ATTACH_OUT" | grep -Eq 'recording_attached=true|bug_recording_attached=true|evidence_attached=true' \
    || { echo "ERROR: GitHub attach soft-skipped or missing success flag" >&2; exit 1; }
  echo "Attached retest GIF inline on $KEY via GitHub issue comment. Local copy discarded."
  exit 0
fi

# Jira multipart attach
if [[ -z "${JIRA_BASE_URL:-}" || -z "${JIRA_EMAIL:-}" || -z "${JIRA_API_TOKEN:-}" ]]; then
  echo "Jira not configured for $SLUG — cannot attach recording" >&2
  exit 1
fi
B="${JIRA_BASE_URL%/}"
HTTP=$(curl -sS -o /dev/null -w "%{http_code}" -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -H "X-Atlassian-Token: no-check" -F "file=@$OUT;type=video/mp4" \
  "$B/rest/api/3/issue/$KEY/attachments")
echo "attach $OUT -> HTTP $HTTP"
[[ "$HTTP" -lt 300 ]] || { echo "attach failed" >&2; exit 1; }
echo "Attached retest recording to $KEY (${MB}MB). Local copy discarded."
