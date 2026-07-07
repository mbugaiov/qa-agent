# QA Agent — Manual Testing by Business Requirements

The agent runs **manual QA against a live web app, driven by business requirements**, instead of a
human tester: ingest requirements → derive scenarios + test cases → execute in a **live browser** →
triage → report → (optional) file to Jira with evidence. One project = one site; one task = one run.

> Operating role: follow `.cursor/rules/qa-team.mdc` (vendored) and the engine constraints in
> `.cursor/rules/qa-engine.mdc` + `token-efficiency.mdc` (always-on). This file is the portable **spine**;
> procedural detail lives in **skills** under `.cursor/skills/`. See **`PORTABILITY.md`** for engine vs
> projects split when moving to a separate repo.

## Skills (the how-to, read on demand)

| When you're doing… | Skill (`.cursor/skills/…/SKILL.md`) |
|---|---|
| Projects, runs, run types, starting an engagement | `qa-runs` |
| The detailed per-phase how-to (Phase 1–9, spec layer) | `qa-phases` |
| A recurring/continuous QA loop tick | `qa-loop` |
| Starting/stopping the app under test | `qa-server` |
| Filing/validating in Jira (+ recordings, fields, isolation) | `qa-jira` |
| Live-app security testing (rotating slice, loop + standalone) | `qa-security` |
| Least-token way to do any op (Jira/Bitbucket/git/testing) | `token-efficient-ops` |
| Security checklist categories (reference) | `templates/security-checklist.md` |
| Always-on hard constraints | rules `.cursor/rules/qa-engine.mdc` + `token-efficiency.mdc` + `qa-team.mdc` |
| What external methodology was integrated and from where | `INTEGRATIONS.md` |
| Engine vs projects repo split, onboarding any new site | `PORTABILITY.md` |
| Host machine setup (global skills, Python, MCP) | `HOST_SETUP.md` |
| Project setup (Jira, creds, epic, server, start) | `SETUP.md` |

## Skills this project orchestrates

| Phase | Skill | Location |
|---|---|---|
| Ingest + design | `qa-site-analysis` | `~/.cursor/skills/qa-site-analysis` |
| Execute | `qa-test-execution` | `~/.cursor/skills/qa-test-execution` |
| Report (md) | `qa-report-generation` | `~/.cursor/skills/qa-report-generation` |
| Acceptance depth + techniques | `release-testing` (optional, external) | install separately if available |
| Report (DOCX) | `docx-test-report` (optional, external) | engine includes `scripts/generate_docx_report.py` |
| Automation (phase 2) | `salesforce-fsl-testing` (Playwright patterns) | `~/.cursor/skills/salesforce-fsl-testing` |

**Always read the relevant SKILL.md before the phase that uses it.** Read them, don't just reference them.

## The loop (run this for every engagement)

> `<run>` = `projects/<slug>/runs/<YYYY-MM-DD>-<type>-<task>/`. Phases adapt to the run type.
> Per-phase detail: skill `qa-phases`. Project/run setup: skill `qa-runs`.

```
0. Setup    → new_project.sh (once) + new_run.sh; read project.yaml + project-memory.md; (if needed) start server
1. Ingest   → ensure REQ-* exist/are current (skip if memory has them and scope is known)
2. Spec     → normalize REQ-* into BDD scenarios SC-* (Given/When/Then) in projects/<slug>/specs/
3. Analyse  → qa-site-analysis: map site/flows (live browser); reuse fresh map from memory
4. Design   → derive/select TC-* FROM scenarios for THIS run's scope; check_coverage.py; (full/uat) traceability matrix
5. Execute  → qa-test-execution two-pass per case → <run>/execution-log.md  (5b exploratory → exploratory-session.md)
6. Triage   → every FAIL: verdict + root cause + class + regression idea → bug-report.md
7. Report   → qa-report-generation → <run>/report.md; (full/uat) + QA proof pack
8. DOCX     → scripts/generate_docx_report.py <run>/report.md → reports/<slug>-QA-Report-<YYYYMMDD>.docx
9. (opt)    → automation: Playwright specs / CLI from the verified cases
10. Memory  → update projects/<slug>/project-memory.md (history, quirks, carry-over bugs); stop server if we started it
```

For **recurring** loops (retest the Jira queue + fresh exploratory each tick), follow skill `qa-loop`.
For **security**, follow skill `qa-security` on **`exploratory`** and **`regression`** runs — not each loop tick.

## Hard rules

- Live, visible browser only — never headless.
- Two-pass execution on every case.
- Spec-driven chain holds: **REQ → SC → TC → evidence** (run `check_coverage.py`; traceability matrix has no empty cells without a reason).
- A bug is CONFIRMED only with evidence (screenshot of error state, or captured 5xx) — never from body-text matching "500".
- A "consistency" fix is PASS only when the displayed VALUE matches the canonical source (detail/DB/API), not just that views agree.
- Every FAIL gets a triage verdict; `works-as-specified` is not a bug — quote the requirement.
- Every confirmed defect gets a regression test referencing its bug id.
- Scope drift (tested behaviour with no requirement) is flagged, never silently accepted.
- **Per-project isolation**: a project uses ONLY its own `projects/<slug>/.secrets/*` — never another project's settings.
- **Jira gating**: no `.secrets/jira.env` (or placeholders) ⇒ run Jira-free; never error (`scripts/jira_status.sh`).
- Never commit secrets — they live in gitignored `projects/<slug>/.secrets/`.
- Report is not "done" until full acceptance coverage exists — smoke passing ≠ accepted.

## Output layout (never put run output in chat-only)

```
qa-agent/                       ← shared ENGINE: AGENTS.md  PORTABILITY.md  .cursor/{skills,rules}  templates/  scripts/
  projects/
    _template/                  ← skeleton copied by new_project.sh (any new site)
    <slug>/                     ← one project = one folder (may live in a separate repo)
```
