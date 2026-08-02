#!/usr/bin/env python3
"""Close a GitHub Issue after QA PASS (Done equivalent).

Usage:
    python3 scripts/github_close_issue.py --project projects/<slug> --key pantheon#12 \
        --comment "QA PASS — evidence …"
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import done_label, github_repo, validate_label  # noqa: E402


def parse_key(key: str) -> int:
    m = re.search(r"(\d+)$", key.strip())
    if not m:
        raise SystemExit(f"Cannot parse issue number from {key!r}")
    return int(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--comment", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    num = parse_key(a.key)
    vlabel = validate_label(a.project)
    dlabel = done_label(a.project)

    if a.dry_run:
        print(f"[dry-run] comment + close #{num}; −{vlabel} +{dlabel}")
        return 0

    owner, repo = github_repo(a.project)
    repo_ref = f"{owner}/{repo}"

    subprocess.run(
        ["gh", "issue", "comment", str(num), "-R", repo_ref, "--body", a.comment],
        check=True,
    )
    # Labels: done on, validate-testing off — fail if labels cannot be applied
    label_res = subprocess.run(
        [
            "gh",
            "issue",
            "edit",
            str(num),
            "-R",
            repo_ref,
            "--add-label",
            dlabel,
            "--remove-label",
            vlabel,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if label_res.returncode != 0:
        print(
            f"GITHUB_CLOSE_LABEL_FAIL {repo_ref}#{num}: {label_res.stderr or label_res.stdout}",
            file=sys.stderr,
        )
        return 1
    subprocess.run(
        ["gh", "issue", "close", str(num), "-R", repo_ref, "--reason", "completed"],
        check=True,
    )
    print(f"GITHUB_CLOSE_OK {repo_ref}#{num}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
