# Execution Log — <Target Name> — <date>

> Maintained live during execution. Two-pass per case (Pass 1 = real input, Pass 2 = automation).

| ID | Title | Pass 1 | Pass 2 | Result | Bug | Notes |
|----|-------|--------|--------|--------|-----|-------|
| TC-AUTH-001 | Login with valid credentials | PASS | PASS | PASS | — | |
| TC-AUTH-002 | Login wrong password shows error | FAIL | FAIL | FAIL | BUG-001 | No error message shown |
| TC-AUTH-003 | Password reset flow | — | — | BLOCKED | — | Depends on email delivery |

**Statuses**: PASS = actual matches expected · FAIL = defect · BLOCKED = dependency missing · SKIP = out of scope.

## Stop conditions reached
- <e.g. none / S1 blocker at TC-X / environment unstable>
