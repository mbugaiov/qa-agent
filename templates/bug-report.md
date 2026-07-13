# Bug Register — <Target Name> — <date>

> A bug is CONFIRMED only with evidence: a screenshot of the visible error state, OR a captured
> HTTP 5xx network response during the action. Never confirm from body-text matching "500".
>
> Triage methodology adapted from koldovsky/project-factory (bug-triage-analyst):
> map → trace → verdict → root cause + class → regression test.

## BUG-001 — <one-line description of the problem, not the symptom>
- **Severity**: S1 | S2 | S3 | S4   (Critical / Major / Minor / Cosmetic)
- **Status**: Open | Fixed | Won't Fix | Needs Retest
- **Feature**: <area>
- **URL / Route**: <exact url>
- **Test case**: TC-AUTH-002
- **Requirement**: REQ-002  *(quote the governing requirement/scenario; if none exists, that is itself a finding — requirements gap)*
- **Steps to reproduce**:
  1. ...
  2. ...
  3. ...
- **Expected**: <what should happen, per the requirement>
- **Actual**: <what actually happens>
- **Evidence**: `runs/<date>/screenshots/BUG-001-*.png`
- **Console**: <paste relevant console errors, if any>
- **Network**: <paste 5xx response line, if a server error>
- **Two-pass result**: Pass 1 (real input): FAIL / PASS · Pass 2 (automation): FAIL / PASS · <discrepancy?>

### Triage verdict (one of)
- `confirmed-defect` — behaviour contradicts the requirement, or crashes/misbehaves on legitimate input
- `works-as-specified` — behaviour matches an explicit requirement the tester didn't know about (quote it; suggest the UX hint that would prevent the report)
- `environment` — code path is correct but a config/env issue causes the symptom (name the exact ops action)
- `cannot-reproduce` — steps don't produce the symptom (state what was checked)

**Verdict**: <verdict>
**Confidence**: high | medium | low

**Jira labels (when filing):** `confirmed-defect` + project slug (e.g. `your-project`) — `create_jira_issue.py` auto-adds `qa-agent`, `severity-s*`, and **`impl-dev`** (dev factory autotake).

### Root cause & class (for confirmed-defect)
- **Root cause (mechanism-specific)**: <e.g. validation throws and surfaces as 500, not "validation broken">
- **Class members (same latent bug elsewhere)**: <other forms/routes with the same mechanism, or "none found">
- **Fix direction**: <what should change>
- **Regression test idea**: <a test that fails on current code and passes after the fix — reference BUG-001>
