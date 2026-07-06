## Business context

<Why this work exists — link to epic goal, user pain, or maturity gap. One short paragraph.>

**Epic:** <EPIC-KEY> — <product name>
**Deploy target:** <STG URL or environment> — note any On Hold deploy work

---

## Implementing agent

> **DEV agent** OR **QA agent** — pick one. The other agent **must skip** this ticket.

| Field | Value |
|-------|--------|
| **Owner** | DEV agent \| QA agent |
| **Codebase** | <app repo path> \| `qa-agent/` |
| **Jira label** | `impl-dev` \| `impl-qa` |
| **CR agent** | Not the implementer (reviews PRs in dev loop only) |

---

## Requirement

**As a** <role>
**I need** <capability in plain business language>
**So that** <measurable outcome>

---

## OpenSpec change (if applicable)

- **Change id:** `<kebab-case-id>`
- **Capability:** `<capability-folder>`
- **Spec delta:** `<path to delta spec>`
- **Validate:** `<project validate command>`
- **Archive when done:** `<project archive command>`

### Scenario — <short title>

```gherkin
Given <precondition>
When <action or event>
Then <observable outcome>
```

---

## Implementation approach

1. <First concrete step>
2. <Code / rule / pipeline change — name files>
3. <Tests>
4. <Review / merge / deploy>
5. <QA retest on target environment>

**Primary surfaces:** `<paths>`

---

## Acceptance criteria

- <ticket-specific criteria>
- QA two-pass PASS on scenarios above; E2E recording attached when moving to Done (unless pure-CI)
- STG/deploy buildId matches merged commit when a staging gate is configured

---

## Out of scope

- <Explicit exclusions>

---

## Dependencies

- <EPIC-child-key or "none">
