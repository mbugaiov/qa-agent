#!/usr/bin/env python3
"""Query GitHub Issues for QA scope.

Priority (matches qa-loop / Jira factory):
1. Open issues with validate-testing (Hephaestus handoff retests) — always first.
2. When that queue is empty: open issues with impl-qa (Argus charter / marathon).

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
    github_inactive,
    impl_qa_label,
    resolve_github_repo,
    validate_label,
)

# Labels that park a ticket out of the unattended queue (same spirit as Jira exclusions).
_EXCLUDED = frozenset(
    {"human-required", "factory-pause", "needs-human", "deferred"}
)


def log_scope_check(slug: str, keys: list[str]) -> None:
    script = os.path.join(ROOT, "scripts", "factory_log.sh")
    subprocess.run(
        [script, slug, "_loop", "scope_check", f"keys={','.join(keys)}", f"count={len(keys)}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def emit_inactive(a: argparse.Namespace) -> int:
    payload = {"keys": [], "count": 0, "jql": "", "inactive": True, "issues": []}
    if a.json:
        print(json.dumps(payload))
    elif a.shell:
        print("keys=''")
        print("count=0")
        print("SCOPE_KEYS=''")
        print("SCOPE_COUNT=0")
        print("SCOPE_JQL=''")
        print("jql=''")
        print("inactive=1")
    else:
        print("keys=")
        print("count=0")
        print("inactive=1")
    return 0


def _list_open_labeled(repo_ref: str, label: str) -> list[dict]:
    try:
        raw = subprocess.check_output(
            [
                "gh",
                "issue",
                "list",
                "-R",
                repo_ref,
                "--state",
                "open",
                "--label",
                label,
                "--json",
                "number,title,state,labels,createdAt",
                "--limit",
                "100",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    items = json.loads(raw) if raw.strip() else []
    out: list[dict] = []
    for i in items:
        if str(i.get("state", "")).lower() != "open":
            continue
        names = {l.get("name") for l in (i.get("labels") or [])}
        if label not in names:
            continue
        if names & _EXCLUDED:
            continue
        out.append(i)
    out.sort(key=lambda i: (i.get("createdAt") or "", int(i["number"])))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--shell", action="store_true")
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()

    slug = os.path.basename(a.project.rstrip("/"))
    if github_inactive(a.project):
        if a.log:
            log_scope_check(slug, [])
        return emit_inactive(a)

    resolved = resolve_github_repo(a.project)
    assert resolved is not None
    owner, repo = resolved
    v_label = validate_label(a.project)
    qa_label = impl_qa_label(a.project)
    repo_ref = f"{owner}/{repo}"

    retest = _list_open_labeled(repo_ref, v_label)
    queue = retest
    queue_kind = "validate-testing"
    jql = f"github:{repo_ref} label:{v_label} is:open"

    # When handoff retest is empty, surface Argus charter queue (impl-qa).
    # Never mix: V/T always wins so retests are not starved by marathon work.
    if not queue:
        charter = _list_open_labeled(repo_ref, qa_label)
        # Prefer pure impl-qa charters; skip items still marked validate-testing
        # (those belong in the retest query above).
        charter = [
            i
            for i in charter
            if not any(
                l.get("name") == v_label for l in (i.get("labels") or [])
            )
        ]
        queue = charter
        queue_kind = "impl-qa"
        jql = f"github:{repo_ref} label:{qa_label} is:open (validate-testing empty)"

    keys = [f"{slug}#{i['number']}" for i in queue]
    issues = [
        {
            "key": f"{slug}#{i['number']}",
            "summary": i.get("title", ""),
            "status": queue_kind,
        }
        for i in queue
    ]

    if a.log:
        log_scope_check(slug, keys)

    if a.json:
        print(
            json.dumps(
                {
                    "keys": keys,
                    "count": len(keys),
                    "jql": jql,
                    "queue": queue_kind,
                    "issues": issues,
                }
            )
        )
        return 0

    if a.shell:
        print(f"count={len(keys)}")
        print(f"SCOPE_COUNT={len(keys)}")
        print(f"keys={shlex.quote(','.join(keys))}")
        print(f"SCOPE_KEYS={shlex.quote(','.join(keys))}")
        print(f"jql={shlex.quote(jql)}")
        print(f"SCOPE_QUEUE={queue_kind}")
        return 0

    print(f"keys={','.join(keys)}")
    print(f"count={len(keys)}")
    print(f"jql={jql}")
    print(f"queue={queue_kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
