# Bug Register — <Target Name> — <date>

> **Evidence is mandatory.** A bug is not filed and not CONFIRMED without Jira attachments:
> **screenshot(s)** of the failure state **and** an **E2E screen recording** of the reproduction.
> Steps and expected behaviour MUST cite **OpenSpec** (REQ-/SC-) or persisted **TC** from `test-cases/`.
>
> Workflow: `openspec_read.sh` → execute steps → capture evidence → `create_bug_issue.py --attach …` → recording on the new bug key.

## BUG-001 — <one-line description of the problem, not the symptom>
- **Severity**: S1 | S2 | S3 | S4
- **Status**: Open | Fixed | Won't Fix | Needs Retest
- **Feature**: <area>
- **URL / Route**: <exact url>
- **STG buildId**: `<sha>` (from `stg_buildid.sh`)
- **Test case**: TC-<ticket>-… (`test-cases/TC-….md`)
- **Persisted TC steps executed**: <yes — list step numbers from ticket_tc / run.md>

### OpenSpec authority (MUST — from `openspec_read.sh`)
| Field | Value |
|-------|-------|
| **Change** | `<change-id>` or `openspec/specs/<cap>/spec.md` |
| **REQ-ID(s)** | REQ-… |
| **Scenario** | `<Scenario name>` |
| **Expected (quote OpenSpec THEN)** | … |

- **Steps to reproduce** (exact — match what recording shows):
  1. Login as `<role>` @ STG
  2. …
  3. …
- **Expected**: <per OpenSpec THEN / REQ — not tester guess>
- **Actual**: <observed on STG — canonical source if applicable>
- **Two-pass result**: Pass 1 (real input): FAIL / PASS · Pass 2 (automation/MCP): FAIL / PASS · discrepancy?

### Jira evidence attachments (MUST before closing filing)
| Artifact | Attached? | Reference |
|----------|-----------|-----------|
| Screenshot (error state) | ☐ | `runs/<run>/screenshots/BUG-001-*.png` → `--attach` on create |
| E2E recording (≤10MB) | ☐ | `record_and_attach.sh <slug> <JIRA-KEY> …` after create |
| Playwright trace / error-context | ☐ | `automation/test-results/…` (link in description) |

- **Console**: <paste relevant console errors, if any>
- **Network**: <paste 5xx response line, if a server error>

### Triage verdict (one of)
- `confirmed-defect` — contradicts OpenSpec/REQ
- `works-as-specified` — quote explicit requirement
- `environment` — config/env (name ops action)
- `cannot-reproduce` — state what was checked

**Verdict**: <verdict>
**Confidence**: high | medium | low

**Jira / GitHub:** `<KEY>` — filed with `--labels <slug>,confirmed-defect` (+ `impl-dev` auto) via `create_bug_issue.py`

### Root cause & class (for confirmed-defect)
- **Root cause (mechanism-specific)**: …
- **Class members**: …
- **Fix direction**: …
- **Regression test idea**: …
