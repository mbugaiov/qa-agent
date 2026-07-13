---
name: qa-test-data
description: Test data preparation and cleanup before/after QA execution — create isolated fixtures, run tests, tear down. Use when assign/relocate/lifecycle tests need available stations, when shared STG is congested, or when the user asks about test setup/teardown.
---

# Test data — prepare before, clean up after

**Rule:** A test that fails because shared STG has no free station is **BLOCKED_SETUP**, not a product **FAIL**. Prep data first; only then record PASS/FAIL.

Do **not** skip prep and blame the app. Do **not** rush Jira Done based on a single ad-hoc pass without cleanup.

## When prep is required

| Feature area | Minimum prep |
|--------------|--------------|
| Assign / schedule | ≥1 **available compatible** station (or accept busy + window) |
| Relocate / multi-station flows | ≥2 **different** compatible stations — assign on A, move to B |
| Full lifecycle PF-02 | Usually works on fresh request if any slot free; on congested STG run prep first |
| Regression on shared STG | Cancel stale `PF lifecycle` / `QA-TST` requests from prior runs |

**Local :3100 / e2e.db:** `server_ctl sync` resets DB — prep optional unless testing against dirty state.

**Shared STG:** prep **mandatory** for relocate and for assign when board shows all stations busy.

## Workflow (every feature retest)

```
1. PREP   → scripts/test_data_prep.sh <slug> [--stg]
2. TEST   → manual steps / automation / two-pass MCP
3. CLEAN  → scripts/test_data_cleanup.sh <slug> [--stg] [--manifest]
4. LOG    → note prep manifest + cleanup result in run.md / Jira comment
```

Prep writes a manifest: `projects/<slug>/.test-data/manifest.json` (gitignored).

## Verdict mapping

| Situation | Verdict | Jira action |
|-----------|---------|-------------|
| Prep not run; no available station | **BLOCKED_SETUP** | Comment only — do not FAIL product |
| Prep run; feature still broken | **FAIL** | In Progress + bug |
| Prep run; feature works; no recording | **PASS (pending recording)** | Stay In Progress until recording attached |
| Prep run; full DoD met | **DONE** | Auto-Done per `qa-jira` |

## Project-specific playbooks

Read `projects/<slug>/test-data.md` if it exists (project-specific naming and prep rules).

## Scripts

```bash
# Create QA stations + manifest (STG or local via run_automation base URL)
./scripts/test_data_prep.sh <slug> --stg

# Cancel QA requests + delete prefixed test stations from manifest
./scripts/test_data_cleanup.sh <slug> --stg

# Prep only (no cleanup) — e.g. before manual testing
./scripts/test_data_prep.sh <slug> --stg --stations 2

# Cleanup all prefixed test stations visible on Stations page (no manifest)
./scripts/test_data_cleanup.sh <slug> --stg --all-qa-prefix
```

Underlying Playwright specs: `projects/<slug>/automation/specs/test-data-prep.spec.js` and `test-data-cleanup.spec.js`.

## Naming conventions

Define per project in `projects/<slug>/test-data.md` (prefixes for stations/requests, roles, equipment flags). Do not reuse production fixture names on shared STG when prep is required.

## Loop ticks

Prep/cleanup is **not** required on every monitor tick. Run prep when a scope ticket's DoD needs assign/relocate/lifecycle write verification that shift. Do not change loop cadence or force Done from one corrected manual run.
