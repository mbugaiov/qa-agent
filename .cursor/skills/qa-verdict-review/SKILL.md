---
name: qa-verdict-review
description: Critique Argus planned/executed QA verdict before Done or RETURN — OpenSpec coverage, evidence, false PASS/FAIL. Use after two-pass retest and before dod_check close/return. Not a third browser pass. Mandatory Cursor Task subagent + VERDICT_REVIEW_PASS tracker comment.
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
8. **Smoke pack** — when `automation/specs/acceptance-smoke.spec.js` (or `SMOKE_PACK`) exists
   (e.g. Pantheon), require green STG smoke + ledger `smoke_pack=pass` before Done.

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

## Sub-agent (mandatory)

For every `DONE` / `FAIL` / `RETURN_DEV` candidate, **wake a Cursor Task subagent**
whose only job is this skill (read artifact + OpenSpec excerpt + evidence paths).
Do **not** treat same-turn self-LGTM as sufficient by itself.

Prompt shape:

1. Role: verdict reviewer (qa-verdict-review) — not the executor who just closed the browser.
2. Read `verdict-review-<KEY>.md` draft (or write it), OpenSpec REQ/Scenario, TC path.
3. Run `check_verdict_review.sh`; if Blocking gaps ≠ None, set `VERDICT_REVIEW_BLOCKED` and stop close.
4. On pass: `factory_log … verdict_review result=pass` then
   `python3 scripts/post_verdict_review_comment.py --project projects/<slug> --key <KEY> --artifact … --summary "…"`.

## Tracker visibility (mandatory)

Humans must see the second opinion on the ticket:

```bash
python3 scripts/post_verdict_review_comment.py --project projects/<slug> --key <KEY> \
  --artifact runs/<run>/verdict-review-<KEY>.md \
  --summary "<KEY> PASS candidate — …"
```

Posts a comment starting with **`VERDICT_REVIEW_PASS`** (or `--blocked` → `VERDICT_REVIEW_BLOCKED`).

## Ledger

```bash
./scripts/factory_log.sh <slug> <KEY> verdict_review result=pass artifact=runs/<run>/verdict-review-<KEY>.md
# Also allowed on dod_check: verdict_review=pass artifact=…
```

`factory_tick_gate.sh` requires pass for `DONE` / `FAIL` / `RETURN_DEV`.

**Hard close gates (projects must use the engine):**

1. Ledger `verdict_review=pass` — else close/return exit **4**
2. Tracker comment `VERDICT_REVIEW_PASS` — else exit **7**
   (`--allow-missing-verdict-review` / `--allow-missing-verdict-review-comment` escape hatches only)

Live scripts: `jira_close_issue.py` / `github_close_issue.py` /
`jira_return_in_progress.py` / `github_return_to_dev.py`.

## If Blocking gaps non-empty

1. Fix execution / evidence / handoff in the **same tick**.
2. Re-write verdict-review until gate passes.
3. Post `VERDICT_REVIEW_BLOCKED` if leaving the ticket open for humans.
4. Only then escalate `needs-human` if policy-ambiguous — do not Done/RETURN with open gaps.
