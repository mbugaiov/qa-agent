#!/usr/bin/env python3
"""Transition a Jira issue and add a closing comment.

Usage:
    python3 scripts/jira_close_issue.py --project projects/<slug> --key RQ-1234 \
        --to Done --comment "Reason for close"

Exit 0 on success / Jira inactive (no-op).
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


def load_env_file(path: str) -> dict[str, str]:
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
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--to", default="Done", help="Target status name")
    ap.add_argument("--comment", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--allow-missing-verdict-review",
        action="store_true",
        help="Escape hatch only — do not use in normal factory ticks",
    )
    ap.add_argument(
        "--allow-missing-smoke-pack",
        action="store_true",
        help="Escape hatch only — skip acceptance-smoke pack gate when pack exists",
    )
    a = ap.parse_args()

    cfg = load_env_file(os.path.join(a.project, ".secrets", "jira.env"))
    base = cfg.get("JIRA_BASE_URL", "")
    email = cfg.get("JIRA_EMAIL", "")
    token = cfg.get("JIRA_API_TOKEN", "")
    if base in PLACEHOLDER or email in PLACEHOLDER or token in PLACEHOLDER or not (base and email and token):
        print(f"Jira not configured for {a.project} — skipping (no-op).")
        return 0

    # Live Jira close: engine feature must be used by the project ledger.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from smoke_pack_require import require_smoke_pack_pass  # noqa: E402
    from verdict_review_require import require_verdict_review_pass  # noqa: E402

    if not a.dry_run:
        require_verdict_review_pass(
            a.project,
            a.key,
            allow_missing=a.allow_missing_verdict_review,
        )
        require_smoke_pack_pass(
            a.project,
            a.key,
            allow_missing=a.allow_missing_smoke_pack,
        )

    base = base.rstrip("/")
    auth = HTTPBasicAuth(email, token)
    H = {"Accept": "application/json", "Content-Type": "application/json"}

    if a.dry_run:
        print(f"[dry-run] would transition {a.key} → {a.to}")
        print(f"[dry-run] comment: {a.comment}")
        return 0

    c = requests.post(
        f"{base}/rest/api/3/issue/{a.key}/comment",
        json={
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": a.comment}]}],
            }
        },
        auth=auth,
        headers=H,
        timeout=30,
    )
    print("comment", c.status_code)

    tr = requests.get(f"{base}/rest/api/3/issue/{a.key}/transitions", auth=auth, headers=H, timeout=30)
    trans = tr.json().get("transitions", [])
    t = next((x for x in trans if x["name"].lower() == a.to.lower()), None)
    if not t:
        names = ", ".join(x["name"] for x in trans)
        print(f"ERROR: no '{a.to}' transition. Available: {names}", file=sys.stderr)
        return 2
    r = requests.post(
        f"{base}/rest/api/3/issue/{a.key}/transitions",
        json={"transition": {"id": t["id"]}},
        auth=auth,
        headers=H,
        timeout=30,
    )
    if r.status_code >= 300:
        print(f"ERROR transition: {r.status_code} {r.text}", file=sys.stderr)
        return 3
    print(f"transitioned {a.key} → {a.to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
