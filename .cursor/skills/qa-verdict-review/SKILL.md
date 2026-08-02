---
name: qa-verdict-review
description: Critique Argus planned/executed QA verdict before Done or RETURN — OpenSpec coverage, evidence, false PASS/FAIL. Use after two-pass retest and before dod_check close/return. Not a third browser pass.
---

# QA verdict review (Argus lead critique)

Mirrors Themis for **verdicts**, not code diffs. Argus plans and executes; this step
asks whether the **decision** is justified before Jira/GitHub close or `QA RETURN`.

## When (mandatory)

After evidence + buildId for a scope ticket, **before**:

- `dod_check` with `DONE` / `FAIL` / `RETURN_DEV`
- `jira_close_issue` / `github_close_issue` / `jira_return_in_progress` / `github_return_to_dev`

**Skip** (document in `run.md`): `SKIP_DEV`, `QA_CONTINUE`, pure-CI with `recording_exempt`
when no product behaviour was judged — still prefer a one-line skip note.

## Not this skill

- Re-running the full two-pass browser suite
- Product code review (Themis / app CR)
- Isolation/portability of engines (`themis-agent`)

## Checklist

1. **OpenSpec** — expected THEN from `openspec_read` matches what was asserted; not a weaker proxy.
2. **TC** — persisted TC steps were the ones executed (`ticket_tc` / `test-cases/`).
3. **Evidence** — recording/screenshots paths exist for the claim (or valid exempt).
4. **buildId** — MATCH / MATCH_AHEAD / N/A / SKIP consistent with handoff.
5. **PASS risk** — would a human reject Done? (missing edge, wrong oracle, UI-only agreement).
6. **FAIL/RETURN risk** — is this `works-as-specified`? Is handoff repro + OpenSpec quote enough for Hephaestus?
7. **Labels** — `impl-qa` not closed with SKIP_DEV; V/T not left open on FAIL.

## Output artifact

Write `projects/<slug>/runs/<run>/verdict-review-<KEY>.md`:

```markdown
## Summary
<KEY> — PASS|FAIL|RETURN candidate — 1–2 sentences

## Blocking gaps
None.

## Suggestions
- …
```

Or exactly: `LGTM - no blocking gaps found.`

Gate: `bash scripts/check_verdict_review.sh <path>` must exit 0.

## Ledger

```bash
./scripts/factory_log.sh <slug> <KEY> verdict_review result=pass artifact=runs/<run>/verdict-review-<KEY>.md
# Also allowed on dod_check: verdict_review=pass artifact=…
```

`factory_tick_gate.sh` requires pass for `DONE` / `FAIL` / `RETURN_DEV`.

## If Blocking gaps non-empty

1. Fix execution / evidence / handoff in the **same tick**.
2. Re-write verdict-review until gate passes.
3. Only then escalate `needs-human` if policy-ambiguous — do not Done/RETURN with open gaps.

## Sub-agent (optional)

Wake a Task subagent **only** when gaps remain after one self-fix, or on marathon
`impl-qa` → Done. Prompt: read this skill + artifact + OpenSpec excerpt; do not re-browser
the whole suite unless evidence is missing.
