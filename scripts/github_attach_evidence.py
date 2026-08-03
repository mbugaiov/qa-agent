#!/usr/bin/env python3
"""Attach one evidence file to a GitHub Issue as an **inline GIF/PNG** comment.

Videos are converted to GIF first. Media is uploaded once (Contents API raw URL)
and the issue comment uses ``![caption](url)`` so it renders in the thread —
not an opaque MP4 blob pack on ``qa-evidence``.

Do **not** push screenshot directories to the product repo; one GIF (or one PNG)
per ticket is the contract.

Usage:
    python3 scripts/github_attach_evidence.py --project projects/<slug> \\
        --key <slug>#12 --file path/to/clip.mp4 [--caption "QA retest"]

Exit 0 on success; 3 if project token missing; non-zero on upload/comment failure.
Prints bug_recording_attached=true / bug_screenshot_attached=true / recording_attached=true.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_create_issue import (  # noqa: E402
    _is_media_path,
    evidence_markdown_line,
    github_repo_evidence_upload,
    prepare_github_media,
    project_gh_env,
    secret_gist_upload,
)
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
            f"DRY RUN → inline GIF/PNG comment on {a.key} "
            f"(project_token={'yes' if has_token else 'no'}) file={a.file}"
        )
        return 0

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

    try:
        upload_path, from_video = prepare_github_media(a.file)
    except Exception as e:
        print(f"media prepare failed: {e}", file=sys.stderr)
        return 1

    base = os.path.basename(upload_path)
    url = github_repo_evidence_upload(
        upload_path,
        owner=owner,
        repo=repo,
        issue_key=a.key,
        message=f"{a.caption} ({a.key})",
        env=gh_env,
    )
    if not url and not _is_media_path(upload_path):
        url = secret_gist_upload(upload_path, f"{a.caption} ({a.key})", env=gh_env)
    if not url:
        print(f"evidence upload failed for {upload_path}", file=sys.stderr)
        return 1

    lower = base.lower()
    is_image = lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    if from_video or lower.endswith(".gif"):
        # One animated GIF satisfies both recording + screenshot DoD on GitHub.
        flags = [
            "bug_recording_attached=true",
            "bug_screenshot_attached=true",
            "recording_attached=true",
        ]
    elif is_image:
        flags = ["bug_screenshot_attached=true", "evidence_attached=true"]
    else:
        flags = ["evidence_attached=true"]

    body = (
        f"## {a.caption}\n\n"
        f"{evidence_markdown_line(base, url, caption=a.caption)}\n\n"
        f"_Inline evidence (GIF/PNG). Do not open opaque repo blob packs._\n"
    )
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

    print(f"Attached {base} → {url} on {repo_ref}#{num} (inline comment)")
    for flag in flags:
        print(flag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
