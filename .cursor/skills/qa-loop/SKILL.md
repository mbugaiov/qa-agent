---
name: qa-loop
description: What every recurring/continuous QA loop tick must do — retest the Jira active scope (In Progress + Validate/Testing), fresh exploratory on uncovered areas, file new bugs, with retest-rigour and browser/server hygiene. Security testing is NOT per tick — see skill `qa-security` (exploratory and regression runs only). Use when running a scheduled/looping QA cycle.
---

# Continuous QA loop (what every tick must include)

**Active run folder:** check `project-memory.md` → `## Active loop` for the current
`projects/<slug>/runs/<id>/run.md`. Append iteration logs there. Rotate the run folder per `qa-runs`
skill when the engagement ages or scope shifts — don't keep writing into a stale dated folder.

A recurring QA loop tick is NOT only ticket re-validation. Each tick does all of:

1. **Work the active QA scope** = query Jira every tick for **every** epic child in `status in (In Progress, Validate/Testing)` — **never tunnel on a single ticket** while others remain in scope. **Each tick must attempt full machine DoD on ALL tickets returned by the scope query before the tick ends** — do not close one ticket and defer the rest to the next wake. Retest each on the live app. **L5 unattended** — act without asking (see `qa-jira` skill for the machine DoD):
   - `Validate/Testing` (dev says ready) → PASS + DoD met → **auto-Done** (incl. STG buildId gate: MATCH or MATCH_AHEAD); FAIL → **In Progress** + bug; **blocked** → **In Progress** + dev/bug ticket — **never leave V/T while blocked**.
     STG **MISMATCH** / **MISMATCH_BEHIND** ⇒ NOT Done → comment expected-vs-actual (MATCH_AHEAD passes when STG advanced past handoff but includes it).
   - `In Progress` (still being worked / mine to track) → re-check anyway: if the fix is now present and
     passes → move to **Validate/Testing** (or **Done** if unambiguous) with "QA: appears fixed"; else
     leave **In Progress** with a note. Never drop In Progress tickets — they stay in scope until Done/Closed.
   - `needs-human` verdict (ambiguous / policy / destructive) → do NOT auto-close; leave open and surface to the user.
   - Always leave a QA comment with the verdict + evidence.
   - **Recording evidence (ALWAYS, FE *and* BE/infra):** attach a ≤10MB E2E screen recording showing the
     **customer-side** steps that validate the fix/feature works now, via `scripts/record_and_attach.sh`
     (stored only in Jira) — required for every auto-Done and every confirmed bug. Pure-CI/pipeline tickets exempt.
   - **Regression**: a Done ticket that now FAILS → `scripts/reopen_regression.py` (auto-reopen to In Progress).
2. **Fresh exploratory testing** — pick the next **uncovered or least-covered** area and probe it (rotate so
   coverage broadens every tick, not the same pages). Track covered areas in `run.md` so ticks don't repeat.
3. **Auto-file new confirmed bugs** to Jira under the epic (dedupe via JQL first, unattended); update `run.md` (covered areas + findings).

4. **impl-qa factory queue (when retest scope is empty):** `labels = impl-qa AND status = "To Do"` — autotake the head ticket (move to In Progress when execution starts), run its linked `runs/<id>/` folder charter. **Never start impl-qa while retest JQL has open V/T tickets.** Do not leave impl-qa queued while retest JQL still has open tickets.

5. **File confirmed defects during regression/retest:** any `confirmed-defect` or sign-off-blocking environmental issue → `create_jira_issue.py` immediately with `--labels <slug>,confirmed-defect` (script auto-adds **`impl-dev`** for dev factory autotake; dedupe JQL first). Comment on the feature ticket; the **bug is a separate issue** under the epic.

**Not on every tick:** security testing — run only on **`exploratory`** and **`regression`** run cycles (skill `qa-security`). Loop ticks are Jira retest + lightweight exploratory slices, not security cycles.

