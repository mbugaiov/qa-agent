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

from github_tracker import github_repo, tracker_provider  # noqa: E402

PASS_SENTINEL = "VERDICT_REVIEW_PASS"
BLOCKED_SENTINEL = "VERDICT_REVIEW_BLOCKED"

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


def fetch_github_comment_bodies(project_dir: str, key: str) -> list[str]:
    m = re.search(r"(\d+)$", key.strip())
    if not m:
        raise SystemExit(f"Cannot parse issue number from {key!r}")
    num = int(m.group(1))
    owner, repo = github_repo(project_dir)
    repo_ref = f"{owner}/{repo}"
    out = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo_ref}/issues/{num}/comments",
            "--paginate",
            "--jq",
            ".[].body",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        print(
            f"VERDICT_REVIEW_COMMENT_FETCH_FAIL {key}: {out.stderr or out.stdout}",
            file=sys.stderr,
        )
        raise SystemExit(7)
    bodies = [ln for ln in (out.stdout or "").split("\n\n") if ln.strip()]
    # gh --jq prints one body per line when using .[].body — actually each body
    # may be multiline. Prefer JSON:
    outj = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo_ref}/issues/{num}/comments",
            "--paginate",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if outj.returncode != 0:
        return bodies
    try:
        data = json.loads(outj.stdout or "[]")
    except json.JSONDecodeError:
        return bodies
    if isinstance(data, list):
        return [str(c.get("body") or "") for c in data if isinstance(c, dict)]
    return bodies


def fetch_jira_comment_bodies(project_dir: str, key: str) -> list[str]:
    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError as e:
        raise SystemExit(f"requests required for Jira comment gate: {e}") from e

    env_path = os.path.join(project_dir, ".secrets", "jira.env")
    cfg: dict[str, str] = {}
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    base = (cfg.get("JIRA_BASE_URL") or "").rstrip("/")
    email = cfg.get("JIRA_EMAIL") or ""
    token = cfg.get("JIRA_API_TOKEN") or ""
    if not (base and email and token):
        print(
            f"VERDICT_REVIEW_COMMENT_SKIP {key}: Jira not configured",
            file=sys.stderr,
        )
        return []

    res = requests.get(
        f"{base}/rest/api/3/issue/{key}/comment",
        auth=HTTPBasicAuth(email, token),
        headers={"Accept": "application/json"},
        timeout=45,
    )
    if res.status_code >= 300:
        print(
            f"VERDICT_REVIEW_COMMENT_FETCH_FAIL {key}: HTTP {res.status_code}",
            file=sys.stderr,
        )
        raise SystemExit(7)
    data = res.json()
    bodies: list[str] = []
    for c in data.get("comments") or []:
        body = c.get("body")
        if isinstance(body, str):
            bodies.append(body)
        elif isinstance(body, dict):
            # ADF → rough plain text
            bodies.append(_adf_to_text(body))
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
            bodies = fetch_github_comment_bodies(project_dir, key)
        elif provider == "jira":
            bodies = fetch_jira_comment_bodies(project_dir, key)
            if not bodies and not os.path.isfile(
                os.path.join(project_dir, ".secrets", "jira.env")
            ):
                # Inactive / unconfigured Jira projects no-op elsewhere — do not block.
                return
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
