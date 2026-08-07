#!/usr/bin/env python3
"""Require a human-visible VERDICT_REVIEW_PASS comment on the tracker before close.

Sentinel (dedicated line — not prose mention only):

    VERDICT_REVIEW_PASS
    artifact: runs/…/verdict-review-<KEY>.md
    summary: …

Or for blocked (close must not proceed):

    VERDICT_REVIEW_BLOCKED
    …

Used by github/jira close + return scripts after ledger verdict_review=pass.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from github_tracker import github_inactive, github_repo, tracker_provider  # noqa: E402
from jira_scope import is_placeholder, load_env_file  # noqa: E402

PASS_SENTINEL = "VERDICT_REVIEW_PASS"
BLOCKED_SENTINEL = "VERDICT_REVIEW_BLOCKED"


def is_jira_inactive(project_dir: str) -> bool:
    """True when Jira is missing or template/placeholder — never call Atlassian."""
    cfg = load_env_file(os.path.join(project_dir, ".secrets", "jira.env"))
    base = cfg.get("JIRA_BASE_URL", "")
    email = cfg.get("JIRA_EMAIL", "")
    token = cfg.get("JIRA_API_TOKEN", "")
    project_key = cfg.get("JIRA_PROJECT_KEY", "")
    return (
        is_placeholder(base)
        or is_placeholder(email)
        or is_placeholder(token)
        or is_placeholder(project_key)
    )

# Dedicated line (optional ## heading), not "wait for VERDICT_REVIEW_PASS" prose.
_PASS_RE = re.compile(
    rf"(?:^|\n)\s*(?:##\s*)?{PASS_SENTINEL}\s*(?:\n|$)",
    re.MULTILINE,
)
_BLOCKED_RE = re.compile(
    rf"(?:^|\n)\s*(?:##\s*)?{BLOCKED_SENTINEL}\s*(?:\n|$)",
    re.MULTILINE,
)


def comment_has_verdict_review_pass(text: str) -> bool:
    return bool(_PASS_RE.search(text or ""))


def comment_has_verdict_review_blocked(text: str) -> bool:
    return bool(_BLOCKED_RE.search(text or ""))


def format_pass_comment(*, artifact: str, summary: str) -> str:
    return "\n".join(
        [
            PASS_SENTINEL,
            f"artifact: {artifact}",
            f"summary: {summary.strip() or '(no summary)'}",
            "",
            "_Posted by post_verdict_review_comment.py (qa-verdict-review)._",
        ]
    )


def format_blocked_comment(*, gaps: str) -> str:
    return "\n".join(
        [
            BLOCKED_SENTINEL,
            "",
            gaps.strip() or "Blocking gaps present — see verdict-review artifact.",
            "",
            "_Posted by post_verdict_review_comment.py (qa-verdict-review)._",
        ]
    )


def _flatten_gh_comment_pages(data: Any) -> list[dict]:
    """Flatten `gh api --paginate --slurp` (list of pages) or a single page list."""
    if not isinstance(data, list):
        return []
    if not data:
        return []
    # Single page: [{comment}, …]
    if isinstance(data[0], dict) and ("body" in data[0] or "id" in data[0]):
        return [c for c in data if isinstance(c, dict)]
    # Slurp: [[{comment}, …], [{comment}, …], …]
    out: list[dict] = []
    for page in data:
        if isinstance(page, list):
            out.extend(c for c in page if isinstance(c, dict))
    return out


def fetch_github_comment_bodies(project_dir: str, key: str) -> list[str]:
    m = re.search(r"(\d+)$", key.strip())
    if not m:
        raise SystemExit(f"Cannot parse issue number from {key!r}")
    num = int(m.group(1))
    owner, repo = github_repo(project_dir)
    repo_ref = f"{owner}/{repo}"
    outj = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo_ref}/issues/{num}/comments",
            "--paginate",
            "--slurp",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if outj.returncode != 0:
        print(
            f"VERDICT_REVIEW_COMMENT_FETCH_FAIL {key}: {outj.stderr or outj.stdout}",
            file=sys.stderr,
        )
        raise SystemExit(7)
    try:
        data = json.loads(outj.stdout or "[]")
    except json.JSONDecodeError:
        print(
            f"VERDICT_REVIEW_COMMENT_FETCH_FAIL {key}: invalid JSON from gh api",
            file=sys.stderr,
        )
        raise SystemExit(7)
    return [str(c.get("body") or "") for c in _flatten_gh_comment_pages(data)]


def _jira_comment_body_text(c: dict) -> str:
    body = c.get("body")
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        return _adf_to_text(body)
    return ""


def fetch_jira_comment_bodies(project_dir: str, key: str) -> list[str]:
    if is_jira_inactive(project_dir):
        print(
            f"VERDICT_REVIEW_COMMENT_SKIP {key}: Jira inactive/placeholder",
            file=sys.stderr,
        )
        return []

    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError as e:
        raise SystemExit(f"requests required for Jira comment gate: {e}") from e

    cfg = load_env_file(os.path.join(project_dir, ".secrets", "jira.env"))
    base = (cfg.get("JIRA_BASE_URL") or "").rstrip("/")
    email = cfg.get("JIRA_EMAIL") or ""
    token = cfg.get("JIRA_API_TOKEN") or ""
    auth = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json"}

    # Paginate oldest→newest so latest_pass_or_blocked sees the newest sentinel.
    bodies: list[str] = []
    start_at = 0
    page_size = 100
    while True:
        res = requests.get(
            f"{base}/rest/api/3/issue/{key}/comment",
            params={"startAt": start_at, "maxResults": page_size, "orderBy": "created"},
            auth=auth,
            headers=headers,
            timeout=45,
        )
        if res.status_code >= 300:
            print(
                f"VERDICT_REVIEW_COMMENT_FETCH_FAIL {key}: HTTP {res.status_code}",
                file=sys.stderr,
            )
            raise SystemExit(7)
        data = res.json()
        comments = data.get("comments") or []
        for c in comments:
            if isinstance(c, dict):
                bodies.append(_jira_comment_body_text(c))
        total = int(data.get("total") or 0)
        start_at += len(comments)
        if not comments or start_at >= total:
            break
    return bodies


def _adf_to_text(node: Any) -> str:
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    parts: list[str] = []
    if node.get("type") == "text":
        parts.append(str(node.get("text") or ""))
    for child in node.get("content") or []:
        parts.append(_adf_to_text(child))
    return "\n".join(p for p in parts if p)


def latest_pass_or_blocked(bodies: list[str]) -> str | None:
    """Return 'pass', 'blocked', or None from newest matching comment."""
    for body in reversed(bodies):
        if comment_has_verdict_review_blocked(body):
            return "blocked"
        if comment_has_verdict_review_pass(body):
            return "pass"
    return None


def require_verdict_review_comment(
    project_dir: str,
    key: str,
    *,
    allow_missing: bool = False,
    bodies: list[str] | None = None,
) -> None:
    """Exit 7 when tracker lacks VERDICT_REVIEW_PASS (or is BLOCKED)."""
    if allow_missing:
        print(
            f"WARNING: skipping VERDICT_REVIEW_PASS comment check for {key}",
            file=sys.stderr,
        )
        return

    if bodies is None:
        provider = tracker_provider(project_dir)
        if provider == "github_issues":
            if github_inactive(project_dir):
                print(
                    f"VERDICT_REVIEW_COMMENT_SKIP {key}: GitHub tracker inactive",
                    file=sys.stderr,
                )
                return
            bodies = fetch_github_comment_bodies(project_dir, key)
        elif provider == "jira":
            if is_jira_inactive(project_dir):
                # Same contract as jira_close_issue / jira_scope — never error on template.
                print(
                    f"VERDICT_REVIEW_COMMENT_SKIP {key}: Jira inactive/placeholder",
                    file=sys.stderr,
                )
                return
            bodies = fetch_jira_comment_bodies(project_dir, key)
        else:
            print(
                f"VERDICT_REVIEW_COMMENT_SKIP {key}: unknown tracker {provider}",
                file=sys.stderr,
            )
            return

    state = latest_pass_or_blocked(bodies)
    if state == "pass":
        return
    if state == "blocked":
        print(
            f"VERDICT_REVIEW_BLOCKED {key}: tracker has {BLOCKED_SENTINEL} — "
            f"fix gaps before Done/RETURN.",
            file=sys.stderr,
        )
        raise SystemExit(7)
    print(
        f"VERDICT_REVIEW_COMMENT_REQUIRED {key}: post tracker comment with "
        f"{PASS_SENTINEL} via `python3 scripts/post_verdict_review_comment.py "
        f"--project … --key {key} --artifact … --summary …` "
        f"(skill qa-verdict-review). Close/return blocked.",
        file=sys.stderr,
    )
    raise SystemExit(7)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--allow-missing-verdict-review-comment", action="store_true")
    a = ap.parse_args()
    try:
        require_verdict_review_comment(
            a.project,
            a.key,
            allow_missing=a.allow_missing_verdict_review_comment,
        )
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1
    print(f"VERDICT_REVIEW_COMMENT_OK {a.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