Prioritise coverage breadth: exploratory slices should advance to something not yet tested each tick.

**Retest rigour:** a fix is PASS only when the *actual behaviour/value* is correct — verify against the
**canonical source of truth**, not a weaker proxy. A "two views disagree" bug is NOT Done just because the
views now agree; confirm the displayed value matches the authoritative record (detail page / DB / API).
When unsure, the verdict is FAIL/needs-info, not Done.

**Server per tick:** start it (if down) and stop it after (only what we started) — see the `qa-server` skill.

**Test data (feature retests on shared STG):** before assign/relocate/lifecycle write tests, run
`scripts/test_data_prep.sh <slug> [--stg]`; after, `scripts/test_data_cleanup.sh`. No free station
without prep ⇒ **BLOCKED_SETUP**, not product FAIL. Skill: `qa-test-data`. Do not force Jira Done
from one corrected run — follow normal DoD + recording.

**Factory ledger (each tick):** log tick boundaries and material events via
`scripts/factory_log.sh <slug> …`; schema: `projects/<slug>/factory/schema.md`.

### Per-ticket DoD checklist (mandatory — gate enforced)

**Do not log `tick_end` until `factory_tick_gate.sh` exits 0.** Smoke tests and Jira
comments alone are **not** tick-complete.

**Tick workflow (strict order):**

0. **Scope (mandatory — never skip, never hardcode):**
```bash
eval "$(./scripts/jira_scope.sh <slug> --log --shell)"
# Sets: count, SCOPE_COUNT, keys, SCOPE_KEYS — use either count or SCOPE_COUNT (both set).
# --log writes scope_check to the factory ledger (required for factory_tick_gate.sh).
echo "scope count=${SCOPE_COUNT:-$count} keys=${SCOPE_KEYS:-$keys}"
```
**Forbidden:** checking `$SCOPE_COUNT` without `--log --shell`; logging `scope_check count=0` by hand; skipping scope when Jira is configured.

1. `tick_start` + scope step above (scope_check logged by `--log`)
2. **If `count > 0` (or `SCOPE_COUNT > 0`):** for **each** scope ticket **before browser work**:
   - `./scripts/jira_handoff.sh <slug> <KEY> --log` → factory `handoff_read`
   - **`./scripts/openspec_read.sh <slug> --ticket <KEY>`** (skill `qa-openspec`) — read governing REQ/scenarios; validate test design
   - Derive 3–5 test steps from **OpenSpec + handoff** → note in `run.md` per-ticket checklist
   - `./scripts/stg_buildid.sh <slug> <handoff-sha>` when handoff cites buildId
3. For **each** scope ticket — execute checklist → log `dod_check` with terminal verdict
4. `./scripts/factory_tick_gate.sh <slug>` — must print `GATE OPEN`
5. **Only if scope empty OR all scope tickets have terminal `dod_check`:** exploratory slice
6. `tick_end` + update `run.md`

**Scope-non-empty rule (gate enforced):** when `scope_check count > 0`, **do not** log
`exploratory` or `tick_end` until every scope key has `handoff_read` + terminal `dod_check`.
Generic STG smoke is **prep only**, not a substitute for feature retest.

**Never re-arm the loop sleeper until step 4 passes** (unless user explicitly requests monitor-only mode).

**Per-ticket checklist** (log one `dod_check` per key; copy into `run.md` each tick):

| Step | Requirement | Ledger |
|------|-------------|--------|
| 0 | `jira_handoff.sh <slug> <KEY> --log` | `handoff_read` |
| 0a | `openspec_read.sh <slug> --ticket <KEY>` — validate PF/TC vs OpenSpec | `openspec_read=true` in `dod_check` |
| 0b | Write 3–5 test steps in `run.md` from **OpenSpec + handoff** | (run.md checklist) |
| 1 | Two-pass retest on **canonical source** (detail / audit / API) | `retest_attempted=true`, `feature_steps_executed=true` |
| 2 | `stg_buildid.sh` → MATCH or MATCH_AHEAD (or N/A / SKIP) | `buildid_gate` |
| 3 | `record_and_attach.sh` → Jira (unless `recording_exempt` pure-CI) | `recording_attached=true` |
| 4 | Jira `transition` + comment: **Done** if PASS; **In Progress** if FAIL or blocked | `transition` event |

