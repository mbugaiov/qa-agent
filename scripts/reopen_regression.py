#!/usr/bin/env python3
"""Reopen a Done Jira ticket that failed retest (regression) — L5 QA auto-reopen.

Moves a ticket back to In Progress and posts a REGRESSION comment (optionally with an
attachment). Per-project Jira config only (projects/<slug>/.secrets/jira.env); strict
isolation, and a graceful no-op when Jira is not configured for the project.

Usage:
    python3 scripts/reopen_regression.py --project projects/<slug> --key ABC-1234 \
        --reason "Retest FAIL on STG: <what broke>" [--attach path.png] [--dry-run]

Exit 0 on success / no-op; non-zero on API failure.
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("The 'requests' package is required: pip install requests")

PLACEHOLDER = {"", "<atlassian api token>", "you@company.com", "https://<company>.atlassian.net"}


def load_env_file(path: str) -> dict:
    out: dict[str, str] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="projects/<slug>")
    ap.add_argument("--key", required=True, help="Jira issue key, e.g. RQ-1234")
    ap.add_argument("--reason", required=True, help="Why it regressed (goes in the comment)")
    ap.add_argument("--attach", action="append", default=[], help="Evidence file(s); repeatable")
    ap.add_argument("--target-status", default="In Progress", help="Status to move to (default: In Progress)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = load_env_file(os.path.join(a.project, ".secrets", "jira.env"))
    base = cfg.get("JIRA_BASE_URL", "")
    email = cfg.get("JIRA_EMAIL", "")
    token = cfg.get("JIRA_API_TOKEN", "")
    if base in PLACEHOLDER or email in PLACEHOLDER or token in PLACEHOLDER or not (base and email and token):
        print(f"Jira not configured for {a.project} — skipping reopen (no-op).")
        return 0

    base = base.rstrip("/")
    auth = HTTPBasicAuth(email, token)
    H = {"Accept": "application/json", "Content-Type": "application/json"}
    body = f"REGRESSION (QA auto-reopen): {a.reason}"

    if a.dry_run:
        print(f"[dry-run] would reopen {a.key} → {a.target_status}")
        print(f"[dry-run] comment: {body}")
        print(f"[dry-run] attach: {a.attach}")
        return 0

    c = requests.post(f"{base}/rest/api/3/issue/{a.key}/comment",
                      json={"body": {"type": "doc", "version": 1,
                                     "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}},
                      auth=auth, headers=H, timeout=30)
    print("comment", c.status_code)

    for p in a.attach:
        if os.path.exists(p):
            r = requests.post(f"{base}/rest/api/3/issue/{a.key}/attachments",
                              headers={"X-Atlassian-Token": "no-check"}, auth=auth,
                              files={"file": (os.path.basename(p), open(p, "rb"))}, timeout=60)
            print("attach", os.path.basename(p), r.status_code)

    tr = requests.get(f"{base}/rest/api/3/issue/{a.key}/transitions", auth=auth, headers=H, timeout=30)
    trans = tr.json().get("transitions", [])
    t = next((x for x in trans if x["name"].lower() == a.target_status.lower()), None)
    if not t:
        print(f"ERROR: no '{a.target_status}' transition. Available: {', '.join(x['name'] for x in trans)}", file=sys.stderr)
        return 2
    r = requests.post(f"{base}/rest/api/3/issue/{a.key}/transitions",
                      json={"transition": {"id": t["id"]}}, auth=auth, headers=H, timeout=30)
    if r.status_code >= 300:
        print(f"ERROR transition: {r.status_code} {r.text}", file=sys.stderr)
        return 3
    print(f"reopened {a.key} → {a.target_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
