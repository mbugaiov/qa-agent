---
name: qa-code-review
description: Review qa-agent engine PRs before merge — run pre_merge_check, optional cursor-agent review with blocking gate, verify portability and no live project data. Use before opening a PR, after engine changes, or when the user asks for code review on qa-agent.
---

# QA Agent engine — code review

## When to use

- Before opening a PR on `qa-agent` (engine repo)
- After editing `scripts/`, `.cursor/skills/`, `.cursor/rules/`, `templates/`, `tests/`, `.github/`
- User asks "review my changes" / "CR this branch"

**Not this skill:** `qa-security` = live-app security testing. `review-security` / `review-bugbot` = Cursor subagents on local diffs (useful locally; CI uses `code-review.mdc` + `cursor-agent`).

## Step 1 — Automated gates (blocking)

From repo root:

```bash
bash scripts/pre_merge_check.sh
```

Runs:

1. `tests/run_tests.sh` — offline self-tests
2. `scripts/portability_check.sh` — no project-specific leaks in tracked files
3. `scripts/projects_isolation_check.sh` — only `projects/_template/` tracked
4. `scripts/check_review_gate_fixtures.sh` — review parser regression fixtures

## Step 2 — Agent review (PR / local)

### On GitHub PRs

Workflow `.github/workflows/code-review.yml` runs automatically when `CURSOR_API_KEY` is configured as a repo secret. It:

1. Runs `cursor-agent` with policy from `.cursor/rules/code-review.mdc`
2. Writes `review.md` and posts it as a PR comment
3. Fails the check if `scripts/check_review_gate.sh` finds blocking issues

Enable: GitHub repo → Settings → Secrets → `CURSOR_API_KEY` (CI key from Cursor dashboard).

### Local (same policy as CI)

```bash
export CURSOR_API_KEY=crsr_…   # or copy from projects/<slug>/.secrets/cursor.env
bash scripts/run_code_review.sh main
```

Review draft only (no agent):

```bash
bash scripts/check_review_gate.sh path/to/your-draft.md
bash scripts/check_review_gate_fixtures.sh   # parser regression
```

## CR auto-fix loop (mandatory when gate fails)

When **Code Review** is red or `check_review_gate.sh` fails:

```bash
# From open PR branch:
bash scripts/fetch_pr_review.sh          # or use local review.md
bash scripts/cr_autofix.sh --pr <N> --base main

# Or with review file already present:
bash scripts/cr_autofix.sh --review review.md --base main
```

The script runs `cursor-agent` to fix blockers, `pre_merge_check`, and re-review (max `CR_AUTOFIX_MAX=3`).

**On GitHub PRs:** job `autofix` in `code-review.yml` runs when review fails (max 2 attempts per job, max 2 `[cr-autofix]` commits per PR branch, then human).

**Rules:** read `.cursor/rules/cr-autofix.mdc` — never fake LGTM; never weaken gates.

## Step 3 — Diff-aware checklist

Read `.cursor/rules/code-review.mdc` and verify:

- [ ] **Projects isolation** — no `projects/<live-slug>/` in the diff (only `_template/`)
- [ ] **Portability** — no customer product names, private paths, real issue keys
- [ ] **Secrets** — nothing under `.secrets/` except `*.example`
- [ ] **Tests** — new scripts/skills have cases in `tests/run_tests.sh`
- [ ] **Docs** — `AGENTS.md` updated if skills/workflows changed
- [ ] **CI** — workflow changes use secrets, not inline tokens

## Step 4 — Factory ledger (optional, dev loop)

When reviewing app-repo PRs from the dev factory, log:

```bash
./scripts/factory_log.sh <slug> <TICKET> cr_pass merge_sha=<sha> --agent cr
# or
./scripts/factory_log.sh <slug> <TICKET> cr_block reason="…" --agent cr
```

Engine PRs typically do not use factory ledger unless tracing cross-repo work.

## Output format (reporting to user)

```markdown
## Code review — qa-agent

**Gates:** pass / fail
**Review gate:** pass / blocked
**Findings:** N block · N suggest

| Severity | Location | Finding |
|----------|----------|---------|
| Block | scripts/foo.sh:12 | … |

**Verdict:** merge-ready / needs fixes
```

## PR readiness

1. `bash scripts/pre_merge_check.sh` green locally
2. GitHub CI green (`ci.yml` + `code-review.yml` when secret configured)
3. PR template checklist complete (`.github/pull_request_template.md`)

## Not in scope

- Reviewing **target application** code — use that project's own CR pipeline
- Live QA / browser testing — skills `qa-loop`, `qa-test-execution`
