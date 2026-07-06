# Spec — <Capability / Area> — <Project>

> Lightweight spec-driven testing layer. Business requirements (`REQ-*`) are
> normalized into testable acceptance scenarios (`SC-*`) in Given/When/Then form.
> Test cases (`TC-*`) derive from scenarios. Authored once per project at the
> **project level** (`projects/<slug>/specs/`); each run consumes a subset.
>
> Chain: `REQ → SC → TC → evidence`. Run `scripts/check_coverage.py projects/<slug>`
> to find requirements with no scenario, or scenarios with no test.

## SC-001 — <scenario title>
- **Covers**: REQ-001
- **Priority**: P1
- **Type**: happy-path | negative | edge | a11y | security

```gherkin
Given a registered user who is logged out
When they submit valid email and password on /login
Then they are authenticated and redirected to the dashboard
And no console error is produced
```

**Notes / ambiguities**: <flag anything unclear — per qa-team rule, do not guess>

## SC-002 — <scenario title>
- **Covers**: REQ-002
- **Priority**: P1
- **Type**: negative

```gherkin
Given a user on /login
When they submit a valid email with an incorrect password
Then an error message is shown
And they remain unauthenticated
And the response status is 401 (not 200 or 500)
```

**Notes / ambiguities**: <…>

---

## Coverage rules
- Every MVP `REQ-*` is covered by **at least one** `SC-*` (else: requirements gap).
- Every `SC-*` has **at least one** `TC-*` deriving from it (else: coverage gap).
- A scenario with a real ambiguity is still written, with the ambiguity flagged —
  not silently resolved.
