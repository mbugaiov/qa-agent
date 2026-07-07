# QA Agent — host setup

The **engine repo** (`qa-agent/`) is self-contained for scripts, templates, rules, and engine skills.
Some capabilities depend on **host-installed** tools and skills on each developer machine.

## Required

| Dependency | Purpose | Install |
|---|---|---|
| Python 3 | Scripts (Jira, DOCX, coverage) | System Python or `pyenv` |
| `python-docx`, `requests` | Report generation, Jira API | `pip install python-docx requests` |
| Browser MCP | Live visible manual QA | Enable in Cursor (e.g. `cursor-ide-browser` or `user-playwright`) |

Document the chosen browser MCP in each project's `project-memory.md`.

## Recommended — global QA phase skills

These three skills are **orchestrated** by `AGENTS.md` / `qa-phases` but are **not vendored** in the engine repo.
Install once per machine under `~/.cursor/skills/`:

| Skill | Phase | Path |
|---|---|---|
| `qa-site-analysis` | 3 — site map + test-case design | `~/.cursor/skills/qa-site-analysis/SKILL.md` |
| `qa-test-execution` | 5 — two-pass browser execution | `~/.cursor/skills/qa-test-execution/SKILL.md` |
| `qa-report-generation` | 7 — structured MD report | `~/.cursor/skills/qa-report-generation/SKILL.md` |

**Install options:**

1. Copy the skill folders from an existing machine into `~/.cursor/skills/`
2. Publish to `skills.sh` and install: `npx skills add <owner/repo@skill> -g -y` (when available)

Without these skills, the agent can still use engine skills (`qa-runs`, `qa-phases`, etc.) but must
read equivalent methodology from `templates/` and `.cursor/rules/qa-team.mdc`.

## Optional

| Dependency | Purpose | Install |
|---|---|---|
| `ffmpeg` | Retest video compression (`record_and_attach.sh`) | `brew install ffmpeg` / system package |
| Node.js + npm | Phase-2 Playwright automation | `node` LTS + `npm install` in `projects/<slug>/automation/` |
| `release-testing` | Deeper acceptance techniques | External squad skill (optional) |
| `docx-test-report` | Alternative DOCX path | External squad skill (optional; engine has `generate_docx_report.py`) |
| `salesforce-fsl-testing` | Playwright patterns reference | `~/.cursor/skills/salesforce-fsl-testing` (optional) |

## Per-project setup (after `new_project.sh`)

See **`SETUP.md`** sections 4–8 for `project.yaml`, credentials, Jira epic, server, and `project-memory.md`.

Quick copy:

```bash
scripts/new_project.sh <slug> <base_url> "<Display Name>"

# Copy and fill secrets (gitignored):
cp projects/<slug>/jira.env.example projects/<slug>/.secrets/jira.env
cp projects/<slug>/server.env.example projects/<slug>/.secrets/server.env
cp projects/<slug>/.secrets/credentials.json.example projects/<slug>/.secrets/credentials.json

# Discover Jira field ids (if Jira enabled):
python3 scripts/jira_discover.py <slug>
./scripts/jira_status.sh <slug>    # expect: active
```

## Workspace layouts

| Layout | Setup |
|---|---|
| Standalone | Open `qa-agent/` as Cursor workspace |
| Sibling app | `myapp/` + `qa-agent/` in one parent folder |
| Engine in app repo | `git submodule add <qa-agent-repo> qa-agent` inside app repo |
| Project in engine | `git submodule add <project-repo> projects/<slug>` — see **`SETUP.md` §13**, **`PORTABILITY.md`** |
| Symlink rules (optional) | `ln -s ../qa-agent/.cursor .cursor` in app workspace |

See **`PORTABILITY.md`** for engine vs per-project repo split.

## Verify engine

```bash
bash tests/run_tests.sh
```

Exit 0 = engine scripts, skills, rules, and gating behave correctly (offline).
