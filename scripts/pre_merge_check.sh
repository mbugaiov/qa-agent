#!/usr/bin/env bash
# Pre-merge gate for qa-agent engine PRs.
#
# Usage: scripts/pre_merge_check.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Engine self-tests"
bash tests/run_tests.sh

echo "==> Portability check"
bash scripts/portability_check.sh

echo "==> Projects isolation check"
bash scripts/projects_isolation_check.sh

echo "==> Review gate fixtures"
bash scripts/check_review_gate_fixtures.sh

echo "pre_merge_check: OK"
