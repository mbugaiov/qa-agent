#!/usr/bin/env bash
# Start/stop the app-under-test for a project. The agent brings the server up for
# testing and stops it after — but ONLY ever stops a server IT started (tracked via
# a pidfile). An already-running (external/user) server is left untouched.
#
# Config: projects/<slug>/.secrets/server.env (gitignored), KEY=VALUE:
#   SERVER_URL=http://localhost:3000        # health-check URL
#   SERVER_CWD=/abs/path/to/app             # where to run the start command
#   SERVER_START=npm run dev                # start command
#   SERVER_READY_TIMEOUT=90                 # seconds to wait for readiness
#
# Optional — test against a branch in an ISOLATED checkout (never touches the dev's
# working dir). When SERVER_GIT_SYNC is set, `up`/`sync` create/refresh a dedicated
# git worktree at origin/<branch>, copy in the runtime env, and bootstrap it:
#   SERVER_GIT_SYNC=main                            # branch to test (enables sync mode)
#   SERVER_GIT_SRC_REPO=/abs/path/to/dev/repo       # repo to fetch from + base the worktree on
#   SERVER_GIT_WORKTREE=/abs/path/to/qa/checkout    # dedicated QA worktree (ours; set SERVER_CWD to it)
#   SERVER_ENV_SRC=/abs/.env                        # optional: copied into the worktree before bootstrap
#   SERVER_BOOTSTRAP="npm install && ..."           # optional: run in the worktree on every sync
#
# Usage:
#   scripts/server_ctl.sh <slug> status  # report up/down + who owns it
#   scripts/server_ctl.sh <slug> sync    # (sync mode) refresh the isolated worktree to origin/<branch>
#   scripts/server_ctl.sh <slug> up      # sync (if configured) + start if not already up; wait until ready
#   scripts/server_ctl.sh <slug> down    # stop ONLY if we started it (pidfile present)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="${1:-}"; ACTION="${2:-}"
[[ -z "$SLUG" || -z "$ACTION" ]] && { echo "Usage: server_ctl.sh <slug> status|sync|up|down" >&2; exit 1; }

PDIR="$ROOT/projects/$SLUG"
ENVF="$PDIR/.secrets/server.env"
PIDF="$PDIR/.secrets/server.pid"
LOGF="$PDIR/.secrets/server.log"
[[ -d "$PDIR" ]] || { echo "No such project: projects/$SLUG" >&2; exit 1; }
[[ -f "$ENVF" ]] || { echo "Missing $ENVF (copy server.env.example, fill SERVER_CWD/SERVER_START)." >&2; exit 1; }

# shellcheck disable=SC1090
set -a; . "$ENVF"; set +a
URL="${SERVER_URL:-http://localhost:3000}"
TIMEOUT="${SERVER_READY_TIMEOUT:-90}"

is_up() { curl -sS -m 4 -o /dev/null "$URL" 2>/dev/null; }

# Refresh an isolated QA checkout to origin/<branch>. No-op unless SERVER_GIT_SYNC is set.
# Never touches SERVER_GIT_SRC_REPO's working tree — only fetches and drives a separate worktree.
do_sync() {
  [[ -n "${SERVER_GIT_SYNC:-}" ]] || return 0
  local br="$SERVER_GIT_SYNC" src="${SERVER_GIT_SRC_REPO:-}" wt="${SERVER_GIT_WORKTREE:-}"
  [[ -n "$src" && -n "$wt" ]] || { echo "sync mode needs SERVER_GIT_SRC_REPO and SERVER_GIT_WORKTREE" >&2; return 1; }
  [[ -d "$src/.git" || -f "$src/.git" ]] || { echo "SERVER_GIT_SRC_REPO is not a git repo: $src" >&2; return 1; }
  echo "git sync: $src @ origin/$br -> worktree $wt"
  git -C "$src" fetch origin --prune --quiet || { echo "fetch failed" >&2; return 1; }
  git -C "$src" rev-parse --verify --quiet "origin/$br" >/dev/null || { echo "origin/$br not found" >&2; return 1; }
  if git -C "$src" worktree list --porcelain | grep -qF "worktree $wt"; then
    git -C "$wt" reset --hard "origin/$br" --quiet || return 1
  else
    mkdir -p "$(dirname "$wt")"
    git -C "$src" worktree add --force --detach "$wt" "origin/$br" || return 1
  fi
  echo "worktree HEAD: $(git -C "$wt" log -1 --oneline 2>/dev/null)"
  if [[ -n "${SERVER_ENV_SRC:-}" ]]; then
    [[ -f "$SERVER_ENV_SRC" ]] && { cp "$SERVER_ENV_SRC" "$wt/.env"; echo "copied env -> $wt/.env"; } || echo "WARN: SERVER_ENV_SRC missing: $SERVER_ENV_SRC" >&2
  fi
  if [[ -n "${SERVER_BOOTSTRAP:-}" ]]; then
    echo "bootstrap (in $wt)..."
    ( cd "$wt" && eval "$SERVER_BOOTSTRAP" ) || { echo "bootstrap failed" >&2; return 1; }
  fi
  return 0
}

case "$ACTION" in
  status)
    if is_up; then
      if [[ -f "$PIDF" ]] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "UP (started by agent, pid $(cat "$PIDF"))"; else echo "UP (external — not started by agent)"; fi
    else echo "DOWN"; fi
    ;;
  sync)
    [[ -n "${SERVER_GIT_SYNC:-}" ]] || { echo "not in git-sync mode (SERVER_GIT_SYNC unset) — nothing to sync"; exit 0; }
    do_sync
    ;;
  up)
    if is_up; then echo "already UP — leaving as-is (external or prior agent start)"; exit 0; fi
    do_sync || { echo "ERROR: git sync failed — not starting" >&2; exit 1; }
    [[ -n "${SERVER_CWD:-}" && -n "${SERVER_START:-}" ]] || { echo "SERVER_CWD/SERVER_START not set in $ENVF" >&2; exit 1; }
    echo "starting: ($SERVER_CWD) $SERVER_START"
    ( cd "$SERVER_CWD" && nohup bash -lc "$SERVER_START" >"$LOGF" 2>&1 & echo $! >"$PIDF" )
    for ((i=0; i<TIMEOUT; i++)); do is_up && { echo "UP after ${i}s (pid $(cat "$PIDF"))"; exit 0; }; sleep 1; done
    echo "ERROR: not ready after ${TIMEOUT}s — see $LOGF" >&2; exit 1
    ;;
  down)
    if [[ -f "$PIDF" ]]; then
      pid="$(cat "$PIDF")"
      # kill the process group we started (dev servers spawn children)
      kill "$pid" 2>/dev/null; pkill -P "$pid" 2>/dev/null
      sleep 1; kill -9 "$pid" 2>/dev/null
      rm -f "$PIDF"
      echo "stopped agent-started server (was pid $pid)"
    else
      echo "no agent pidfile — server not started by us; leaving it running"
    fi
    ;;
  *) echo "Unknown action: $ACTION" >&2; exit 1;;
esac
