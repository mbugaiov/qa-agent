# Retest FAIL — Dev handoff — <TICKET-KEY> (tick <N>)

> Structured return for dev-agent. Post via `jira_return_in_progress.py --handoff-file`.

## Summary
<One line: what failed and why dev must act>

## Environment
- **STG URL:** <url>
- **STG buildId:** `<sha>` (handoff: `<sha>` · gate: MATCH|MATCH_AHEAD|MISMATCH)
- **Automation:** `<spec-file>` (PF-XX)
- **Recording:** <Jira attachment name or "attached">

## OpenSpec authority (read before retest)
| Field | Value |
|-------|-------|
| **Change** | `<change-id>` (e.g. `fix-scheduled-backlog-assign`) |
| **Capability** | `<capability>` (e.g. `visibility`, `lab-request`) |
| **Spec path** | `openspec/changes/<change>/specs/<cap>/spec.md` |
| **REQ-IDs** | REQ-…, REQ-… |
| **Governing scenario** | `<Scenario name>` |

### Expected behaviour (quote OpenSpec)
```
<GIVEN/WHEN/THEN from OpenSpec — the oracle for this retest>
```

## QA retest steps executed
1. `jira_handoff.sh` — PR #… build …
2. `openspec_read.sh` — scenarios …
3. `test_data_prep` — … (or N/A)
4. …
5. …

## Expected (per OpenSpec + acceptance)
- …

## Actual (observed on STG)
- …

## Dev reproduction (minimal)
1. Login manager `<user>` @ STG
2. …
3. …

## Test design review
| Check | Result |
|-------|--------|
| Test asserts correct OpenSpec THEN? | YES / NO — … |
| GIVEN preconditions met (prep/data)? | YES / NO — … |
| Could this be works-as-specified? | YES / NO — … |
| Canonical confirmation used? | e.g. `request-status-badge` vs ambiguous "Scheduled" text |

## Suggested fix direction
- …

## Evidence
- Screenshot: `test-results/…`
- Playwright error-context: …
- Prior recording on ticket: …
