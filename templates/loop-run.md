# Run — <task title> (continuous loop)

> Loop engagement manifest. Durable state → `project-memory.md` (active loop, coverage, cadence).

- **Run id**: <YYYY-MM-DD>-exploratory-<task-slug>
- **Type**: exploratory (recurring L5 / continuous QA loop)
- **Date**: <YYYY-MM-DD>
- **Scope**: retest Jira active scope + exploratory on uncovered areas + security slice
- **Prior run (if rotated):** `runs/<previous-run-id>/` (archived — history preserved)

## Mandate (each tick)
1. Jira scope check first (no server if empty).
2. Retest active tickets per machine DoD (`qa-jira` skill).
3. Fresh exploratory — rotate toward uncovered areas (`project-memory.md` coverage ledger).
4. Security slice from `templates/security-checklist.md`.
5. Auto-file / auto-reopen per project policy.
6. Append iteration log below; update `project-memory.md` when material state changes.

**Start loop (Agent chat):** `/loop 21600 AGENT_LOOP_WAKE_<purpose>` — see skill `qa-loop` (interval in seconds; not a bash command).

## Iteration log

### Tick 0 — <date> (run opened)
- <why this run was created / rotated from prior run>

## Result
- **Verdict**: in progress
- **Memory updated**: ☐ yes
