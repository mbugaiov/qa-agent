#!/usr/bin/env bash
# Gate: is GitHub CLI authenticated for git push/pull on this machine?
#
# Tokens live in the OS keyring via `gh` — never in qa-agent .secrets/.
# One-time setup: gh auth login && gh auth setup-git  (see HOST_SETUP.md)
#
# Exit 0 = logged in (prints account + protocol)
# Exit 1 = gh installed but not logged in
# Exit 2 = gh not installed
#
# Usage: scripts/gh_auth_check.sh
set -uo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "inactive (gh not installed — brew install gh, then gh auth login)"
  exit 2
fi

if ! gh auth token -h github.com >/dev/null 2>&1; then
  echo "inactive (run: gh auth login -h github.com && gh auth setup-git)"
  exit 1
fi

USER=$(gh api user -q .login 2>/dev/null || true)
PROTO=$(gh config get git_protocol -h github.com 2>/dev/null || echo "https")
[[ -n "$USER" ]] && echo "active ($USER @ github.com, git protocol: $PROTO)" || echo "active (github.com, git protocol: $PROTO)"
exit 0
