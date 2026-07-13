---
name: qa-openspec
description: Read dev-agent OpenSpec before retest — map REQs/scenarios to test design, validate PF/TC assertions against canonical Given/When/Then, and ground FAIL handoffs for dev. Use before every V/T retest, when filing bugs, when judging works-as-specified vs confirmed-defect, or when designing/updating automation specs.
---

# OpenSpec — read before retest

QA tests a deployed app; **OpenSpec is the oracle** for what correct behaviour means. Read it **before** executing feature retest steps — not only after a failure.

## Canonical paths

| Source | Path |
|--------|------|
| Baseline specs | `{SERVER_GIT_WORKTREE}/openspec/specs/<capability>/spec.md` |
| Active change deltas | `{SERVER_GIT_WORKTREE}/openspec/changes/<change-id>/specs/<capability>/spec.md` |
| REQ index (QA) | `projects/<slug>/requirements/openspec-requirements.md` |
| Traceability | `projects/<slug>/runs/.../traceability-matrix.md` |

`SERVER_GIT_WORKTREE` from `projects/<slug>/.secrets/server.env` (app repo worktree with `openspec/`).

## Mandatory workflow (every scope retest)

```
1. openspec_read   → scripts/openspec_read.sh <slug> --ticket <KEY> [--change <id>]
2. Map REQs        → note governing REQ-IDs + scenario names in run.md test plan
3. Design check    → does PF/TC assertion match OpenSpec WHEN/THEN? (see below)
4. Execute retest  → prep → two-pass / automation on canonical source
5. On FAIL         → templates/retest-fail-dev-handoff.md → jira_return_in_progress.py --handoff-file
```

## Test design validation (before declaring FAIL)

For each retest, answer in `run.md`:

| Question | Action if NO |
|----------|----------------|
| Does the test assert the **THEN** from the governing OpenSpec scenario? | Fix test or mark `test-design-gap` — do not file product bug yet |
| Does the test satisfy all **GIVEN** preconditions (prep, role, data)? | Run `test_data_prep` / fix setup — verdict `BLOCKED_SETUP` |
| Could failure be **works-as-specified** (e.g. FR-SCH-7 conflict rejection)? | Quote OpenSpec scenario; verdict `works-as-specified`, not `confirmed-defect` |
| Is assign success confirmed via `request-status-badge` / status, not ambiguous text? | Fix helper before blaming product |

**Example:** OpenSpec says backlog update applies **WHEN assign succeeds**. If assign is **rejected** (scheduling conflict), staying in Triage is **correct** — failure is test/helper/prep, not queue UI.

## Reading a ticket's OpenSpec

1. `jira_handoff.sh` — note `change` id, PR, acceptance steps.
2. `openspec_read.sh <slug> --ticket ABC-123` — prints linked change + capability excerpts.
3. Or explicit: `openspec_read.sh <slug> --cap <capability> --grep "keyword"`.
4. Cross-check automation spec header comments against live OpenSpec text.

## FAIL → dev-agent handoff (mandatory)

Every retest **FAIL** or **RETURN_DEV** on a scope ticket requires a structured handoff file:

- Copy `templates/retest-fail-dev-handoff.md` → `runs/<active-run>/retest-fail-<KEY>-tick<N>.md`
- Fill **all** sections (OpenSpec refs, steps executed, expected/actual, dev repro, test design review)
- Post to Jira:

```bash
python3 scripts/jira_return_in_progress.py --project projects/<slug> --key <KEY> \
  --reason "<one line>" \
  --steps-tried "summary" \
  --handoff-file runs/<run>/retest-fail-<KEY>-tick<N>.md
```

Gate: `factory_tick_gate.sh` requires `openspec_read=true` on FAIL/RETURN_DEV `dod_check` when scope non-empty.

## Verdict mapping (OpenSpec-grounded)

| Observation | Verdict |
|-------------|---------|
| Behaviour matches OpenSpec THEN | PASS / `works-as-specified` |
| Contradicts OpenSpec THEN with evidence | `confirmed-defect` → file/update bug |
| Test asserts wrong THEN / missing GIVEN | `test-design-gap` — fix QA spec first |
| STG data blocks GIVEN (LAB-3, congestion) | `environment` / `BLOCKED_SETUP` |
