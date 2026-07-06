---
name: qa-phases
description: Detailed per-phase how-to for the QA Agent loop (Phase 1 Ingest → 2 Spec/BDD → 3 Analyse → 4 Design+traceability → 5 Execute two-pass → 6 Triage → 7 Report+proof-pack → 9 Automation) plus the spec layer. Use when executing any loop phase against an app.
---

# Loop phases (detail)

`<run>` = `projects/<slug>/runs/<YYYY-MM-DD>-<type>-<task>/`.

**Spec layer (lightweight spec-driven testing).** Scenarios `SC-*` bridge requirements and concrete tests.
NOT OpenSpec capability specs (no `openspec validate`, deltas, change folders — we test a black-box app we
don't own). They ARE testable Given/When/Then acceptance criteria, authored once per project (`specs/`),
reused by every run. Chain: **REQ → SC → TC → evidence**. Tiny `targeted`/`smoke` runs may select existing
SCs; `exploratory` runs may work charter-only and feed new SC ideas back afterward.

### Phase 1 — Requirement sources (situational)
1. **Files** — drop `.docx`/`.pdf`/`.md` into `projects/<slug>/requirements/`; read them; extract every testable statement.
2. **Chat text** — capture pasted requirements into `requirements/requirements.md` for reproducibility.
3. **External** — Jira/Confluence/Bitbucket via MCP (check the tool schema first).
Output: numbered `REQ-001 … REQ-NNN`. Every scenario traces to ≥1 REQ.

### Phase 2 — Spec (BDD scenarios)
Normalize each `REQ-*` into `SC-*` (Given/When/Then) grouped by capability in `specs/<capability>.md`
(`templates/spec.md`). Each `SC-*` lists the `REQ-*` it **Covers**. Surface ambiguities (flag, don't guess).

### Phase 3 — Analyse (live browser, MANDATORY)
Use the live browser MCP, visible beside the chat (`position: "side"`, lock/unlock). Never headless.
Map the site per `qa-site-analysis`. Reuse the map from `project-memory.md` if fresh.

### Phase 4 — Design cases (from scenarios) + traceability
For every in-scope `SC-*`, derive cases (happy/edge/negative/a11y/responsive) using `release-testing`
techniques (EP, BVA, State Transition, Decision Table, CRUD, Error Guessing). `templates/test-case.md`;
each `TC-<FEATURE>-<NNN>` has a `Scenario:` + `REQ:` line. Run `python3 scripts/check_coverage.py
projects/<slug>` (no REQ without SC, no SC without TC). (full/uat) build the traceability matrix →
`<run>/traceability-matrix.md`. Inverse check: any app behaviour with NO backing requirement = scope drift → flag.

### Phase 5 — Execute (two-pass, MANDATORY)
Per `qa-team.mdc`: Pass 1 real input (`browser_type` + click by coords — fires blur/focus/change),
Pass 2 automation (`browser_fill` + click by ref). Agree → record confidently; disagree → record both,
trust Pass 1. Log to `<run>/execution-log.md`. On FAIL: screenshot + console + network → `templates/bug-report.md`.
5b. (exploratory) charter-driven, time-boxed → `<run>/exploratory-session.md` (no fixed TC list).

**Browser hygiene (every session):** reset a wedged MCP browser with `browser_close` → fresh navigate;
sanity-check interactivity (e.g. a toggle or button that must respond) before trusting "nothing works".
**Server actions / RSC:** if MCP `browser_click` no-ops on submit/lifecycle buttons, drive via native
`.click()` in `browser_evaluate` — document app-specific patterns in `project-memory.md`.
**Pointer drag (dnd-kit, etc.):** HTML5 `browser_drag` often fails — verify via action buttons, Playwright
specs, or manual; note inconclusive automation in the log.

### Phase 6 — Triage every FAIL (bug-triage-analyst)
1. **Map** the governing requirement (none ⇒ requirements-gap finding). 2. **Trace** where it arises.
3. **Verdict**: `confirmed-defect` / `works-as-specified` / `environment` / `cannot-reproduce` (+ confidence).
4. **Root cause + class** (mechanism-specific; list other locations with the same latent bug).
5. **Regression idea** referencing the bug id. `works-as-specified` is NOT a bug — quote the requirement.

### Phase 7 — Report + QA proof pack
`qa-report-generation` → `<run>/report.md`. (full/uat) proof pack into `<run>/`: traceability-matrix,
manual-test-plan, risk-register, acceptance-report. Final DOCX via `docx-test-report` standards →
`scripts/generate_docx_report.py <run>/report.md` → `reports/`.

### Phase 9 — Automation (optional, manual-first)
Only after manual verification: generate Playwright specs into `projects/<slug>/automation/specs/`
mirroring verified TC ids (each `SC-*` maps to a spec/feature), or use the Playwright CLI
(`automation/README.md`). Every confirmed defect gets a regression test referencing its bug id.
