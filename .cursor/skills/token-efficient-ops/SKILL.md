---
name: token-efficient-ops
description: How the QA Agent performs every operation (Jira, Bitbucket, git, testing, browser, shell, file reads) with the least token/context cost. Prefer filtered/terse output over raw payloads. Use whenever you touch Jira/Bitbucket/git or run tests, and when choosing between REST-script vs CLI vs MCP.
---

# Token-efficient operations (playbook)

Principle: **filter at the source, print only what you'll use.** Ranking for any integration —
custom REST wrapper (leanest) > CLI with terse flags > MCP (chattiest). Reach for MCP last.

## Jira (REST via `scripts/*`)
- Scope check: one `requests` call with `fields=status,summary`, print `KEY | status | summary` per row. Nothing else.
- Reads: request only the fields you need (`params={'fields':'status,summary'}`); never fetch the whole issue.
- Descriptions/comments are ADF — flatten to text and slice (`[:N]`); don't dump the ADF tree or full threads.
- Writes (comment/transition/attach): print a **one-line** result (`comment 201 | ->Done 204`), not the response body.
- Dedup/search with JQL that returns keys only.
- Wrappers to reuse: `create_jira_issue.py`, `reopen_regression.py`, `jira_discover.py`, `jira_status.sh`.

## Bitbucket & MCP
- Prefer **local git** for diffs/commits/file contents (see below) — no API payload in context.
- Bitbucket MCP (`bb_get`) or any MCP: MANDATORY `jq` filter + `pagelen`; fetch one item with `pagelen:1` only to learn the schema, then always filter. Never call an MCP unfiltered.
- Don't read MCP tool descriptors you already know.

## git (local, cheap)
- `git -C <repo> …` instead of `cd`. Use `--oneline`, `-s`/`--short`, `--name-only`, `--format=%h %s`.
- Inspect a file at a commit without checkout: `git show <sha>:<path>` (slice with `sed -n`/`head`).
- Diffs: `git show <sha> -- <path> | sed -n '/@@/,$p' | head -N`; `git diff --name-only A B`.
- Fetch quietly: `git fetch -q`. Compare vs remote: `git rev-list --left-right --count origin/main...HEAD`.

## Testing / browser — cheapest control first
**Default to the Playwright CLI for EVERYTHING possible. The Playwright MCP is the LAST RESORT** — use it only
when a live, visible browser is genuinely required (exploratory / two-pass manual QA on an unknown page) AND the
CLI/specs cannot do it. If a spec can express the check, write/run the spec instead of driving the MCP.
Ranking (cheapest → most tokens): **Playwright `test` CLI (terse reporter) > `playwright screenshot`/node lib > Playwright MCP.**
- **Repeatable checks/regression/acceptance → Playwright specs via the CLI, NOT the MCP.** Run the app's suite
  (`npm run test:e2e`) or a targeted case and read only the summary:
  `./node_modules/.bin/playwright test tests/e2e/<file>.spec.ts -g "<case>" --reporter=dot 2>&1 | tail -5`
  (`--reporter=dot` = ~1 char/test; `line`/`list` are more verbose). `--last-failed` re-runs only failures.
  Specs also cover what the MCP CAN'T drive (e.g. dnd-kit board drag → `boardDnd.spec.ts`).
- **One-off capture without interaction:** `./node_modules/.bin/playwright screenshot <url> <file>` (no snapshots in context).
- **Recordings:** node + Playwright lib via `record_and_attach.sh` (≤10MB, local copy discarded).
- **Playwright MCP = LAST RESORT** — only when a live/visible browser is required and no CLI/spec path works
  (unknown-page exploratory, the mandatory visible two-pass). Even then: return **compact values** with
  `browser_evaluate` (booleans/counts/short strings); take a full `browser_snapshot` ONLY when you need element
  refs; `browser_console_messages(onlyErrors:true)`. If you find yourself repeating MCP actions, convert to a spec.
- Non-UI checks → `curl`: status (`-o /dev/null -w '%{http_code}'`), headers (`-D-` + `grep`), `/api/health`, auth matrices, JSON (`| jq`/`grep`).
- Engine self-tests: `bash tests/run_tests.sh 2>&1 | tail -6`, not the whole log.

## Shell / file reads
- One chained command for related checks; cap output (`| tail -N`, `| head -N`, `grep -m N`, `--silent`, `-q`).
- Big output auto-streams to the terminal file — do a single smoke check, don't echo it back.
- Find/search with Grep/Glob (ripgrep), `head_limit`; read **ranges** of large files, never `cat` them wholesale.
- Reuse values already in context (merge sha, prior read) instead of re-fetching.

## Quick decision
- Need Jira data → `scripts/*` REST (fielded) → else ACLI terse → else MCP (filtered).
- Need repo data → local `git` → else Bitbucket API (fielded) → else MCP (filtered).
- Need to verify behavior → `curl`/`browser_evaluate` compact value → else targeted snapshot → else full page.
