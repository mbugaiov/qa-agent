# Requirements Traceability Matrix — <Target Name>

> Adapted from koldovsky/project-factory (qa-documenter / qa-pack).
> Full chain: **REQ → SC → TC → evidence**. **No empty cells** — if something is
> untested, write the explicit reason in the cell.

| Req | Scenario | Capability / Area | Test cases | Manual / Auto | Evidence | Status |
|-----|----------|-------------------|-----------|---------------|----------|--------|
| REQ-001 | SC-001 | Authentication | TC-AUTH-001 | Manual | runs/<run>/screenshots/TC-AUTH-001.png | ✅ Pass |
| REQ-002 | SC-002 | Authentication | TC-AUTH-002 | Manual | BUG-001 (runs/<run>/screenshots/BUG-001.png) | ❌ Fail |
| REQ-003 | SC-… | <area> | TC-… | Manual+Auto | <link> | ⏳ Not run |

## Coverage check (run before sign-off)

Run `scripts/check_coverage.py projects/<slug>` for the automated REQ→SC→TC check, then confirm:

- [ ] Every MVP requirement is covered by **at least one** scenario (no REQ without SC).
- [ ] Every scenario has **at least one** test case (no SC without TC).
- [ ] No empty cells without an explicit reason.
- [ ] NFRs (performance, security, a11y) also have rows.
- [ ] **Inverse check (scope drift):** any tested behaviour with NO backing
      requirement is flagged here so requirements can be amended.

## Scope-drift / requirement-gap findings

- <e.g. App exposes a bulk-export feature not covered by any REQ — flag for product owner>
