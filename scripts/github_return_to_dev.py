#!/usr/bin/env python3
"""Return validate-testing GitHub Issue to Hephaestus (QA RETURN).

Usage:
    python3 scripts/github_return_to_dev.py --project projects/<slug> --key <slug>#12 \
        --reason "…" --steps-tried "…"
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import github_repo, pickup_label, validate_label  # noqa: E402


def parse_key(key: str) -> int:
    m = re.search(r"(\d+)$", key.strip())
    if not m:
        raise SystemExit(f"Cannot parse issue number from {key!r}")
    return int(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--steps-tried", required=True)
    ap.add_argument("--dev-ticket", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    num = parse_key(a.key)
    vlabel = validate_label(a.project)
    plabel = pickup_label(a.project)

    lines = [
        "QA RETURN",
        "",
        f"**Reason:** {a.reason}",
        "",
        "**Steps tried:**",
        a.steps_tried,
    ]
    if a.dev_ticket:
        lines.extend(["", f"**Related:** {a.dev_ticket}"])
    lines.extend(
        [
            "",
            f"Removed `{vlabel}`; re-applied `{plabel}` for Hephaestus pickup.",
        ]
    )
    body = "\n".join(lines)

    if a.dry_run:
        print(body)
        return 0

    owner, repo = github_repo(a.project)
    repo_ref = f"{owner}/{repo}"

    subprocess.run(
        ["gh", "issue", "comment", str(num), "-R", repo_ref, "--body", body],
        check=True,
    )
    label_res = subprocess.run(
        [
            "gh",
            "issue",
            "edit",
            str(num),
            "-R",
            repo_ref,
            "--add-label",
            plabel,
            "--remove-label",
            vlabel,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if label_res.returncode != 0:
        print(
            f"GITHUB_RETURN_LABEL_FAIL {repo_ref}#{num}: {label_res.stderr or label_res.stdout}",
            file=sys.stderr,
        )
        return 1
    # Keep issue open for Dev
    print(f"GITHUB_RETURN_OK {repo_ref}#{num} → {plabel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
