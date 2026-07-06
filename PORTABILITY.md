# QA Agent — portability (engine vs projects)

The **engine** is everything needed to run QA on **any** web app. **Project data** is per-site and
may live in a separate repo or monorepo subtree.

## What ships in the engine repo

```
qa-agent/
  AGENTS.md                 portable spine (loop + index)
  PORTABILITY.md            this file
  INTEGRATIONS.md           external methodology sources
  .cursor/
    rules/                  qa-engine, token-efficiency, qa-team (vendored)
    skills/                 qa-runs, qa-phases, qa-loop, qa-server, qa-jira, token-efficient-ops
  templates/                artifact shapes (run, bug-report, jira-task, security-checklist, …)
  scripts/                  slug-parameterized CLI (new_project, new_run, server_ctl, jira_*, …)
  tests/run_tests.sh        offline self-tests
  automation/               Playwright patterns (optional phase 2)
  projects/
    _template/              skeleton copied for every new site
```

**Rule:** engine files must not hardcode a project slug, Jira key, product name, or app-specific routes.
Use `projects/<slug>/` paths, placeholders (`<EPIC-KEY>`, `<PRODUCT>`), and per-project `.secrets/`.

## What stays per project (not in the engine)

```
projects/<slug>/
  project.yaml              target URL, roles, jira block
  project-memory.md         quirks, active loop pointer, coverage ledger, run history
  .secrets/                 jira.env, server.env, credentials (gitignored)
  requirements/ specs/ test-cases/
  runs/<date>-<type>-<task>/   one folder per task or loop engagement
  reports/
  automation/specs/
  scripts/                  optional project-only helpers (e.g. bulk Jira import)
```

Example: LRM factory tickets live in `projects/lrm/requirements/l5-tickets/` and
`projects/lrm/scripts/create_l5_jira_tickets.sh` — not in the shared engine.

## Onboarding a new project

```bash
scripts/new_project.sh <slug> <base_url> "<Display Name>"
# Fill projects/<slug>/.secrets/jira.env + server.env (copy from *.example)
python3 scripts/jira_discover.py <slug>    # if Jira enabled
scripts/new_run.sh <slug> <type> "<task>"  # targeted | exploratory | regression | smoke | uat | full
```

Read `projects/<slug>/project-memory.md` first every engagement. Update it at the end.

## Continuous QA loop

- One **loop engagement** = one run folder (`exploratory` type is typical).
- **Rotate** the run folder when the date is stale, scope shifts, or logs grow large — see skill `qa-runs`.
- Durable loop state (active run pointer, cadence, coverage ledger, On Hold exclusions) → `project-memory.md`.
- Tick iteration logs → current run's `run.md`.

## Optional host dependencies

Install separately (not vendored in the engine):

| Dependency | Purpose |
|---|---|
| `~/.cursor/skills/qa-site-analysis` | Phase 3 site mapping |
| `~/.cursor/skills/qa-test-execution` | Phase 5 two-pass execution |
| `~/.cursor/skills/qa-report-generation` | Phase 7 report |
| Browser MCP (`cursor-ide-browser` or `user-playwright`) | Live visible browser — document choice in `project-memory.md` |
| `python-docx`, `requests`, `ffmpeg`, Playwright | Reports, Jira, recordings, automation |

The engine works without Jira (Jira-free no-op) and without server autostart (`server.manage: false`).

## Splitting repos

1. **Engine repo** — `qa-agent/` tree above, minus `projects/lrm/` (and any other live projects).
2. **Projects repo** — `projects/<slug>/` folders only; depends on engine via path or submodule.
3. Point Cursor at the engine's `.cursor/rules` + `.cursor/skills` (or symlink into the workspace).

After any engine change: `bash tests/run_tests.sh` must stay green.
