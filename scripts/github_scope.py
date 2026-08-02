#!/usr/bin/env python3
"""Query GitHub Issues for QA retest scope (label validate-testing).

Usage:
    python3 scripts/github_scope.py --project projects/<slug>
    python3 scripts/github_scope.py --project projects/<slug> --json
    python3 scripts/github_scope.py --project projects/<slug> --shell
    python3 scripts/github_scope.py --project projects/<slug> --log --shell
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import (  # noqa: E402
    github_repo,
    validate_label,
)


def log_scope_check(slug: str, keys: list[str]) -> None:
    script = os.path.join(ROOT, "scripts", "factory_log.sh")
    subprocess.run(
        [script, slug, "_loop", "scope_check", f"keys={','.join(keys)}", f"count={len(keys)}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--shell", action="store_true")
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()

    slug = os.path.basename(a.project.rstrip("/"))
    owner, repo = github_repo(a.project)
    label = validate_label(a.project)
    repo_ref = f"{owner}/{repo}"

    # List open issues; filter label client-side.
    # Note: `gh issue list --label X` can miss newly labeled issues; open+filter is reliable.
    raw = subprocess.check_output(
        [
            "gh",
            "issue",
            "list",
            "-R",
            repo_ref,
            "--state",
            "open",
            "--json",
            "number,title,state,labels",
            "--limit",
            "100",
        ],
        text=True,
    )
    items = json.loads(raw) if raw.strip() else []
    open_items = [
        i
        for i in items
        if str(i.get("state", "")).lower() == "open"
        and any(l.get("name") == label for l in (i.get("labels") or []))
    ]
    open_items.sort(key=lambda i: int(i["number"]))

    keys = [f"{slug}#{i['number']}" for i in open_items]
    issues = [
        {
            "key": f"{slug}#{i['number']}",
            "summary": i.get("title", ""),
            "status": "validate-testing",
        }
        for i in open_items
    ]
    jql = f"github:{repo_ref} label:{label} is:open"

    if a.log:
        log_scope_check(slug, keys)

    if a.json:
        print(json.dumps({"keys": keys, "count": len(keys), "jql": jql, "issues": issues}))
        return 0

    if a.shell:
        # Match jira_scope --shell exports
        print(f"count={len(keys)}")
        print(f"SCOPE_COUNT={len(keys)}")
        print(f"keys={shlex.quote(','.join(keys))}")
        print(f"SCOPE_KEYS={shlex.quote(','.join(keys))}")
        print(f"jql={shlex.quote(jql)}")
        return 0

    print(f"keys={','.join(keys)}")
    print(f"count={len(keys)}")
    print(f"jql={jql}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
