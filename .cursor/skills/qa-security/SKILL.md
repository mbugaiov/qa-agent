---
name: qa-security
description: Live-app security testing for the QA Agent — pick and run a rotating checklist slice (headers, auth, RBAC/IDOR, rate-limit, input/XSS/SQLi, data exposure, debug paths) on exploratory and regression run cycles, capture evidence, file confirmed bugs via qa-jira, update project-memory. Use when starting or executing an exploratory or regression run, when the user asks for a security pass, or for full/UAT runs with security NFRs. Not on every loop tick. Not for static code review — use review-security for diff-based review.
---

# Security testing (live app)

**Checklist source:** `templates/security-checklist.md` (categories below).  
**Bug filing / recordings:** skill `qa-jira`. **Browser rules:** `.cursor/rules/qa-team.mdc` (two-pass when UI is involved).  
**Not this skill:** Cursor `review-security` = subagent on **code diffs** only.

## Active usage (when this skill runs)

| Trigger | Required? | What to run |
|---------|-----------|-------------|
| **`exploratory` run** (`new_run.sh … exploratory`) | **Yes** | ≥1 rotating slice per run; log in `run.md` + Security ledger |
| **`regression` run** (`new_run.sh … regression`) | **Yes** | ≥1 slice — align to changed areas or rotate oldest ✅ category for security regression |
| **Continuous loop tick** (`qa-loop`) | **No** | Jira retest + lightweight exploratory slice only — **do not** run security each tick |
| **User request** — "security pass", "security slice" | Yes | Named category or `next` from ledger |
| **`full` / `uat` run** | Yes — at least one slice | Cover gaps in Security ledger |
| **`targeted` / `smoke` run** | Only if scope touches auth, roles, input, APIs, or headers | Slice aligned to the change |

**Always read** `projects/<slug>/project-memory.md` → **Security ledger** before picking a slice.

### Run types we have (engine)

Both security cycles are first-class run types — see skill `qa-runs`:

```bash
scripts/new_run.sh <slug> exploratory "<charter or task>"
scripts/new_run.sh <slug> regression "<what to re-verify>"
```

| Type | Artifact | Security |
|------|----------|----------|
| `exploratory` | `exploratory-session.md` | **Required** — rotate categories across exploratory runs |
| `regression` | `execution-log.md` | **Required** — focus on areas affected by fixes or ledger gaps |

## Pick the next slice

Categories (rotate across **exploratory/regression runs** — not loop ticks):

1. `headers`
2. `authentication`
3. `authorization` (RBAC / IDOR / write-path authz)
4. `rate-limit`
5. `input-validation` (XSS, SQLi, oversize/malformed payloads)
6. `data-exposure` (errors, PII, debug/secret paths)

**Algorithm:**
1. Read ledger — note ✅ done, ⬜ shallow, **Next slice** pointer.
2. Pick the **lowest** category that is ⬜ or shallow; if all ✅, pick the **oldest** ✅ for regression.
3. Set **Next slice** to the following category for the next security cycle.
4. Log: `scripts/factory_log.sh <slug> _loop security_slice topic=<category>` (when factory ledger exists).

## Execute by category

**Dev-only caveats (always note in findings):** plain `http://localhost` — HSTS and `Secure` cookie flags are **n/a**, not failures. STG/https is authoritative for transport cookie flags.

### `headers` (no browser)
```bash
curl -sI "$BASE/" | head -20
curl -sI "$BASE/api/health"   # or project's health/API route
```
Check CSP, X-Frame-Options / frame-ancestors, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, X-Powered-By absent. Record raw headers in run log.

### `authentication`
- Wrong password + unknown user → same generic outcome (no enumeration).
- Protected routes → redirect/deny when logged out (list from `project-memory.md`).
- Session cookie: `HttpOnly`, `SameSite` (and `Secure` on https only).
- UI checks: **Pass 1** real typing + click; **Pass 2** MCP fill/click.

### `authorization`
- As **lowest** role: direct URL to admin/manager routes → deny/redirect.
- **IDOR:** user A must not read/mutate user B's resource by ID (requests, audit rows, etc.).
- **Write-path authz:** low role attempting manager-only mutation (server action/API) → rejected, not silent success.
- Use creds from `projects/<slug>/.secrets/credentials.json` only.

### `rate-limit`
- N rapid bad logins (document N, e.g. 10–20) → 429/throttle **or** document absence + file if policy expects limit.
- Valid login still works after burst (no good-user lockout).

### `input-validation`
- Stored XSS probe in a persistent text field (e.g. request objective) → escaped on display, no execution.
- Benign SQLi-style payload → no error leak / no data bleed.
- Oversize or malformed JSON to an API → 4xx, not 500 stack trace.

### `data-exposure`
- Provoke or observe errors → no stack traces, paths, or DB internals in response.
- Client bundle / API JSON → no secrets beyond need.
- Probe: `/.env`, `/.git/config`, `/api/debug` (and app-specific paths from memory) → 404/403.

## Verdicts and filing

| Outcome | Action |
|---------|--------|
| **Confirmed defect** | File under epic via `create_jira_issue.py` (dedupe JQL first); severity per `qa-team` scale; attach evidence |
| **Expected on localhost only** | Note in run log — do **not** file |
| **Policy gap / ambiguous** | `needs-human` — comment in run.md, do not auto-close tickets |
| **Pass** | One-line evidence (header snippet, status code, screenshot ref) in run log |

Security bugs use the same evidence bar as functional bugs — no filing without reproduction proof.

## Record results (every slice)

1. **`run.md`** — bullet: `Security slice: <category> — PASS | FAIL | n/a (localhost)` + evidence pointer.
2. **`project-memory.md` Security ledger** — update ✅/⬜ and **Next slice**.
3. **Optional artifact** — copy checklist into `<run>/security-<date>.md` with checked boxes.

### Security ledger format (`project-memory.md`)

```markdown
## Security ledger (skill `qa-security` — exploratory + regression runs)
- **Next slice:** authorization
- **Last run:** 2026-07-06 regression — rate-limit — PASS
| Category | Status | Notes |
|----------|--------|-------|
| headers | ✅ | STG curl 2026-06-28 |
| authentication | ✅ | session flags + guards |
| authorization | ⬜ shallow | read RBAC done; write-path authz not probed |
| rate-limit | ✅ | RQ-1593 |
| input-validation | ✅ | stored XSS |
| data-exposure | ✅ | debug paths |
```

## Standalone invocation

```
Run a security slice for projects/<slug> — category authorization (or "next" from ledger).
```

Or start a proper cycle:

```
scripts/new_run.sh <slug> exploratory "security — authorization write-paths"
```

Read `qa-server` if the app is down; stop server after if you started it.
