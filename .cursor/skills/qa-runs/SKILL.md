---
name: qa-runs
description: How the QA Agent structures projects and runs — one project = one site folder (projects/<slug>/), one task = one dated run; run types (targeted/exploratory/regression/smoke/uat/full) and how to start an engagement. Use when creating a project/run or deciding run scope.
---

# Projects, runs, and run types

## One project = one folder (the pattern that stays constant)

Every site becomes a self-contained folder under `projects/<slug>/`, created from `projects/_template/`
via `scripts/new_project.sh <slug> <url> "<Name>"`. The **engine** (`AGENTS.md`, `templates/`, `scripts/`,
`.cursor/skills/`, `.cursor/rules/`, `qa-team.mdc`) is shared and never duplicated — every project runs the
same loop/artifacts.

```
projects/<slug>/
  project.yaml          target config (url, roles, requirement sources, jira: block)
  project-memory.md     persistent context across runs (quirks, known bugs, history)
  requirements/         source docs + extracted REQ-*
  specs/<capability>.md SC-* BDD scenarios (Given/When/Then), traced to REQ
  test-cases/           TC-* derived from SC, traced to REQ
  runs/<YYYY-MM-DD>-<type>-<task>/   one TASK = one run (logs, qa-pack, screenshots)
  reports/              final DOCX
  automation/specs/     Playwright specs (phase 2)
  .secrets/             credentials (gitignored: jira.env, server.env, creds)
```

## Project vs run

- **Project = the site.** Created **once** (`new_project.sh`). Slug never changes. Holds requirements, specs, test-cases, memory.
- **Run = one task.** Many per project. Each task — point check, exploratory session, regression, release
  sign-off — is a new run folder, never a new project: `scripts/new_run.sh <slug> <type> "<task title>"`
  → `projects/<slug>/runs/<YYYY-MM-DD>-<type>-<task-slug>/`.

### Continuous loop runs (special case)

A **recurring L5 QA loop** is still one run — but **rotate the run folder** when:
- the dated folder name no longer reflects the engagement (e.g. loop ran for weeks under one date), or
- scope materially changes (new epic, release sign-off, major policy shift), or
- `run.md` iteration log grows unwieldy (~200+ lines).

On rotation: (1) mark the old run **ARCHIVED** in its `run.md` header; (2) `new_run.sh` for the new loop;
(3) move durable state (coverage ledger, cadence, active-loop pointer, quirks) into **`project-memory.md`**
(use sections from `_template/project-memory.md`); (4) seed loop headers from `templates/loop-run.md` if helpful;
(5) keep iteration history in the archived run — don't delete it. **Not every 60m tick** gets a new folder.

## Run types (what each produces)

| Type | When | Scope | Artifacts created |
|---|---|---|---|
| `targeted` | point test of one feature / a few REQ | subset of cases | `run.md`, `execution-log.md`, (bug-report), report |
| `exploratory` | charter-driven, time-boxed probing | a charter, no fixed TC list | `run.md`, `exploratory-session.md`, (bug-report) |
| `regression` | re-verify previously failed/fixed cases | prior cases + carry-over bugs | `run.md`, `execution-log.md` |
| `smoke` | quick "is it up / core flow works" | P0 happy paths only | `run.md`, `execution-log.md` |
| `uat` | triage a batch of reported bugs | one verdict per reported bug | `run.md`, `execution-log.md`, full qa-pack |
| `full` | release / acceptance | everything | `run.md` + full QA proof pack |

`new_run.sh` seeds exactly the artifacts the type needs; the loop scales to the run's scope.

## Starting a new engagement

1. If the project doesn't exist: `scripts/new_project.sh <slug> <base_url> "<Name>"` (once per site).
2. Create the task's run: `scripts/new_run.sh <slug> <type> "<task>"`.
3. **Read `projects/<slug>/project-memory.md` first** — apply known quirks/bugs, don't rediscover them.
4. Fill `run.md` scope, run the loop, write all artifacts under the run folder.
5. At the end, **update `project-memory.md`** (run history row, new quirks, carry-over bugs).
