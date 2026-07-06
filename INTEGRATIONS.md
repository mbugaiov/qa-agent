# Integrations — external testing skills folded into QA Agent

This documents which **testing** skills/agents from external sources were studied
and what was integrated into this project. We adopted the *methodology* (templates,
rules, workflow steps) rather than vendoring large files, so the project stays
self-contained and agent-agnostic.

## Sources reviewed

| Source | Testing content found | Integrated? |
|---|---|---|
| [`koldovsky/project-factory`](https://github.com/koldovsky/project-factory) | `test-engineer`, `qa-documenter`, `bug-triage-analyst`, `spec-compliance-auditor`, `requirements-analyst`, `quality-gates` (G6/G8), `qa-pack` template | ✅ Yes (primary) |
| [`openai/skills`](https://github.com/openai/skills) | `.curated/playwright`, `.curated/playwright-interactive`, `screenshot`, `security-*` | ✅ Playwright (CLI automation) |
| [`vercel-labs/agent-skills`](https://github.com/vercel-labs/agent-skills) | only `react-best-practices` (dev, not QA); rest is the repo's own test suite | ❌ Not QA |
| [`orchestra-research/AI-research-SKILLs`](https://github.com/orchestra-research/AI-research-SKILLs) | ML research / model `evaluation` (lm-eval-harness etc.), not app QA | ❌ Out of scope |
| `CyberAlbSecOP/Awesome_GPT_Super_Prompting` | prompt-injection / jailbreak collections | ❌ Not testing methodology |

## What was integrated (from `koldovsky/project-factory`)

| Concept | Origin agent | Landed in |
|---|---|---|
| **Requirements traceability matrix** — REQ → capability → tests → evidence, no empty cells | `qa-documenter` | `templates/traceability-matrix.md`, AGENTS.md Phase 3 |
| **Bug triage verdicts** — `confirmed-defect` / `works-as-specified` / `environment` / `cannot-reproduce` + confidence | `bug-triage-analyst` | `templates/bug-report.md`, AGENTS.md Phase 5 |
| **Root-cause + class** — mechanism-specific cause, list other locations with same latent bug | `bug-triage-analyst` | `templates/bug-report.md` |
| **Regression rule** — every fixed bug gets a test referencing the bug id | `test-engineer` | AGENTS.md Phase 7 + hard rules |
| **QA proof pack** — manual test plan, risk register, acceptance report | `qa-pack` template | `templates/manual-test-plan.md`, `risk-register.md`, `acceptance-report.md` |
| **Scope-drift / inverse check** — tested behaviour with no requirement is flagged | `spec-compliance-auditor` | AGENTS.md Phase 3 + traceability matrix |
| **Negative-case discipline** — locale decimals, oversized, blanks, RBAC denial, referential deletes | `qa-pack` / `test-engineer` | `templates/manual-test-plan.md` |

## What was integrated (from `openai/skills`)

| Concept | Origin | Landed in |
|---|---|---|
| **CLI browser driving** — open → snapshot → interact by ref → re-snapshot → capture | `.curated/playwright` | `automation/README.md` |
| **Interactive snapshot/ref workflow** — stable refs, re-snapshot on stale | `.curated/playwright-interactive` | `automation/README.md` |

> Note: the **manual** two-pass execution still uses the live `cursor-ide-browser`
> MCP (human-visible, per `qa-team.mdc`). The OpenAI Playwright CLI is for *scripted*
> automation in phase 2, complementary — not a replacement.

## Deliberately NOT adopted

- project-factory's heavy CI/ratchet machinery (coverage-ratchet, eval-ratchet,
  git-hook gates, OpenSpec) — that's for a full SDLC build pipeline, not a
  standalone manual-QA-by-requirements agent. We kept the QA-facing parts (G6
  proof pack, G8 UAT triage) and dropped the build-system parts.
- Vendoring full SKILL.md files — we reference upstream and adopt the methodology
  so the project stays light and agent-agnostic.