**RETURN_DEV / FAIL** additionally require in `dod_check`: `retest_attempted=true`,
`alternate_locators_tried=true` (RETURN_DEV only), `feature_steps_executed=true` or `steps_tried=…`.
`jira_return_in_progress.py` requires `--steps-tried` (summary of what was attempted).

**V/T terminal outcomes (mandatory — no third state):**

A ticket in `Validate/Testing` must end the tick as either **Done** or **In Progress**. Logging
`BLOCKED` while Jira still shows V/T is **forbidden**.

**Before declaring blocked**, exhaust alternate verification:
- other locators (`data-testid`, aria, role, text, CSS)
- native `.click()` / `evaluate` (MCP `browser_click` often misses server actions)
- manual two-pass on canonical source if automation cannot drive one control

If still blocked:
1. **File** a separate Jira issue (`create_jira_issue.py` for product bug; impl-dev task for missing testids/locators)
2. **Return** feature ticket: `python3 scripts/jira_return_in_progress.py --project projects/<slug> --key <KEY> --reason "…" --steps-tried "1. … 2. …" --handoff-file runs/<run>/retest-fail-<KEY>-tick<N>.md [--dev-ticket <KEY>]`
3. Log `transition to=In Progress` + `dod_check verdict=RETURN_DEV` with `openspec_read=true`, `dev_handoff=<path>`

**Terminal `dod_check` verdicts only:**

| Verdict | When |
|---------|------|
| `DONE` | Full DoD met (two-pass, buildId, recording) |
| `FAIL` | Product defect confirmed |
| `RETURN_DEV` | Blocked — returned to In Progress + dev/bug ticket |
| `SKIP_DEV` | **Only** when ticket is **dev-owned** and STG/build **unchanged** — awaiting dev handoff |

**FORBIDDEN:** `SKIP_DEV` on QA-owned **In Progress** tickets where QA already has PASS evidence. If PASS + unchanged build → **re-run DoD** (prep, automation, recording) and **transition Done/V/T** same tick. Never log 5+ consecutive monitor SKIP_DEV ticks without execution.

| Verdict | When | Required fields |
|---------|------|-----------------|
| `DONE` | All DoD met | `two_pass=true`, `canonical_source=true`, `buildid_gate`, `recording_attached=true` (or `recording_exempt=true`) |
| `FAIL` | Product defect | `bug_filed=<KEY>`, `transition` to=In Progress |
| `RETURN_DEV` | QA/dev blocker after alt locators tried | `bug_filed` or `dev_ticket`, `transition` to=In Progress, `retest_attempted=true`, `alternate_locators_tried=true`, `feature_steps_executed=true` |
| `SKIP_DEV` | Ticket already **In Progress** (dev-owned) — not V/T retest | `jira_status=In Progress`, `note` |

**Forbidden at tick_end:** `PARTIAL`, `DEFERRED`, `PASS_PENDING`, `BLOCKED`, “PASS (recording pending)” in `run.md`.

**Monitor skip policy:** skip automation **only** when every scope ticket already has `recording_attached`
on a prior tick **or** explicit user monitor mode. Open V/T without recordings → **no skip**.

