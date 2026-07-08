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
   - `Validate/Testing` (dev says ready) → PASS + DoD met → **auto-Done** (incl. STG buildId gate: MATCH or MATCH_AHEAD); FAIL → **In Progress**.
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

4. **impl-qa factory queue (when retest scope is empty):** `labels = impl-qa AND status = "To Do"` — autotake the head ticket (move to In Progress when execution starts), run its linked `runs/<id>/` folder charter. Do not leave impl-qa queued while retest JQL still has open tickets.

**Not on every tick:** security testing — run only on **`exploratory`** and **`regression`** run cycles (skill `qa-security`). Loop ticks are Jira retest + lightweight exploratory slices, not security cycles.

Prioritise coverage breadth: exploratory slices should advance to something not yet tested each tick.

**Retest rigour:** a fix is PASS only when the *actual behaviour/value* is correct — verify against the
**canonical source of truth**, not a weaker proxy. A "two views disagree" bug is NOT Done just because the
views now agree; confirm the displayed value matches the authoritative record (detail page / DB / API).
When unsure, the verdict is FAIL/needs-info, not Done.

**Server per tick:** start it (if down) and stop it after (only what we started) — see the `qa-server` skill.

**Factory ledger (each tick):** log tick boundaries and material events via
`scripts/factory_log.sh <slug> _loop tick_start run=<run-id>` at tick start and
`tick_end` at tick end; log per-ticket `verdict`, `transition`, `bug_filed`, and
`regression_reopen` events as they happen. Summarize offline with
`scripts/factory_status.sh <slug>`. Schema: `projects/<slug>/factory/schema.md`.
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
./scripts/stg_buildid.sh <slug> <merge-sha>
./scripts/server_ctl.sh <slug> status
./scripts/factory_status.sh <slug>
./scripts/run_automation.sh <slug> --stg
```

**Loop mechanics (agent):** use the `loop` skill (background sleeper + sentinel + `notify_on_output`); reset the
Playwright MCP browser at tick start (`browser_close` → navigate) to avoid the wedged-session no-op trap;
sanity-check interactivity (e.g. `/login` show-password toggle) before trusting "nothing works".
