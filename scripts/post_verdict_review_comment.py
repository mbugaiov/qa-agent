#!/usr/bin/env python3
"""Post VERDICT_REVIEW_PASS (or BLOCKED) to the tracker after check_verdict_review.

Usage:
  python3 scripts/post_verdict_review_comment.py --project projects/<slug> \\
    --key <KEY> --artifact runs/…/verdict-review-<KEY>.md --summary "…"
  python3 scripts/post_verdict_review_comment.py … --blocked --gaps "…"
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import github_inactive, github_repo, tracker_provider  # noqa: E402
from verdict_review_comment_require import (  # noqa: E402
    format_blocked_comment,
    format_pass_comment,
    is_jira_inactive,
)


def parse_issue_number(key: str) -> int:
    m = re.search(r"(\d+)$", key.strip())
    if not m:
        raise SystemExit(f"Cannot parse issue number from {key!r}")
    return int(m.group(1))


def post_github(project_dir: str, key: str, body: str) -> None:
    num = parse_issue_number(key)
    owner, repo = github_repo(project_dir)
    repo_ref = f"{owner}/{repo}"
    subprocess.run(
        ["gh", "issue", "comment", str(num), "-R", repo_ref, "--body", body],
        check=True,
    )
    print(f"VERDICT_REVIEW_COMMENT_POSTED github {repo_ref}#{num}")


def post_jira(project_dir: str, key: str, body: str) -> None:
    if is_jira_inactive(project_dir):
        print(f"VERDICT_REVIEW_COMMENT_SKIP {key}: Jira inactive/placeholder (no-op)")
        return

    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError as e:
        raise SystemExit(f"requests required: {e}") from e

    from jira_scope import load_env_file  # noqa: E402

    cfg = load_env_file(os.path.join(project_dir, ".secrets", "jira.env"))
    base = (cfg.get("JIRA_BASE_URL") or "").rstrip("/")
    email = cfg.get("JIRA_EMAIL") or ""
    token = cfg.get("JIRA_API_TOKEN") or ""

    # Plain text in a single ADF paragraph (newlines → hardBreaks)
    content: list[dict] = []
    for i, line in enumerate(body.split("\n")):
        if i:
            content.append({"type": "hardBreak"})
        if line:
            content.append({"type": "text", "text": line})
    adf = {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": content or [{"type": "text", "text": " "}]}],
    }
    res = requests.post(
        f"{base}/rest/api/3/issue/{key}/comment",
        json={"body": adf},
        auth=HTTPBasicAuth(email, token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=45,
    )
    if res.status_code >= 300:
        raise SystemExit(f"Jira comment failed HTTP {res.status_code}: {res.text[:400]}")
    print(f"VERDICT_REVIEW_COMMENT_POSTED jira {key}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--artifact", default="")
    ap.add_argument("--summary", default="")
    ap.add_argument("--blocked", action="store_true")
    ap.add_argument("--gaps", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.blocked:
        body = format_blocked_comment(gaps=a.gaps)
    else:
        if not a.artifact:
            raise SystemExit("--artifact required unless --blocked")
        body = format_pass_comment(artifact=a.artifact, summary=a.summary)

    if a.dry_run:
        print(body)
        print("[dry-run] not posted")
        return 0

    provider = tracker_provider(a.project)
    if provider == "github_issues":
        if github_inactive(a.project):
            print(
                f"VERDICT_REVIEW_COMMENT_SKIP {a.key}: GitHub tracker inactive (no-op)"
            )
            return 0
        post_github(a.project, a.key, body)
    elif provider == "jira":
        post_jira(a.project, a.key, body)
    else:
        raise SystemExit(f"Unsupported tracker provider: {provider}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
