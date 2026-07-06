# Exploratory Session — <Target> — <date>

> Session-based test management. Exploratory runs are charter-driven and
> time-boxed — they do NOT use a fixed TC list. Findings still trace to
> requirements where one applies; behaviour with no requirement is a scope-drift
> finding (flag it).

## Charter
- **Mission**: <what to explore, in one sentence — e.g. "probe the checkout flow for state/validation defects">
- **Areas in scope**: <pages / features>
- **Out of scope**: <what not to touch>
- **Timebox**: <e.g. 60 min>  ·  **Roles used**: <guest / user / admin>

## Test notes (running log)
> Timestamped stream of what you did and saw. Mark anomalies `[INVESTIGATE]`.

- HH:MM — <action> → <observation>
- HH:MM — <action> → <observation> `[INVESTIGATE]`

## Coverage touched
| Area | Depth | Notes |
|------|-------|-------|
| Checkout | deep | tried empty cart, duplicate coupon, back-mid-flow |
| Search | shallow | only basic queries |

## Bugs found (log to bug-report.md, triage each)
| Bug | Severity | Area | Verdict | Notes |
|-----|----------|------|---------|-------|
| BUG-00X | S2 | Checkout | confirmed-defect | coupon stacks twice |

## Questions / risks raised
- <ambiguity to confirm with product owner — per qa-team rule, flag, don't guess>

## Follow-up
- **New scripted cases to add**: <TC ideas worth formalising into test-cases/>
- **Areas needing another session**: <…>
