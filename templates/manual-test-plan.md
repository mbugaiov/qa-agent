# Manual Test Plan — <Target Name>

> Adapted from koldovsky/project-factory (qa-pack). Executable by a non-developer
> in a browser. Each case is objectively checkable and traces to requirements.

**Environment**: <browser / OS / viewport>
**Test accounts**: <seeded users / roles>

## MT-01 — <Title>
- **Covers**: REQ-001, REQ-002
- **Preconditions**: <state before test>
- **Steps**:
  1. ...
  2. ...
  3. ...
- **Expected**: <objectively checkable result>
- **Result**: ☐ Pass ☐ Fail — notes: ______

## MT-02 — <Title>
- **Covers**: REQ-...
- **Steps**: 1. ... 2. ...
- **Expected**: ...
- **Result**: ☐ Pass ☐ Fail — notes: ______

## Negative cases (mandatory)

Always include cases for:
- Invalid input — oversized strings, locale decimals ("12,51"), blanks/missing fields, boundary values (0, max, max+1)
- Unauthorized access per role (anonymous redirect, wrong-role denial, inactive-user denial)
- Deletion / edit of referenced records (referential integrity)
