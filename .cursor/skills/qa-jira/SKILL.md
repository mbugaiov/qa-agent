---
name: qa-jira
description: Per-project tracker integration for the QA Agent (Jira or GitHub Issues) — isolation, filing bugs via create_bug_issue.py, recordings/evidence, and L5 unattended Validate/Testing→Done (auto-accept, auto-file confirmed bugs, auto-reopen; needs-human is the only stop). Use before any tracker create/close/return/comment/recording.
---

# Tracker integration (Jira or GitHub Issues)

**Strict per-project isolation.** Each project's tracker credentials live ONLY in its own
`projects/<slug>/.secrets/` (`jira.env` and/or `github.env` + `project.yaml` tracker block).
No shared/global config; ambient env ignored.

**Route filing through `create_bug_issue.py`** — it selects `create_jira_issue.py` or
`github_create_issue.py` from `tracker.provider`.

**GitHub credentials:** `projects/<slug>/.secrets/github.env` (`GITHUB_TOKEN` / `GH_TOKEN`).
When set, `github_create_issue.py` strips ambient `GH_TOKEN`/`GITHUB_TOKEN` for its
subprocesses and uses the project token — required for `--attach` (secret gist upload).
Without a project token, issue create may still use the local `gh` login, but `--attach`
upload is refused (isolation). Copy `github.env.example` → `github.env`.

**Jira gate:** if `scripts/jira_status.sh <slug>` is `inactive` and the project is Jira-backed,
**skip ALL Jira work** — local QA + `run.md` only. `create_jira_issue.py` no-ops when unconfigured.

**GitHub gate:** if `tracker.provider: github_issues` but owner/repo/`gh` missing, GitHub scripts
no-op or exit inactive (same offline-safe contract as `github_scope.py`).

`projects/<slug>/.secrets/jira.env` (copy from `jira.env.example`):

```
JIRA_BASE_URL=https://<company>.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=<atlassian api token>
JIRA_PROJECT_KEY=ABC
JIRA_ISSUE_TYPE=Bug
JIRA_EPIC_FOR_TASKS_BUGS=https://<company>.atlassian.net/browse/ABC-123   # optional epic parent
```

**Onboarding (once):** fill the connection block, then `python3 scripts/jira_discover.py <slug>` to print
`JIRA_ASSIGNEE_ACCOUNT_ID`, `JIRA_BOARD_ID`, `JIRA_SPRINT_FIELD`, story-point field + the board's estimation
field; paste them into `.secrets/jira.env`.

## Description format (Markdown → Jira ADF)

`create_jira_issue.py` converts **Markdown** to Jira ADF so headings, lists, bold,
links, and fenced **Gherkin** blocks render correctly. Use `templates/jira-task.md`
for factory/dev **Task** tickets (business context + Requirement + OpenSpec + scenarios).

Structure for tasks:

