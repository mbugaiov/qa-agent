# Test Cases — <Target Name>

> Each case derives from a scenario (SC-*) and traces to requirements (REQ-*).
> Chain: REQ → SC → TC. Techniques: Equivalence Partitioning, Boundary Value
> Analysis, State Transition, Decision Table, CRUD matrix, Error Guessing.

## <Feature Area>

| ID | Title | Type | Priority | Scenario | REQ |
|----|-------|------|----------|----------|-----|
| TC-AUTH-001 | Login with valid credentials | Acceptance | P1 | SC-001 | REQ-001 |
| TC-AUTH-002 | Login with wrong password shows error | Negative | P1 | SC-002 | REQ-002 |

### TC-AUTH-001 — Login with valid credentials
- **Type**: Acceptance
- **Priority**: P1
- **Scenario**: SC-001
- **REQ**: REQ-001
- **Preconditions**: A valid user account exists; user is logged out.
- **Steps**:
  1. Navigate to `/login`.
  2. Enter valid email.
  3. Enter valid password.
  4. Click "Sign in".
- **Expected**: User is authenticated and redirected to the dashboard; no console errors.

### TC-AUTH-002 — Login with wrong password shows error
- **Type**: Negative
- **Priority**: P1
- **Scenario**: SC-002
- **REQ**: REQ-002
- **Preconditions**: User is logged out.
- **Steps**:
  1. Navigate to `/login`.
  2. Enter valid email.
  3. Enter an incorrect password.
  4. Click "Sign in".
- **Expected**: An error message is shown; user is NOT authenticated; response is 401 (not 200/500).
