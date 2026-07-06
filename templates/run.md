# Run — <task title>

> Manifest for one task/run inside this project. One project (slug) = many runs.

- **Run id**: <YYYY-MM-DD>-<type>-<task-slug>
- **Type**: targeted | exploratory | regression | smoke | uat | full
- **Date**: <YYYY-MM-DD>
- **Requested by / source**: <chat task | Jira BUG-x | release sign-off>
- **Scope**: <which REQ-* / features / pages this run covers — or "charter" for exploratory>
- **Out of scope**: <explicitly excluded>

## Artifacts in this run
> Only the ones relevant to the type are created (see AGENTS.md run-type table).

- [ ] execution-log.md        (targeted / regression / smoke / full)
- [ ] exploratory-session.md  (exploratory)
- [ ] bug-report.md           (any, if defects found)
- [ ] traceability-matrix.md  (full / acceptance)
- [ ] manual-test-plan.md     (full / acceptance)
- [ ] risk-register.md        (full / acceptance)
- [ ] acceptance-report.md    (full / acceptance)
- [ ] report.md               (any — summary)
- [ ] screenshots/            (evidence)

## Result
- **Cases**: <n run> · **Pass**: <n> · **Fail**: <n> · **Blocked**: <n>
- **New bugs**: <ids>  ·  **Verdict**: <PASS / GO / CONDITIONAL / NO-GO / n/a>
- **Memory updated**: ☐ yes (project-memory.md run-history row added)