1. **Business context** — why (epic, STG factory, On Hold items)
2. **Requirement** — As a / I need / So that
3. **OpenSpec change** — change id, capability, spec paths, validate/archive commands
4. **Scenarios** — ` ```gherkin ` Given/When/Then blocks (one per acceptance scenario)
5. **Implementation approach** — numbered steps + primary file paths
6. **Acceptance criteria** — bullet checklist (includes OpenSpec test gate + STG buildId)
7. **Out of scope** / **Dependencies**

Preview before filing: `--dry-run`. Legacy plain-text lines: `--plain-description`.

## Factory ticket ownership (optional — label-driven factories)

If the project uses factory engineering tickets, label them **`impl-dev`** or **`impl-qa`**:

| Loop | Picks | Skips |
|------|-------|-------|
| **Dev factory loop** | `labels = impl-dev AND status = "To Do"` | `impl-qa`, `deferred`, On Hold |
| **QA factory loop** | `labels = impl-qa AND status = "To Do"` | `impl-dev`, `deferred`, On Hold |
| **QA retest loop** | `Validate/Testing`, `In Progress` (features dev shipped) | impl-* factory tickets in To Do only |

**Ownership at verdict time (gate enforced):**

| Ticket | Verdict when still In Progress |
|--------|--------------------------------|
| **`impl-qa`** | **Marathon → Done** only at charter end; dev scope frozen until then |
| **`impl-dev` / feature fix** | **`SKIP_DEV`** only when passive monitor |
| **`Validate/Testing`** | **`DONE` \| `FAIL` \| `RETURN_DEV`** — never SKIP_DEV |

## Evidence package (MUST — gate enforced)

**No Jira ticket is filed, reopened, or moved to Done without attached artifacts and spec authority.**

### Before any test or filing
1. **`openspec_read.sh <slug> --ticket <KEY>`** (or `--cap` / `--grep`) — read governing **REQ** + **Scenario** WHEN/THEN.
2. **`ticket_tc.sh`** — persist steps in `test-cases/TC-<KEY>.md`; execution must match persisted TC + OpenSpec oracle.
3. Log **`openspec_read=true`**, **`openspec_req=REQ-…`**, **`openspec_scenario=…`** in `dod_check` or bug description.

### When filing a bug (`create_bug_issue.py` → Jira or GitHub)

**All required before the issue is considered filed:**

| # | Artifact | How |
|---|----------|-----|
| 1 | **Exact steps** | Numbered in `templates/bug-report.md` — same steps as recording |
| 2 | **Expected vs actual** | **Quote OpenSpec THEN** (or REQ from traceability matrix / `manual-test-plan.md`) |
| 3 | **Screenshot** | Error state PNG → `--attach` (repeatable for multiple) |
| 4 | **E2E recording** | After create: `record_and_attach.sh <slug> <NEW-KEY> …` (Jira or GitHub — auto-routes) |
| 5 | **Build / env** | STG buildId, role, URL in description |
| 6 | **Factory log** | `bug_filed=<KEY>` + `bug_recording_attached=true` + `bug_screenshot_attached=true` in `dod_check` |

**Forbidden:** filing with description-only; markdown-only evidence; curl output without screenshot+recording; steps that don't match OpenSpec oracle; on GitHub factories, returning the feature ticket without a separate `confirmed-defect` bug when the failure is a product defect.

### When moving a ticket to Done
- **`record_and_attach.sh`** on the **feature/impl-qa ticket** (≤10MB E2E of customer journey proving acceptance).
- Steps in recording must match **OpenSpec scenarios** exercised + persisted TC.
- Log `recording_attached=true`, `two_pass=true`, `canonical_source=true` in `dod_check`.

### When reopening a regression
- `reopen_regression.py --attach <screenshot>` **and** attach recording via `record_and_attach.sh` on the reopened key.
- Comment must cite **OpenSpec expected** vs **actual** on current STG buildId.

## Filing a bug

```
# 1. Read spec authority
./scripts/openspec_read.sh <slug> --ticket <FEATURE-KEY>

# 2. Write templates/bug-report.md (OpenSpec REQ/Scenario + exact steps)

# 3. Create with screenshot(s) — tracker-aware router
python3 scripts/create_bug_issue.py --project projects/<slug> \
  --summary "PF-XX: <one line>" --description-file <run>/bug-report.md \
  --severity S2 --labels <slug>,confirmed-defect \
  --attach <run>/screenshots/BUG-001-fail.png \
  --related-key <FEATURE-KEY>

# Equivalent direct scripts:
#   create_jira_issue.py     (tracker.provider jira)
#   github_create_issue.py   (tracker.provider github_issues) — dedupe on by default

# 4. Recording on the NEW bug key (MUST) — tracker-aware
scripts/record_and_attach.sh <slug> <NEW-KEY> <steps.json> "Repro: …"

