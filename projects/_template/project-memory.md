# Project Memory — <Project Name>

> Persistent context for this site across runs. Read at the start of every engagement;
> update at the end. Keep it factual and short.

## App profile
- **URL(s)**: <staging / prod / local QA port>
- **Stack hints**: <framework, auth mechanism, notable libraries>
- **Roles / personas**: <guest / user / admin and what each can do>
- **Browser MCP**: <which MCP this project uses — e.g. cursor-ide-browser, user-playwright>

## Quirks & gotchas (learned)
- <e.g. login form does not fire validation until blur — use real typing in Pass 1>
- <e.g. MCP click may not fire React server actions — use native DOM `.click()` via evaluate>
- <e.g. long-lived browser sessions can wedge — reset with browser_close + fresh navigate>

## Known bugs (carry-over)
| Bug | Severity | Status | First seen | Notes |
|-----|----------|--------|-----------|-------|
| BUG-001 | S2 | Open | <date> | <one line> |

## Requirements baseline
- **Source**: <docx/jira link>  ·  **Last synced**: <date>
- **REQ count**: <n>

## Active loop (optional — continuous QA only)
- **Current run:** `runs/<YYYY-MM-DD>-exploratory-<task>/` (or `none`)
- **Cadence:** <e.g. 60m when scope empty>
- **Scope JQL:** `parent = <EPIC-KEY> AND status in ("In Progress", "Validate/Testing")` (adjust per project)
- **On Hold / skip:** <ticket keys or status exclusions>
- **Last known scope:** <empty | list keys>

## Coverage ledger (rotate exploratory each tick)
- ✅ Covered: <areas already tested>
- ⬜ Not yet / shallow: <areas to probe next>
- 🔒 Security slices run: <headers, RBAC, XSS, rate-limit, …> — see `templates/security-checklist.md`

## Run history
| Date | Type | Scope | Bugs | Verdict |
|------|------|-------|------|---------|
| <date> | <type> | <scope summary> | <n> | <PASS/GO/…> |

## Open ops / residual risks
- <e.g. STG can lag main — use stg_buildid gate before auto-Done>
- <e.g. credentials or env not available for full path>

## L5 unattended (optional — if enabled for this project)
- Auto-accept Validate/Testing → Done when machine DoD met (see skill `qa-jira`).
- Auto-file confirmed bugs; auto-reopen regressions. Stop only on `needs-human` verdict.
- Requires `STG_URL` in `.secrets/server.env` when using the STG buildId gate.
