# <Project Name>

Per-project QA workspace. Same pattern as every other project — see the engine root
`../../AGENTS.md` for the workflow, `../../PORTABILITY.md` for engine vs projects split,
and `../../templates/` for artifact shapes.

## Layout
- `project.yaml` — target config (url, roles, requirement sources)
- `project-memory.md` — persistent context (quirks, active loop, coverage ledger, history)
- `requirements/` — source docs + extracted `REQ-*`
- `specs/` — BDD `SC-*` scenarios
- `test-cases/` — `TC-*` traced to requirements
- `runs/<YYYY-MM-DD>-<type>-<task>/` — one folder per task or loop engagement
- `reports/` — final DOCX
- `automation/` — Playwright package (`specs/`, `helpers/`; phase 2)
- `factory/` — optional factory event ledger (`schema.md`, `runs/*.jsonl`)
- `scripts/` — optional project-only helpers (not in the shared engine)
- `.secrets/` — credentials (gitignored; copy from `*.example`)

## Run
From the engine root:
```bash
scripts/new_run.sh <slug> <type> "<task title>"
```
Or ask the agent: "Run a **targeted** test on `projects/<slug>` …"
