#!/usr/bin/env python3
"""Read Dev STG handoff from a GitHub Issue before retest.

Usage:
    python3 scripts/github_handoff.py --project projects/<slug> --key <slug>#12
    python3 scripts/github_handoff.py --project projects/<slug> --key 12 --json --log
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import (  # noqa: E402
    extract_hints,
    github_inactive,
    github_repo,
    is_dev_handoff_comment,
    validate_label,
)


def parse_key(key: str) -> int:
    m = re.search(r"(\d+)$", key.strip())
    if not m:
        raise SystemExit(f"Cannot parse issue number from {key!r}")
    return int(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--log", action="store_true")
    a = ap.parse_args()

    slug = os.path.basename(a.project.rstrip("/"))
    num = parse_key(a.key)

    if github_inactive(a.project):
        payload = {
            "key": f"{slug}#{num}",
            "status": "inactive",
            "summary": "",
            "description": "",
            "comments": [],
            "handoff": "",
            "hints": {},
            "labels": [],
            "inactive": True,
        }
        if a.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"=== {slug}#{num} [inactive] ===")
            print("GitHub tracker inactive (missing repo config or gh CLI)")
        return 0

    owner, repo = github_repo(a.project)
    repo_ref = f"{owner}/{repo}"

    try:
        issue_raw = subprocess.check_output(
            [
                "gh",
                "issue",
                "view",
                str(num),
                "-R",
                repo_ref,
                "--json",
                "number,title,state,labels,body",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        issue = json.loads(issue_raw)
        comments_raw = subprocess.check_output(
            ["gh", "api", f"repos/{owner}/{repo}/issues/{num}/comments"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        comments = json.loads(comments_raw) if comments_raw.strip() else []
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"GITHUB_HANDOFF_INACTIVE {repo_ref}#{num}: {exc}", file=sys.stderr)
        if a.json:
            print(
                json.dumps(
                    {
                        "key": f"{slug}#{num}",
                        "status": "inactive",
                        "inactive": True,
                        "handoff": "",
                        "hints": {},
                        "comments": [],
                        "labels": [],
                    }
                )
            )
            return 0
        return 1

    comments_out = []
    all_text = (issue.get("body") or "") + "\n"
    handoff_text = ""
    for c in comments:
        body = (c.get("body") or "").strip()
        if not body:
            continue
        entry = {
            "created": (c.get("created_at") or "")[:16],
            "author": (c.get("user") or {}).get("login", ""),
            "text": body,
        }
        comments_out.append(entry)
        all_text += body + "\n"
        if is_dev_handoff_comment(body):
            handoff_text = body

    hints = extract_hints(handoff_text or all_text)
    labels = [x.get("name", "") for x in (issue.get("labels") or [])]
    vlabel = validate_label(a.project)
    status = vlabel if vlabel in labels else str(issue.get("state"))
    key = f"{slug}#{num}"

    payload = {
        "key": key,
        "status": status,
        "summary": issue.get("title", ""),
        "description": (issue.get("body") or "")[:2000],
        "comments": comments_out[-5:],
        "handoff": handoff_text[:4000] if handoff_text else "",
        "hints": hints,
        "labels": labels,
    }

    if a.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"=== {key} [{status}] ===")
        print(f"Summary: {payload['summary']}")
        if handoff_text:
            print("\nDev handoff:\n" + handoff_text[:2500])
        elif comments_out:
            print("\nRecent comments:")
            for c in comments_out[-5:]:
                print(f"  [{c['created']}] {c['author']}: {c['text'][:600]}")
        if hints:
            print(f"\nHints: {hints}")

    if a.log:
        log_args = [f"buildId={hints['buildId']}"] if hints.get("buildId") else []
        if hints.get("pr"):
            log_args.append(f"pr={hints['pr']}")
        if hints.get("pipeline"):
            log_args.append(f"pipeline={hints['pipeline']}")
        log_args.append(f"status={status}")
        if labels:
            log_args.append(f"labels={','.join(labels)}")
        script = os.path.join(ROOT, "scripts", "factory_log.sh")
        subprocess.run([script, slug, key, "handoff_read", *log_args], check=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
