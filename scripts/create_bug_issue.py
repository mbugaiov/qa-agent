#!/usr/bin/env python3
"""Tracker-aware bug filing — routes to Jira or GitHub Issues.

Usage (same flags as create_jira_issue / github_create_issue where applicable):
    python3 scripts/create_bug_issue.py --project projects/<slug> \\
        --summary "…" --description-file … --severity S2 \\
        --labels <slug>,confirmed-defect --attach shot.png \\
        [--related-key <slug>#12]
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import tracker_provider  # noqa: E402

# Flags understood only by one backend — strip when routing to the other.
JIRA_ONLY = {
    "--issue-type",
    "--parent",
    "--no-parent",
    "--epic-link-field",
    "--points",
    "--estimate",
    "--no-sprint",
    "--no-assignee",
    "--on-hold",
    "--on-hold-transition",
    "--priority",
    "--set-priority",
    "--plain-description",
}
GITHUB_ONLY = {"--related-key", "--no-dedupe"}
# Flags that take a following value (not bare store_true)
VALUE_FLAGS = {
    "--issue-type",
    "--parent",
    "--epic-link-field",
    "--points",
    "--estimate",
    "--on-hold-transition",
    "--priority",
    "--related-key",
}


def filter_argv(argv: list[str], *, drop: set[str]) -> list[str]:
    out: list[str] = []
    skip_next = False
    for a in argv:
        if skip_next:
            skip_next = False
            continue
        key = a.split("=", 1)[0]
        if key in drop or a in drop:
            if key in VALUE_FLAGS and "=" not in a:
                skip_next = True
            continue
        out.append(a)
    return out


def main() -> int:
    argv = sys.argv[1:]
    project = ""
    for i, a in enumerate(argv):
        if a == "--project" and i + 1 < len(argv):
            project = argv[i + 1]
            break
        if a.startswith("--project="):
            project = a.split("=", 1)[1]
            break
    if not project:
        print("Usage: create_bug_issue.py --project projects/<slug> …", file=sys.stderr)
        return 2

    provider = tracker_provider(project)
    if provider == "github_issues":
        script = "github_create_issue.py"
        filtered = filter_argv(argv, drop=JIRA_ONLY)
    else:
        script = "create_jira_issue.py"
        filtered = filter_argv(argv, drop=GITHUB_ONLY)

    cmd = [sys.executable, os.path.join(ROOT, "scripts", script), *filtered]
    print(f"create_bug_issue → {script} (provider={provider})", file=sys.stderr)
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
