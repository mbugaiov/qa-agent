#!/usr/bin/env python3
"""Return a Validate/Testing ticket to In Progress — QA blocked handoff to dev.

Use when retest cannot complete and the feature ticket must NOT stay in V/T:
locator/testid gaps, product defects, or environmental blockers with a filed dev/bug ticket.

Usage:
    python3 scripts/jira_return_in_progress.py --project projects/<slug> --key RQ-1234 \
        --reason "Relocate picker: options not exposed to automation; need data-testid on options" \
        [--dev-ticket RQ-1741] [--attach evidence.png] [--dry-run]

Exit 0 on success / Jira inactive (no-op); non-zero on API failure.
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
    ap.add_argument("--key", required=True, help="Feature ticket in Validate/Testing")
    ap.add_argument("--reason", required=True, help="Why QA cannot close; what dev must fix")
    ap.add_argument("--steps-tried", required=True, help="Bullet summary of retest steps attempted (proves retest ran)")
    ap.add_argument("--handoff-file", default="", help="Structured dev handoff (templates/retest-fail-dev-handoff.md)")
    ap.add_argument("--dev-ticket", default="", help="Separate bug/task filed for dev (e.g. locator)")
    ap.add_argument("--attach", action="append", default=[], help="Evidence file(s)")
    ap.add_argument("--target-status", default="In Progress")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = load_env_file(os.path.join(a.project, ".secrets", "jira.env"))
    base = cfg.get("JIRA_BASE_URL", "")
    email = cfg.get("JIRA_EMAIL", "")
    token = cfg.get("JIRA_API_TOKEN", "")
    if base in PLACEHOLDER or email in PLACEHOLDER or token in PLACEHOLDER or not (base and email and token):
        print(f"Jira not configured for {a.project} — skipping return (no-op).")
        return 0

    base = base.rstrip("/")
    auth = HTTPBasicAuth(email, token)
    H = {"Accept": "application/json", "Content-Type": "application/json"}
    extra = f" Dev ticket: {a.dev_ticket}." if a.dev_ticket else ""
    handoff_body = ""
    if a.handoff_file and os.path.exists(a.handoff_file):
        with open(a.handoff_file, encoding="utf-8") as fh:
            handoff_body = fh.read().strip()
    body = (
        f"QA RETURN (blocked — cannot stay in Validate/Testing): {a.reason}.{extra}\n\n"
        f"Steps tried:\n{a.steps_tried}"
    )
    if handoff_body:
        body += f"\n\n---\n## Dev handoff (structured)\n\n{handoff_body}"

    if a.dry_run:
        print(f"[dry-run] would return {a.key} → {a.target_status}")
        print(f"[dry-run] comment ({len(body)} chars): {body[:800]}…" if len(body) > 800 else f"[dry-run] comment: {body}")
        return 0

    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from jira_adf import adf_from_text

    c = requests.post(
        f"{base}/rest/api/3/issue/{a.key}/comment",
        json={"body": adf_from_text(body, markdown=True)},
        auth=auth, headers=H, timeout=30,
    )
    print("comment", c.status_code)

    for p in a.attach:
        if os.path.exists(p):
            r = requests.post(
                f"{base}/rest/api/3/issue/{a.key}/attachments",
                headers={"X-Atlassian-Token": "no-check"},
                auth=auth,
                files={"file": (os.path.basename(p), open(p, "rb"))},
                timeout=60,
            )
            print("attach", os.path.basename(p), r.status_code)

    tr = requests.get(f"{base}/rest/api/3/issue/{a.key}/transitions", auth=auth, headers=H, timeout=30)
    trans = tr.json().get("transitions", [])
    t = next((x for x in trans if x["name"].lower() == a.target_status.lower()), None)
    if not t:
        print(f"ERROR: no '{a.target_status}' transition. Available: {', '.join(x['name'] for x in trans)}", file=sys.stderr)
        return 2
    r = requests.post(
        f"{base}/rest/api/3/issue/{a.key}/transitions",
        json={"transition": {"id": t["id"]}},
        auth=auth, headers=H, timeout=30,
    )
    if r.status_code >= 300:
        print(f"ERROR transition: {r.status_code} {r.text}", file=sys.stderr)
        return 3
    print(f"returned {a.key} → {a.target_status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