# 5. Ledger
./scripts/factory_log.sh <slug> <FEATURE-KEY> dod_check … bug_filed=<NEW-KEY> \
  bug_recording_attached=true bug_screenshot_attached=true openspec_read=true openspec_req=REQ-…
```

## Filing a task (L5 / factory / dev work)

Copy `templates/jira-task.md`, fill placeholders, then:

```
python3 scripts/create_jira_issue.py --project projects/<slug> \
  --issue-type Task \
  --summary "[<PRODUCT>] <one line>" \
  --description-file path/to/ticket.md \
  --points 5 --estimate 8h --labels <slug>,factory \
  --dry-run
```

Auto-set on creation (per `.secrets/jira.env`): **assignee** (`JIRA_ASSIGNEE_ACCOUNT_ID`); **story points**
(severity default S1=5/S2=3/S3=2/S4=1) on `JIRA_STORYPOINTS_FIELD` (+ optional `JIRA_STORYPOINTS_FIELD_ALT`);
**original time estimate** (severity default S1=8h/S2=4h/S3=2h/S4=1h via `timetracking.originalEstimate`);
**active sprint** (from `JIRA_BOARD_ID`); **epic parent**. Discover field ids via `jira_discover.py`. Opt out: `--no-assignee` / `--no-sprint`.

## Retest recording evidence (ALWAYS — FE and BE/infra)

Attach a short **E2E recording** to **every** ticket you move to Done (and to every confirmed bug),
compressed to **≤10MB**, via tracker-aware `record_and_attach.sh` (Jira attachment or GitHub secret gist):

```
scripts/record_and_attach.sh <slug> <KEY> <stepsJson> "<caption>"
```

The clip MUST show the **customer-side end-to-end steps** that validate the fix/feature works now — a real
user journey in the live browser, not just a static page. Build the steps JSON accordingly (login → navigate →
perform the user action → show the expected outcome). Records via Playwright (`record_retest.cjs`), compresses
with ffmpeg, attaches, deletes the local copy. Keep clips short but complete (show the actual outcome).

- **FE tickets:** record the user flow exercising the changed UI and its result.
- **BE / API / CI / infra tickets:** there is still a customer outcome — record the end-to-end **user journey that
  depends on the backend path** (e.g. a request lifecycle that exercises a DB/adapter change), or, when there is
  truly no UI, capture the customer-observable proof end-to-end (API response in the browser/devtools, the health
  page, the protected action being allowed/denied). The caption must name the customer outcome being validated.
- Curl/unit-test/config-review output is **supporting** evidence — it does **not** replace the recording.
- No recording ⇒ the ticket is **not** Done.
- **Exception — pure-CI / pipeline-only tickets** (no app/customer surface, e.g. deploy gating, pipeline steps):
  **no evidence required** — neither a recording nor a pipeline-run log. Verify the change at config/logic level,
  note it briefly in the Jira comment, and PASS→Done.

## Validation workflow (QA scope) — L5 unattended

- `Validate/Testing` = QA queue. Retest → PASS → **auto-Done** when DoD met. **Only two terminal outcomes for V/T:** **Done** (all passed) or **In Progress** (blocker/dev fix). **Never leave a ticket in Validate/Testing while blocked.**
- **Locator / automation blockers:** try alternate locators and native-click paths first. If still blocked → file separate dev ticket (impl-dev: add testids/locators) or product bug → `jira_return_in_progress.py` → log `dod_check verdict=RETURN_DEV`.
- `In Progress` = also in QA scope; re-check each tick, never drop until Done/Closed.
  - **`impl-qa` In Progress:** **`SKIP_DEV` forbidden**. Slice mode → **`QA_CONTINUE`** (charter slice + artifact); marathon (`marathon_start`) → work until **`DONE`** (gate reads `handoff_read.labels`).
  - **Dev-owned In Progress:** **`SKIP_DEV` only when passive monitor** — `jira_handoff.sh --log` status `In Progress`, no work started this tick; never when handoff says **Validate/Testing**.
- **Multi-ticket ticks (mandatory):** each loop tick runs the scope JQL and must attempt **full machine DoD on every row returned** before the tick ends. Never close one ticket and defer siblings to the next wake. A dev handoff that moves a previously Done ticket back to `Validate/Testing` (new merge SHA) puts it back in scope — retest it in the same tick if other scope tickets are also open.
- Active/QA-retest scope JQL: `parent = <EPIC-KEY> AND statusCategory != Done AND status not in ("To Do","On Hold")`.
- QA *implementation* (impl-qa) scope JQL: `parent = <EPIC-KEY> AND labels = impl-qa AND status = "To Do"`.
- **Same-tick completion:** autotake `impl-qa` To Do → **In Progress** only when starting a **marathon** (work until Done) or finishing a subtask same session — never **`SKIP_DEV`**. **Marathon:** no `tick_end`/re-arm until **Done**; dev scope **waits**.

### Machine DoD for auto-Done (all must hold)
1. Two-pass retest **PASS** against the **canonical source** (detail page / DB / API), not a weaker proxy.
2. **STG buildId gate**: `scripts/stg_buildid.sh <slug> <handoff-sha>` returns **MATCH** or **MATCH_AHEAD** — live STG
   `/api/health` buildId equals the handoff commit, or is **ahead** of it on the same branch (handoff SHA is a git
   ancestor of live STG; requires `SERVER_GIT_WORKTREE` or `SERVER_GIT_SRC_REPO` in `server.env`). **MISMATCH** or
   **MISMATCH_BEHIND** ⇒ do NOT Done; comment expected-vs-actual. (Skip only when the project has no `STG_URL`.)
3. Mandatory **E2E recording** attached (pure-CI/pipeline tickets exempt).
4. Verdict is not `needs-human` (ambiguous requirement / policy uncertainty / destructive → leave open, surface to user).
5. **Verdict review** (skill `qa-verdict-review`): write `verdict-review-<KEY>.md` → `check_verdict_review.sh` →
   ledger `verdict_review=pass` **before** `jira_close_issue.py` / `github_close_issue.py`. Those scripts **exit 4**
   without the ledger pass (`--allow-missing-verdict-review` escape hatch only).

Log a terminal `dod_check` per scope ticket and pass `factory_tick_gate.sh` before `tick_end` (skill `qa-loop`, `factory/schema.md`). **Forbidden at tick_end:** `PARTIAL`, `DEFERRED`, `BLOCKED`, comments-only “PASS (recording pending)”. V/T tickets with blockers must use `RETURN_DEV` or `FAIL` **and** transition to In Progress same tick.

### Auto-file & auto-reopen (unattended, default ON)
- **Confirmed defect** (evidence + `confirmed-defect` verdict) → file immediately with `create_bug_issue.py`
  (no ask-first). **Always pass `--labels <slug>,confirmed-defect`** — the script auto-adds **`impl-dev`** so the
  dev factory loop can autotake. **Dedupe first** (Jira JQL / GitHub open title match — `github_create_issue.py`
  dedupes by default). Use `--related-key` on GitHub to comment the feature ticket. NEVER auto-file
  `works-as-specified`/`cannot-reproduce`/`needs-human`.
- **Regression** (a Done ticket FAILS retest) → `scripts/reopen_regression.py --project projects/<slug> --key <ISSUE-KEY> --reason "…" [--attach …]` moves it to In Progress with a REGRESSION comment + evidence.

## Rules

- Write the returned **Jira key + URL back into the run's `bug-report.md`** (BUG-XXX ↔ ISSUE-KEY). Dedupe on re-runs.
- Severity → label `severity-s{1..4}` always; priority only with `--priority`/`--set-priority`.
- The only stop condition for unattended action is `needs-human`; otherwise act (Done/file/reopen) without asking.
