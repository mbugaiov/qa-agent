---
name: qa-jira
description: Per-project Jira integration for the QA Agent — strict isolation, the active/inactive gate, onboarding (jira_discover), filing bugs with assignee/story-points/estimate/sprint/epic, attaching ≤10MB retest recordings, and the L5 UNATTENDED Validate/Testing→Done workflow (auto-accept with STG buildId gate, auto-file confirmed bugs, auto-reopen regressions; needs-human is the only stop). Use before any Jira action (file/transition/comment/recording/reopen).
---

# Jira integration (per-project, optional)

**Strict per-project isolation.** Each project's Jira connection + field ids live ONLY in its own
`projects/<slug>/.secrets/jira.env`. No shared/global config; scripts read the project's file exclusively
(ambient env ignored) — project A can never pull project B's settings. A without Jira details runs Jira-free.

**Gate first — no Jira details ⇒ do nothing with Jira.** Before any Jira action run
`scripts/jira_status.sh <slug>`. If `inactive` (no `.secrets/jira.env`, or placeholder fields), **skip ALL
Jira work** — just local QA + `run.md`. `create_jira_issue.py` is itself a no-op (not an error) when unconfigured.

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
| **QA retest loop** | `Validate/Testing`, `In Progress` (features dev shipped) | impl-* factory tickets |

**CR agent** never picks Jira tickets — it reviews PRs inside the dev loop only. Each ticket description may include **Implementing agent** — read it before any work.

## Filing a bug

```
python3 scripts/create_jira_issue.py --project projects/<slug> \
  --summary "BUG-XXX: <one line>" --description-file <run>/bug-report.md \
  --severity S2 --labels <slug>,confirmed-defect --attach <run>/screenshots/BUG-XXX.png   # repeatable
  # confirmed-defect → script also adds impl-dev (dev factory autotake). --dry-run to preview.
  # --no-impl-dev only for rare exceptions (e.g. human-triaged-only noise).
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
stored **only in Jira**, compressed to **≤10MB**:

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
- `In Progress` = also in QA scope; re-check each tick, never drop until Done/Closed. `SKIP_DEV` dod_check only when `jira_status=In Progress` (not V/T).
- **Multi-ticket ticks (mandatory):** each loop tick runs the scope JQL and must attempt **full machine DoD on every row returned** before the tick ends. Never close one ticket and defer siblings to the next wake. A dev handoff that moves a previously Done ticket back to `Validate/Testing` (new merge SHA) puts it back in scope — retest it in the same tick if other scope tickets are also open.
- Active/QA-retest scope JQL: `parent = <EPIC-KEY> AND statusCategory != Done AND status not in ("To Do","On Hold")`.
- QA *implementation* (impl-qa) scope JQL: `parent = <EPIC-KEY> AND labels = impl-qa AND status = "To Do"`.

### Machine DoD for auto-Done (all must hold)
1. Two-pass retest **PASS** against the **canonical source** (detail page / DB / API), not a weaker proxy.
2. **STG buildId gate**: `scripts/stg_buildid.sh <slug> <handoff-sha>` returns **MATCH** or **MATCH_AHEAD** — live STG
   `/api/health` buildId equals the handoff commit, or is **ahead** of it on the same branch (handoff SHA is a git
   ancestor of live STG; requires `SERVER_GIT_WORKTREE` or `SERVER_GIT_SRC_REPO` in `server.env`). **MISMATCH** or
   **MISMATCH_BEHIND** ⇒ do NOT Done; comment expected-vs-actual. (Skip only when the project has no `STG_URL`.)
3. Mandatory **E2E recording** attached (pure-CI/pipeline tickets exempt).
4. Verdict is not `needs-human` (ambiguous requirement / policy uncertainty / destructive → leave open, surface to user).

Log a terminal `dod_check` per scope ticket and pass `factory_tick_gate.sh` before `tick_end` (skill `qa-loop`, `factory/schema.md`). **Forbidden at tick_end:** `PARTIAL`, `DEFERRED`, `BLOCKED`, comments-only “PASS (recording pending)”. V/T tickets with blockers must use `RETURN_DEV` or `FAIL` **and** transition to In Progress same tick.

### Auto-file & auto-reopen (unattended, default ON)
- **Confirmed defect** (evidence + `confirmed-defect` verdict) → file immediately with `create_jira_issue.py`
  (no ask-first). **Always pass `--labels <slug>,confirmed-defect`** — the script auto-adds **`impl-dev`** so the
  dev factory loop can autotake (`labels = impl-dev AND status = "To Do"`). **Dedupe via JQL first** (search open
  issues under the epic with the same summary); use `--dry-run` for an audit preview only. NEVER auto-file
  `works-as-specified`/`cannot-reproduce`/`needs-human`.
- **Regression** (a Done ticket FAILS retest) → `scripts/reopen_regression.py --project projects/<slug> --key <ISSUE-KEY> --reason "…" [--attach …]` moves it to In Progress with a REGRESSION comment + evidence.

## Rules

- Write the returned **Jira key + URL back into the run's `bug-report.md`** (BUG-XXX ↔ ISSUE-KEY). Dedupe on re-runs.
- Severity → label `severity-s{1..4}` always; priority only with `--priority`/`--set-priority`.
- The only stop condition for unattended action is `needs-human`; otherwise act (Done/file/reopen) without asking.
