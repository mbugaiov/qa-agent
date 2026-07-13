#!/usr/bin/env python3
"""Read dev handoff on a Jira ticket before V/T retest.

Prints summary, description, recent comments (ADF → plain text), and extracted
hints (buildId, PR/MR URLs, pipeline). Optionally logs handoff_read to factory ledger.

Usage:
    python3 scripts/jira_handoff.py --project projects/<slug> --key RQ-1234
    python3 scripts/jira_handoff.py --project projects/<slug> --key RQ-1234 --log
    python3 scripts/jira_handoff.py --project projects/<slug> --key RQ-1234 --json

Exit 0 on success / Jira inactive (prints note, exit 0). Non-zero on API failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("The 'requests' package is required: pip install requests")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def adf_to_text(node: dict | None) -> str:
    if not node:
        return ""
    parts: list[str] = []
    t = node.get("type")
    if t == "text":
        parts.append(node.get("text", ""))
    elif t == "hardBreak":
        parts.append("\n")
    elif t == "inlineCard" and node.get("attrs", {}).get("url"):
        parts.append(node["attrs"]["url"])
    for child in node.get("content") or []:
        parts.append(adf_to_text(child))
    if t in ("paragraph", "heading", "listItem", "bulletList", "orderedList"):
        parts.append("\n")
    return "".join(parts)


def extract_hints(text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    m = re.search(r"buildId[:\s]+([0-9a-f]{7,40})", text, re.I)
    if m:
        hints["buildId"] = m.group(1)
    m = re.search(r"STG buildId[:\s]+([0-9a-f]{7,40})", text, re.I)
    if m:
        hints["buildId"] = m.group(1)
    prs = re.findall(r"https?://\S+pull-requests/\d+", text, re.I)
    if prs:
        hints["pr"] = prs[0]
    mrs = re.findall(r"https?://\S+pull-requests/\d+", text, re.I)
    if mrs and "pr" not in hints:
        hints["pr"] = mrs[0]
    pipe = re.search(r"Pipeline build[:\s#]+(\S+)", text, re.I)
    if pipe:
        hints["pipeline"] = pipe.group(1)
    return hints


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="projects/<slug>")
    ap.add_argument("--key", required=True, help="Jira issue key")
    ap.add_argument("--log", action="store_true", help="Append handoff_read to factory ledger")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    a = ap.parse_args()

    slug = os.path.basename(a.project.rstrip("/"))
    cfg = load_env_file(os.path.join(a.project, ".secrets", "jira.env"))
    base = cfg.get("JIRA_BASE_URL", "")
    email = cfg.get("JIRA_EMAIL", "")
    token = cfg.get("JIRA_API_TOKEN", "")
    if base in PLACEHOLDER or email in PLACEHOLDER or token in PLACEHOLDER or not (base and email and token):
        print(f"Jira not configured for {a.project} — handoff_read skipped (no-op).")
        return 0

    base = base.rstrip("/")
    auth = HTTPBasicAuth(email, token)
    H = {"Accept": "application/json"}

    ir = requests.get(
        f"{base}/rest/api/3/issue/{a.key}",
        auth=auth,
        headers=H,
        params={"fields": "summary,description,status,comment,labels"},
        timeout=30,
    )
    if ir.status_code >= 300:
        print(f"ERROR issue: {ir.status_code} {ir.text}", file=sys.stderr)
        return 1
    issue = ir.json()
    fields = issue["fields"]
    status = fields["status"]["name"]
    summary = fields.get("summary", "")
    desc_text = adf_to_text(fields.get("description")).strip()

    comments_out: list[dict] = []
    all_text = desc_text + "\n"
    for c in (fields.get("comment") or {}).get("comments") or []:
        body = adf_to_text(c.get("body")).strip()
        if not body:
            continue
        entry = {
            "created": (c.get("created") or "")[:16],
            "author": (c.get("author") or {}).get("displayName", ""),
            "text": body,
        }
        comments_out.append(entry)
        all_text += body + "\n"

    hints = extract_hints(all_text)
    payload = {
        "key": a.key,
        "status": status,
        "summary": summary,
        "description": desc_text,
        "comments": comments_out[-5:],
        "hints": hints,
        "labels": fields.get("labels") or [],
    }

    if a.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"=== {a.key} [{status}] ===")
        print(f"Summary: {summary}")
        if desc_text:
            print(f"\nDescription:\n{desc_text[:2000]}")
        if comments_out:
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
        script = os.path.join(ROOT, "scripts", "factory_log.sh")
        cmd = [script, slug, a.key, "handoff_read", *log_args]
        subprocess.run(cmd, check=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
