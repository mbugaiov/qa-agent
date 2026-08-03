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
    script = (
        "github_create_issue.py"
        if provider == "github_issues"
        else "create_jira_issue.py"
    )
    cmd = [sys.executable, os.path.join(ROOT, "scripts", script), *argv]
    # Jira script does not understand --related-key / --no-dedupe — strip for jira path
    if script == "create_jira_issue.py":
        filtered: list[str] = []
        skip_next = False
        for i, a in enumerate(argv):
            if skip_next:
                skip_next = False
                continue
            if a in ("--related-key", "--no-dedupe"):
                if a == "--related-key":
                    skip_next = True
                continue
            if a.startswith("--related-key="):
                continue
            filtered.append(a)
        cmd = [sys.executable, os.path.join(ROOT, "scripts", script), *filtered]

    print(f"create_bug_issue → {script} (provider={provider})", file=sys.stderr)
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