```bash
./scripts/factory_log.sh <slug> _loop tick_start run=<run-id>
eval "$(./scripts/jira_scope.sh <slug> --log --shell)"
# scope_check logged; count / SCOPE_COUNT available for branching
./scripts/jira_handoff.sh <slug> ABC-1 --log
./scripts/jira_handoff.sh <slug> ABC-2 --log
./scripts/factory_log.sh <slug> ABC-1 dod_check verdict=DONE two_pass=true canonical_source=true buildid_gate=MATCH recording_attached=true feature_steps_executed=true retest_attempted=true
./scripts/factory_log.sh <slug> ABC-1 transition to=Done
python3 scripts/jira_return_in_progress.py --project projects/<slug> --key ABC-2 \
  --reason "Control not reachable by automation" --dev-ticket ABC-9 \
  --steps-tried "1. handoff read 2. test_data_prep 3. primary flow 4. alt locators"
./scripts/factory_log.sh <slug> ABC-2 transition to=In\ Progress reason="locator gap"
./scripts/factory_log.sh <slug> ABC-2 dod_check verdict=RETURN_DEV dev_ticket=ABC-9 transition=In\ Progress retest_attempted=true alternate_locators_tried=true feature_steps_executed=true
./scripts/factory_tick_gate.sh <slug>
./scripts/factory_log.sh <slug> _loop exploratory area="…" result=PASS
./scripts/factory_log.sh <slug> _loop tick_end run=<run-id> gate=open
```

Summarize offline with `scripts/factory_status.sh <slug>`.
Dev factory events (`agent=dev`: pick, merge, deploy, handoff_vt) use the same script when a dev loop is enabled.

## Run the loop yourself (Cursor chat — not bash)

The recurring loop is started with the Cursor **`/loop` skill** in **Agent chat** (with the
`qa-agent` workspace open). It is **not** a shell script you run in Terminal.

### Start / resume

```
/loop 3600 AGENT_LOOP_WAKE_<slug>qa
```

| Part | Meaning |
|------|---------|
| `/loop` | Cursor loop skill — run now, then re-arm a background timer |
| `3600` | Interval in **seconds** (3600 = 1 hour). Use `21600` for 6h, `900` for 15m, `180` for 3m, etc. |
| `AGENT_LOOP_WAKE_<slug>qa` | Unique **sentinel** for this project's QA loop. Wakes the agent when the timer fires. |

**What happens:** the agent runs **one full tick immediately** (Jira retest per `qa-jira`, exploratory
slice, update `run.md` + `project-memory.md`), then arms:

```bash
sleep 3600; echo 'AGENT_LOOP_WAKE_<slug>qa {"prompt":"…"}'
```

with `notify_on_output` so Cursor auto-wakes on the sentinel.

**Before starting:** read `projects/<slug>/project-memory.md` → `## Active loop` for the current
`runs/<id>/run.md` and scope JQL (if Jira-enabled).

### Run a single tick (no timer)

```
Run one QA loop tick now for projects/<slug> (continuous loop, epic <EPIC-KEY>).
```

Or attach skill `qa-loop` and ask for one tick. Does **not** re-arm a background sleeper unless you ask.

### Stop all loops

Tell the agent: **"stop all loops for qa-agent"** — kills background `sleep …; echo AGENT_LOOP_WAKE_*`
tasks and marks the run **paused** in `run.md` / `project-memory.md`. No auto re-arm until you
`/loop …` again.

### Diagnostics only (shell — not the loop itself)

Run from the **engine repo root** (where `scripts/` lives):

```bash
./scripts/jira_status.sh <slug>
./scripts/jira_handoff.sh <slug> <KEY> [--log]   # mandatory before V/T retest when scope non-empty
./scripts/stg_buildid.sh <slug> <merge-sha>
./scripts/server_ctl.sh <slug> status
./scripts/factory_status.sh <slug>
./scripts/factory_tick_gate.sh <slug>    # before tick_end — must exit 0
./scripts/run_automation.sh <slug> --stg
```

**Loop mechanics (agent):** use the `loop` skill (background sleeper + sentinel + `notify_on_output`); reset the
Playwright MCP browser at tick start (`browser_close` → navigate) to avoid the wedged-session no-op trap;
sanity-check interactivity (e.g. `/login` show-password toggle) before trusting "nothing works".
