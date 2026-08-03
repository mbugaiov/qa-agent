#!/usr/bin/env python3
"""Attach a local evidence file to a GitHub Issue (secret gist + comment).

Uses projects/<slug>/.secrets/github.env GITHUB_TOKEN only (strips ambient GH_*).

Usage:
    python3 scripts/github_attach_evidence.py --project projects/<slug> \\
        --key <slug>#12 --file path/to/clip.mp4 [--caption "QA retest recording"]

Exit 0 on success; 3 if project token missing; non-zero on upload/comment failure.
Prints bug_recording_attached=true or bug_screenshot_attached=true when applicable.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_create_issue import project_gh_env, secret_gist_upload  # noqa: E402
from github_tracker import github_inactive, github_repo, resolve_github_repo  # noqa: E402


def parse_issue_number(key: str) -> int:
    m = re.search(r"(\d+)$", key.strip())
    if not m:
        raise SystemExit(f"Cannot parse issue number from {key!r}")
    return int(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--caption", default="QA evidence")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.file):
        print(f"Missing file: {a.file}", file=sys.stderr)
        return 1

    repo_tuple = resolve_github_repo(a.project)
    if repo_tuple is None and not a.dry_run:
        print(f"GitHub owner/repo not configured for {a.project}.", file=sys.stderr)
        return 1

    gh_env, has_token = project_gh_env(a.project)
    if a.dry_run:
        print(
            f"DRY RUN → secret gist + comment on {a.key} "
            f"(project_token={'yes' if has_token else 'no'}) file={a.file}"
        )
        return 0

    # Isolation: require project token whenever a repo is configured (do not
    # soft-skip via github_inactive / missing gh — that masked CI token gates).
    if not has_token:
        print(
            "GITHUB_ATTACH_TOKEN_REQUIRED — set GITHUB_TOKEN in "
            f"{a.project}/.secrets/github.env",
            file=sys.stderr,
        )
        return 3

    if github_inactive(a.project):
        print(
            f"GitHub CLI unavailable for {a.project} — cannot attach.",
            file=sys.stderr,
        )
        return 1

    owner, repo = github_repo(a.project)
    repo_ref = f"{owner}/{repo}"
    num = parse_issue_number(a.key)
    base = os.path.basename(a.file)
    gist_url = secret_gist_upload(
        a.file, f"{a.caption} ({a.key})", env=gh_env
    )
    if not gist_url:
        print(f"secret gist upload failed for {a.file}", file=sys.stderr)
        return 1

    lower = base.lower()
    if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        line = f"- ![{base}]({gist_url})"
        flag = "bug_screenshot_attached=true"
    elif lower.endswith((".mp4", ".webm", ".mov", ".m4v")):
        line = f"- [{base}]({gist_url})"
        flag = "bug_recording_attached=true"
    else:
        line = f"- [{base}]({gist_url})"
        flag = "evidence_attached=true"

    body = f"## {a.caption}\n\n{line}\n"
    r = subprocess.run(
        [
            "gh",
            "issue",
            "comment",
            str(num),
            "-R",
            repo_ref,
            "--body",
            body,
        ],
        check=False,
        env=gh_env,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        return 1

    print(f"Attached {base} → {gist_url} on {repo_ref}#{num}")
    print(flag)
    # Also print recording_attached for feature Done DoD (same clip)
    if flag.startswith("bug_recording"):
        print("recording_attached=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
