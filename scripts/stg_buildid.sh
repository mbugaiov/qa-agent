#!/usr/bin/env bash
# STG buildId gate for L5 auto-accept. Reads the LIVE deployed buildId from
# the STG /api/health endpoint so the QA loop only auto-accepts a ticket to Done when
# STG actually serves the expected merge commit (STG can lag main).
#
# Config: projects/<slug>/.secrets/server.env
#   STG_URL=http://<stg-host>            # base URL of the deployed STG app
#   STG_HEALTH_PATH=/api/health          # optional (default /api/health)
#   SERVER_GIT_WORKTREE or SERVER_GIT_SRC_REPO — optional; enables ancestor gate
#     when live STG buildId is AHEAD of the handoff SHA but still includes it.
#
# Usage:
#   scripts/stg_buildid.sh <slug>                              # print live STG buildId
#   scripts/stg_buildid.sh <slug> <expected-sha>               # gate (live from STG)
#   scripts/stg_buildid.sh <slug> <expected-sha> --offline <live-sha>  # gate without curl (tests)
#
# Gate outcomes (exit 0 = pass, 2 = fail):
#   MATCH        — live equals handoff (prefix match on short/long sha)
#   MATCH_AHEAD  — live is ahead of handoff; handoff commit is an ancestor of live STG
#   MISMATCH_BEHIND — live is behind handoff (STG not deployed yet)
#   MISMATCH     — unrelated or git ancestry unavailable
#
# Exit 3 if STG_URL unset (live mode only), 4 if health unreachable/no buildId.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"; EXPECT="${2:-}"; OFFLINE_LIVE=""
[[ -z "$SLUG" ]] && { echo "Usage: stg_buildid.sh <slug> [expected-sha] [--offline <live-sha>]" >&2; exit 1; }

if [[ "${3:-}" == "--offline" ]]; then
  OFFLINE_LIVE="${4:-}"
  [[ -n "$OFFLINE_LIVE" ]] || { echo "Usage: stg_buildid.sh <slug> <expected-sha> --offline <live-sha>" >&2; exit 1; }
fi

ENVF="$ROOT/projects/$SLUG/.secrets/server.env"
[[ -f "$ENVF" ]] || { echo "Missing $ENVF" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; . "$ENVF"; set +a

norm_sha() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }

git_repo_for_gate() {
  if [[ -n "${SERVER_GIT_WORKTREE:-}" && -d "${SERVER_GIT_WORKTREE}/.git" ]]; then
    printf '%s' "$SERVER_GIT_WORKTREE"
  elif [[ -n "${SERVER_GIT_SRC_REPO:-}" && -d "${SERVER_GIT_SRC_REPO}/.git" ]]; then
    printf '%s' "$SERVER_GIT_SRC_REPO"
  fi
}

resolve_git_commit() {
  local repo="$1" ref="$2" out
  out="$(git -C "$repo" rev-parse --verify "${ref}^{commit}" 2>/dev/null)" || return 1
  printf '%s' "$out"
}

ancestor_gate() {
  local live="$1" expect="$2"
  local repo live_full expect_full
  repo="$(git_repo_for_gate)" || return 1
  live_full="$(resolve_git_commit "$repo" "$live")" || return 1
  expect_full="$(resolve_git_commit "$repo" "$expect")" || return 1

  if git -C "$repo" merge-base --is-ancestor "$expect_full" "$live_full" 2>/dev/null; then
    echo "MATCH_AHEAD live=$live handoff=$expect (STG includes handoff commit)"
    return 0
  fi
  if git -C "$repo" merge-base --is-ancestor "$live_full" "$expect_full" 2>/dev/null; then
    echo "MISMATCH_BEHIND live=$live handoff=$expect (STG lags handoff — not deployed yet)"
    return 2
  fi
  return 1
}

compare_gate() {
  local live="$1" expect="$2"
  local b e
  b="$(norm_sha "$live")"
  e="$(norm_sha "$expect")"

  if [[ "$b" == "$e"* || "$e" == "$b"* ]]; then
    echo "MATCH live=$live handoff=$expect"
    return 0
  fi

  if ancestor_gate "$live" "$expect"; then
    return 0
  fi
  local anc_rc=$?
  if [[ $anc_rc -eq 2 ]]; then
    return 2
  fi

  echo "MISMATCH live=$live handoff=$expect"
  return 2
}

if [[ -n "$OFFLINE_LIVE" ]]; then
  BUILD="$OFFLINE_LIVE"
elif [[ -z "$EXPECT" ]]; then
  [[ -n "${STG_URL:-}" ]] || { echo "STG_URL not set in $ENVF — cannot read live STG buildId" >&2; exit 3; }
  URL="${STG_URL%/}${STG_HEALTH_PATH:-/api/health}"
  JSON="$(curl -fsS -m 15 "$URL" 2>/dev/null)" || { echo "STG health unreachable: $URL" >&2; exit 4; }
  BUILD="$(printf '%s' "$JSON" | sed -nE 's/.*"buildId"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p')"
  [[ -n "$BUILD" ]] || { echo "no buildId in STG health response" >&2; exit 4; }
  echo "$BUILD"
  exit 0
else
  [[ -n "${STG_URL:-}" ]] || { echo "STG_URL not set in $ENVF — cannot run STG buildId gate" >&2; exit 3; }
  URL="${STG_URL%/}${STG_HEALTH_PATH:-/api/health}"
  JSON="$(curl -fsS -m 15 "$URL" 2>/dev/null)" || { echo "STG health unreachable: $URL" >&2; exit 4; }
  BUILD="$(printf '%s' "$JSON" | sed -nE 's/.*"buildId"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p')"
  [[ -n "$BUILD" ]] || { echo "no buildId in STG health response" >&2; exit 4; }
fi

compare_gate "$BUILD" "$EXPECT"
exit $?
