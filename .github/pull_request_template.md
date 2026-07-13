## Summary

<!-- What changed and why (1–3 sentences) -->

## Type

- [ ] Engine feature
- [ ] Bug fix
- [ ] Skills / rules / templates
- [ ] Tests / CI / code review

## Pre-merge checklist

- [ ] `bash scripts/pre_merge_check.sh` passes locally
- [ ] No live project data — only `projects/_template/` if touching `projects/`
- [ ] No project-specific leaks (product slugs, private paths, real Jira keys)
- [ ] No secrets or credentials in the diff
- [ ] New script/skill behavior covered in `tests/run_tests.sh`

## Test plan

- [ ] `bash tests/run_tests.sh`
- [ ] `bash scripts/portability_check.sh`
- [ ] `bash scripts/projects_isolation_check.sh`
- [ ] `bash scripts/check_review_gate_fixtures.sh` (if review parser changed)
- [ ] CI green on this PR

## Review notes

<!-- Optional: areas you want reviewers to focus on -->
