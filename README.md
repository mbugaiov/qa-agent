# Argus

**Argus** is the QA engine — this repository (`qa-agent`). An agent-driven **manual QA** workspace: feed it **business requirements**, point it at a **live web app**, and it designs test cases, executes them in a visible browser, captures evidence, and produces a Markdown + DOCX report — instead of a human tester doing it by hand.

> **Naming:** Argus is the high-level product name (presentation: *Argus · QA*). Low-level identifiers stay unchanged: folder `qa-agent/`, skills `qa-*`, factory ledger `agent=qa`.

Built as an orchestrator on top of existing QA skills (`qa-site-analysis`, `qa-test-execution`, `qa-report-generation`, `release-testing`, `docx-test-report`) **plus methodology integrated from `koldovsky/project-factory` and `openai/skills`**. It is **spec-driven**: business requirements are normalized into BDD scenarios (`SC-*`, Given/When/Then) from which test cases derive — chain `REQ → SC → TC → evidence`. Read **`SETUP.md`** to configure a project (Jira, creds, epic, server) and start your first run; **`AGENTS.md`** for the full loop; **`PORTABILITY.md`** for multi-repo layouts.

## One project = one folder · one task = one run

The **engine** (`AGENTS.md`, `templates/`, `scripts/`, `.cursor/skills/`, `.cursor/rules/`, `PORTABILITY.md`)
is shared and project-agnostic. Each **site** gets one folder under `projects/<slug>/` (created once).
Each **task** is a new **run** inside that project:

```
scripts/new_run.sh <slug> <type> "<task>"
  type: targeted | exploratory | regression | smoke | uat | full
  → projects/<slug>/runs/<YYYY-MM-DD>-<type>-<task>/
```

## Quickstart

> **Full setup guide:** **`SETUP.md`** — Jira, credentials, epic, server, loop, and pre-flight checklist.

1. **Create the project** (copies the skeleton from `projects/_template/`):

   ```bash
   scripts/new_project.sh myapp https://staging.myapp.com "My App"
   ```

2. **Add requirements** — any of:
   - drop `.docx` / `.pdf` / `.md` into `projects/myapp/requirements/`, or
   - paste requirements in chat (agent saves them to `projects/myapp/requirements/requirements.md`), or
   - pull from Jira/Confluence/Bitbucket via MCP.
   - put credentials in `projects/myapp/.secrets/` (gitignored).

3. **Run a task** — tell the agent what kind of task it is:

   > Run a **targeted** test on the login of `projects/myapp` after the latest release.
   > Run an **exploratory** session on the checkout of `projects/myapp`, 45 min.
   > Run a **full** acceptance on `projects/myapp`.

   The agent creates the run (`new_run.sh`), reads `project-memory.md`, executes the
   scope two-pass in the live browser, triages fails, writes `runs/<date>-<type>-<task>/`
   artifacts, generates the DOCX (for full/uat), and updates `project-memory.md`.

   **Continuous QA loop** (retest Jira queue + exploratory each tick) — in **Agent chat**, not Terminal:

   ```
   /loop 3600 AGENT_LOOP_WAKE_myappqa
   ```

   Replace `3600` with your interval in seconds (`21600` = 6h, `900` = 15m). See skill **`qa-loop`** for start/stop,
   one-off ticks, and project-specific sentinels (`AGENT_LOOP_WAKE_<purpose>`).

4. **Generate the DOCX report** (also runnable manually):

   ```bash
   python3 scripts/generate_docx_report.py projects/myapp/runs/<date>-<type>-<task>/report.md
   ```

5. **(Optional) Automate** — after manual verification, ask the agent to generate Playwright specs into `projects/myapp/automation/specs/`.

## Layout

| Path | Purpose |
|---|---|
| `SETUP.md` | **Start here** — project setup: Jira, creds, epic, server, first run |
| `AGENTS.md` | Lean portable spine: the loop + hard rules + skill index |
| `PORTABILITY.md` | Engine vs projects split; onboarding any new site |
| `HOST_SETUP.md` | Host machine setup: global QA skills, Python deps, MCP |
| `.cursor/skills/` | Procedural how-to (`qa-runs`, `qa-phases`, `qa-loop`, `qa-server`, `qa-jira`, `qa-security`, `token-efficient-ops`) |
| `.cursor/rules/` | Always-on constraints (`qa-engine`, `token-efficiency`, vendored `qa-team`) |
| `tests/run_tests.sh` | Engine self-tests (offline) — verify scripts, rules, skills, isolation, gating |
| `tests/smoke_clone.sh` | Fresh-clone smoke test — validates SETUP quickstart offline (`--local` to skip clone) |
| `INTEGRATIONS.md` | What external testing skills were folded in and from where |
| `templates/` | requirements, spec, test-case, bug-report, jira-task, loop-run, security-checklist, … |
| `scripts/new_project.sh` | Creates a new `projects/<slug>/` from the template (once per site) |
| `scripts/new_run.sh` | Creates a new task run inside a project (`<type>`) |
| `scripts/check_coverage.py` | Spec-driven coverage check: REQ → SC → TC gaps |
| `scripts/generate_docx_report.py` | Markdown report → DOCX |
| `scripts/jira_discover.py` | Discover a project's Jira ids (assignee, board, sprint, story-point/estimation fields) to fill `.secrets/jira.env` |
| `scripts/gh_auth_check.sh` | Gate: is `gh` logged in for git push/pull? (see `HOST_SETUP.md`) |
| `scripts/create_jira_issue.py` | File bugs/tasks into the project's Jira (Markdown → ADF; use `templates/jira-task.md` for tasks) |
| `templates/jira-task.md` | Jira Task description template: business context, Requirement, OpenSpec, Gherkin scenarios, acceptance criteria |
| `scripts/record_and_attach.sh` | Record a retest flow (Playwright), compress ≤10MB, attach to the Jira ticket, delete local copy |
| `scripts/factory_log.sh` | Append factory tick/ticket events to `projects/<slug>/factory/runs/*.jsonl` |
| `scripts/factory_status.sh` | Offline summary of factory ledger (open tickets, last failures) |
| `scripts/run_automation.sh` | Run project Playwright specs (`--stg`, `--url`, `--no-server`, or local via `server.env` + `server.manage`) |
| `automation/` | Shared Playwright guide + example config (CLI + specs) |
| `projects/_template/` | Per-project skeleton |
| `projects/<slug>/` | One site: `project.yaml`, `project-memory.md`, `requirements/`, `specs/` (BDD SC-*), `test-cases/`, `runs/<date>-<type>-<task>/`, `reports/`, `automation/specs/`, `.secrets/` |

## Requirements (tooling)

- A live browser MCP (document per project in `project-memory.md`; never headless for manual QA).
- Python 3 with `python-docx` and `requests`: `pip install python-docx requests`.
- `ffmpeg` + Playwright for retest recordings (`scripts/record_and_attach.sh`).
- Node + Playwright only if you opt into phase-2 automation.

Optional host-installed skills: `qa-site-analysis`, `qa-test-execution`, `qa-report-generation` (see **`HOST_SETUP.md`** and `PORTABILITY.md`).

## Principles (see `AGENTS.md` for the full list)

- Live, visible browser only.
- Two-pass execution on every case (real input + automation).
- Full traceability: requirement → test case → bug.
- A bug is confirmed only with evidence.
- Never commit secrets.
