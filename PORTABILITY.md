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

Example: product-specific factory tickets live in `projects/your-project/requirements/l5-tickets/` and
`projects/your-project/scripts/create_l5_jira_tickets.sh` — not in the shared engine.

## Splitting repos — link projects without symlinks

Three ways to attach a per-app project folder to the engine. **No `ln -s` required.**

### Repo layout rule

Scripts expect project files at `qa-agent/projects/<slug>/` (e.g. `project.yaml` at that path).
The **git root of a project repo should be the project folder itself**, not a parent that contains `<slug>/`:

```
# Good — clone/submodule into projects/your-project
projects/your-project/project.yaml
projects/your-project/project-memory.md
projects/your-project/runs/…

# Awkward — extra nesting (avoid for submodule target)
projects/project-bundle/your-project/project.yaml
```

If your repo wraps an extra folder (e.g. `parent-repo/your-project/`), publish a
**`qa-agent-project-your-project`** repo whose root *is* the `your-project/` tree, or use plain clone + rename (below).

---

### Option A — `git submodule` (recommended for teams)

Pins a project repo inside the engine at a fixed path:

```bash
git clone https://github.com/maksymbugaiov/qa-agent.git
cd qa-agent

# Project repo root = projects/<slug>/ layout (project.yaml at repo root)
git submodule add https://github.com/your-org/qa-agent-project-your-project.git projects/your-project
git submodule update --init --recursive
```

Teammates:

```bash
git clone --recurse-submodules https://github.com/maksymbugaiov/qa-agent.git
# or after a normal clone:
git submodule update --init
```

Update project data:

```bash
cd projects/your-project
git pull
cd ../..
```

### Option B — `git clone` into `projects/<slug>/`

Same result as submodule, but you manage the nested repo manually (no pin in engine's `main`):

```bash
git clone https://github.com/maksymbugaiov/qa-agent.git
cd qa-agent/projects

git clone https://github.com/your-org/qa-agent-project-your-project.git your-project
# your-project/ is now a normal git repo; engine scripts use projects/your-project/ as usual
```

Add `projects/your-project/` to the engine's `.gitignore` if you do not want the engine repo to track it as
untracked nested content — or use submodule (Option A) so the engine records the commit SHA.
The engine `.gitignore` already ignores `projects/*` except `projects/_template/` (Option B).

### Option C — sibling clones (no nesting)

Keep repos side by side; open the **parent folder** in Cursor so both are in one workspace:

```bash
mkdir my-workspace && cd my-workspace
git clone https://github.com/maksymbugaiov/qa-agent.git
git clone https://github.com/your-org/qa-agent-project-your-project.git your-project-data

# Copy or restructure so engine sees projects/your-project/ — one-time:
mkdir -p qa-agent/projects/your-project
cp -R your-project-data/* qa-agent/projects/your-project/    # if repo root is the project tree
```

Or init the project repo **from** `qa-agent/projects/<slug>` after `new_project.sh` and push that
folder as its own remote (common for greenfield apps).

---

### If your repo wraps an extra folder

Some local trees nest the project under a parent directory. Publish a repo whose **root** is the
project folder (`project.yaml` at top level):

```bash
cd path/to/your-project
git init
git remote add origin https://github.com/your-org/qa-agent-project-your-project.git
git add -A && git commit -m "Your project QA data"
git push -u origin main

# Then in engine:
cd qa-agent
git submodule add https://github.com/your-org/qa-agent-project-your-project.git projects/your-project
```

Non-project assets (decks, extra docs) can stay in a separate repo — not under `projects/your-project/`.

### Symlink (optional, local only)

Still valid for quick local dev, but not required:

```bash
ln -s ../../path/to/your-project qa-agent/projects/your-project
```

---

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

## New machine checklist (engine + project)

See **`SETUP.md` §14** for the full bootstrap. Short version:

```bash
# 1. Host (once): HOST_SETUP.md — Python, global skills, MCP
# 2. Engine
git clone https://github.com/maksymbugaiov/qa-agent.git && cd qa-agent
git submodule add <project-repo-url> projects/your-project && git submodule update --init
# 3. Secrets (local): copy *.example → .secrets/, fill jira/server/credentials
# 4. Cursor: open qa-agent/ as workspace
# 5. Verify: bash tests/run_tests.sh && ./scripts/jira_status.sh your-project
```

**Updates:** `git pull` in `qa-agent/` (engine) and `projects/your-project/` (project).  
**Contributions:** engine PRs → `qa-agent` repo; project data PRs → your project repo; never commit `.secrets/`.
