#!/usr/bin/env bash
# Record a retest flow, ensure the video is <= MAX_MB, attach it to a Jira ticket,
# then delete the local file (recording lives only in Jira).
#
# Usage: scripts/record_and_attach.sh <slug> <TICKET-KEY> <stepsJsonFile> [caption]
# Requires: app repo with playwright (SERVER_CWD from .secrets/server.env), ffmpeg.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:?slug}"; KEY="${2:?ticket key}"; STEPS="${3:?steps json}"; CAPTION="${4:-QA retest recording}"
MAX_MB=10
PROJ="$ROOT/projects/$SLUG"
ENVF="$PROJ/.secrets/server.env"; JENV="$PROJ/.secrets/jira.env"
# shellcheck disable=SC1090
set -a; . "$ENVF"; . "$JENV"; set +a
APP_CWD="${SERVER_CWD:?SERVER_CWD needed (app repo with playwright)}"

TMP="$(mktemp -d /tmp/qa-rec-XXXX)"
trap 'rm -rf "$TMP"' EXIT

PW_NODE="$APP_CWD/node_modules"
if [[ ! -d "$PW_NODE/playwright" && -d "$PROJ/automation/node_modules/playwright" ]]; then
  PW_NODE="$PROJ/automation/node_modules"
fi
echo "Recording retest for $KEY…"
RAW="$( NODE_PATH="$PW_NODE" node "$SCRIPT_DIR/record_retest.cjs" "$STEPS" "$TMP" | tail -n1 )"
[[ -f "$RAW" ]] || { echo "recording failed" >&2; exit 1; }

# Compress to <= MAX_MB if needed (mp4 h264, scale down, drop fps)
OUT="$TMP/${KEY}-retest.mp4"
size_mb() { echo $(( ($(stat -f%z "$1" 2>/dev/null || stat -c%s "$1")) / 1048576 + 1 - 1 )); }
# Report sub-MB sizes accurately for logs
size_kb() { echo $(( ($(stat -f%z "$1" 2>/dev/null || stat -c%s "$1")) / 1024 )); }
ffmpeg -y -loglevel error -i "$RAW" -vf "scale=1024:-2,fps=12" -c:v libx264 -preset veryfast -crf 30 -pix_fmt yuv420p -an "$OUT" 2>/dev/null || cp "$RAW" "$OUT"
# If still too big, re-encode harder
if [[ "$(size_mb "$OUT")" -gt "$MAX_MB" ]]; then
  ffmpeg -y -loglevel error -i "$RAW" -vf "scale=854:-2,fps=10" -c:v libx264 -preset veryfast -crf 34 -pix_fmt yuv420p -an "$OUT" 2>/dev/null
fi
MB="$(size_mb "$OUT")"
KB="$(size_kb "$OUT")"
echo "video size: ${KB}KB (${MB}MB)"
BYTES=$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT")
if [[ "$BYTES" -lt 10240 ]]; then echo "ERROR: video too small (${BYTES} bytes); not attaching" >&2; exit 1; fi
if [[ "$MB" -gt "$MAX_MB" ]]; then echo "ERROR: still > ${MAX_MB}MB after compression; not attaching" >&2; exit 1; fi

# Attach to Jira (multipart) + add an evidence comment
B="${JIRA_BASE_URL%/}"
HTTP=$(curl -sS -o /dev/null -w "%{http_code}" -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -H "X-Atlassian-Token: no-check" -F "file=@$OUT;type=video/mp4" \
  "$B/rest/api/3/issue/$KEY/attachments")
echo "attach $OUT -> HTTP $HTTP"
[[ "$HTTP" -lt 300 ]] || { echo "attach failed" >&2; exit 1; }
echo "Attached retest recording to $KEY (${MB}MB). Local copy discarded."
