---
name: qa-server
description: How the QA Agent starts/stops the app under test for a project (autostart/autostop, only stopping a server it started itself). Use before testing when the app may be down, and to shut it down after. Config in projects/<slug>/.secrets/server.env via scripts/server_ctl.sh.
---

# Managing the app under test (autostart / autostop)

The agent **brings the server up for testing and stops it afterwards** — but it **only ever stops a
server it started itself**. A server already running (started by the user / externally) is left untouched.

Per-project config in `projects/<slug>/.secrets/server.env` (gitignored, copy from `server.env.example`):

```
SERVER_URL=http://localhost:3000     # health-check URL
SERVER_CWD=/abs/path/to/app/repo     # where to run the start command
SERVER_START="npm run dev"           # start command (quote if it has spaces)
SERVER_READY_TIMEOUT=90
```

Helper (tracks ownership via `.secrets/server.pid`):

```
scripts/server_ctl.sh <slug> status   # UP (agent) | UP (external) | DOWN
scripts/server_ctl.sh <slug> sync     # (sync mode) refresh the isolated worktree to origin/<branch>
scripts/server_ctl.sh <slug> up       # sync (if configured) + start if DOWN, wait until ready; no-op if already UP
scripts/server_ctl.sh <slug> down     # stop ONLY if WE started it; else leave running
```

## Test against `main` in an ISOLATED checkout (never the dev's working dir)

The dev's working dir may sit on a feature branch and be behind `main`, with uncommitted work — testing
it would be wrong and risky. Instead, set `SERVER_GIT_SYNC` so the agent tests a dedicated **git worktree**
pinned to `origin/<branch>`. The dev's repo is only **fetched** from; its working tree is never touched.

```
SERVER_URL=http://localhost:3100                       # dedicated port — never collides with a dev server
SERVER_GIT_SYNC=main                                   # branch to test (enables sync mode)
SERVER_GIT_SRC_REPO=/abs/path/to/dev/repo              # repo to fetch from + base the worktree on
SERVER_GIT_WORKTREE=/abs/path/to/.qa-worktrees/<slug>-main   # our checkout
SERVER_ENV_SRC=/abs/path/to/dev/repo/.env             # gitignored runtime env copied into the worktree
SERVER_CWD=/abs/path/to/.qa-worktrees/<slug>-main     # run inside the worktree
SERVER_BOOTSTRAP="npm install ... && <build a fresh isolated test DB + seed>"   # runs on every sync
SERVER_START="... ./node_modules/.bin/<bin> -p 3100"  # use node_modules/.bin (bare `next`/`vite` aren't on PATH)
```

`sync` does: `git fetch` → create/refresh worktree at `origin/<branch>` (`reset --hard`) → copy `SERVER_ENV_SRC`
→ run `SERVER_BOOTSTRAP`. Use a **separate DB and build/dist dir** in the worktree so QA never clobbers the
dev's data/build (document the recipe in `projects/<slug>/project-memory.md` and `SERVER_BOOTSTRAP`).
Prefer plain `dev` over a special `e2e:server` script if the latter disables protections you need to test
(e.g. rate-limiting).

Rules:
- **Start of run/tick:** check `server_ctl <slug> status`. UP (external) → use as-is, do NOT stop later. DOWN → start it.
- **Sync before every tick (mandatory when `SERVER_GIT_SYNC` is set):** run `server_ctl <slug> sync` at the
  start of each QA loop tick *before* `up` or browser work — even if the server is already UP (external).
  This guarantees retest/exploratory/automation hit the latest `origin/<branch>`, not a stale worktree.
- **Sync mode (testing a branch):** before starting, run `server_ctl <slug> sync` to refresh the isolated
  worktree to `origin/<branch>` and bootstrap it. Then start the server (background task) **from
  `SERVER_GIT_WORKTREE`** on `SERVER_URL`'s port. This guarantees you test the latest `main`, not a stale dir.
- **Starting under the Cursor agent harness:** a `nohup`/daemonized child is reaped when a foreground Shell
  call ends, so start the dev server as a **background Shell task** (`block_until_ms: 0`) whose command writes
  its own PID to `.secrets/server.pid`:
  `cd "$SERVER_CWD" && echo $$ > <proj>/.secrets/server.pid && exec <SERVER_START>`. Then poll `curl $SERVER_URL`
  until ready. (`server_ctl up`'s built-in nohup path is only for non-harness/CI use.)
  Use `./node_modules/.bin/<bin>` in `SERVER_START` — a bare `next`/`vite` is not on PATH outside an npm script.
- **End of run/tick:** `server_ctl <slug> down` — stops only if WE started it (pidfile present); else leaves it.
- Never `down` a server the agent didn't start. Never assume a path — `server.env` must be filled per project.
- A loop tick leaves the machine as it found it: if the agent started the server this tick, stop it before re-arming.
