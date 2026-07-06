#!/usr/bin/env python3
"""Create a Jira issue (bug) for a project. Per-project connection + credentials.

Each project has its OWN Jira site + account (different companies), so all Jira
connection info lives in the project's gitignored secrets file:

    projects/<slug>/.secrets/jira.env      (KEY=VALUE, gitignored)
        JIRA_BASE_URL=https://<company>.atlassian.net
        JIRA_EMAIL=you@company.com
        JIRA_API_TOKEN=<atlassian API token>
        JIRA_PROJECT_KEY=ABC
        JIRA_ISSUE_TYPE=Bug            # optional, default "Bug"

STRICT per-project isolation: ONLY this project's .secrets/jira.env is used (ambient env is
ignored) so one project can never inherit another's Jira settings. Get an API token at:
    https://id.atlassian.com/manage-profile/security/api-tokens

Usage:
    python3 scripts/create_jira_issue.py --project projects/<slug> \
        --summary "BUG-103: title mismatch on board" \
        --description-file projects/<slug>/runs/<run>/bug-report.md \
        --severity S3 --labels qa-agent,<slug> \
        --attach projects/<slug>/runs/<run>/screenshots/02-display.png \
        [--priority Medium] [--dry-run]

Exit 0 on success (prints issue key + URL); non-zero on failure (prints Jira error body).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("The 'requests' package is required: pip install requests")

from jira_adf import adf_from_text

SEVERITY_LABEL = {"S1": "severity-s1", "S2": "severity-s2", "S3": "severity-s3", "S4": "severity-s4"}
SEVERITY_PRIORITY = {"S1": "Highest", "S2": "High", "S3": "Medium", "S4": "Low"}
SEVERITY_POINTS = {"S1": 5, "S2": 3, "S3": 2, "S4": 1}
SEVERITY_HOURS = {"S1": 8, "S2": 4, "S3": 2, "S4": 1}


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


def resolve_config(project_dir: str) -> dict:
    # STRICT per-project isolation: the project's own .secrets/jira.env is the ONLY source.
    # We deliberately do NOT read ambient os.environ here, so project A can never inherit
    # another project's (or a leftover shell's) JIRA_* values. CLI flags are the only override.
    return load_env_file(os.path.join(project_dir, ".secrets", "jira.env"))


def issue_key_from(value: str) -> str:
    """Accept a full browse URL or a bare key; return the issue key (e.g. ABC-123)."""
    if not value:
        return ""
    return value.rstrip("/").split("/")[-1].strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a Jira bug for a project")
    ap.add_argument("--project", required=True, help="path to projects/<slug>")
    ap.add_argument("--summary", required=True, help="issue summary (one line)")
    desc = ap.add_mutually_exclusive_group(required=True)
    desc.add_argument("--description", help="issue description text")
    desc.add_argument("--description-file", help="file whose contents become the description")
    ap.add_argument("--severity", choices=list(SEVERITY_LABEL), help="S1..S4 (adds label; maps priority with --set-priority)")
    ap.add_argument("--labels", default="", help="comma-separated labels (always adds 'qa-agent')")
    ap.add_argument("--priority", help="explicit Jira priority name (e.g. Medium)")
    ap.add_argument("--set-priority", action="store_true", help="set priority from --severity map")
    ap.add_argument("--issue-type", help="override issue type (default from env or 'Bug')")
    ap.add_argument("--parent", help="parent epic key or URL (default from env JIRA_EPIC_FOR_TASKS_BUGS/JIRA_PARENT_KEY)")
    ap.add_argument("--no-parent", action="store_true", help="do not set a parent epic even if configured")
    ap.add_argument("--epic-link-field", help="custom field id for Epic Link (company-managed projects), e.g. customfield_10014")
    ap.add_argument("--points", type=float, help="story points (default from severity: S1=5,S2=3,S3=2,S4=1)")
    ap.add_argument("--estimate", help="original time estimate, e.g. '2h' (default from severity: S1=8h,S2=4h,S3=2h,S4=1h)")
    ap.add_argument("--no-sprint", action="store_true", help="do not add to the active sprint")
    ap.add_argument("--no-assignee", action="store_true", help="do not set the assignee")
    ap.add_argument(
        "--on-hold",
        action="store_true",
        help="after create, transition to On Hold (factory/dev must not pick up until released)",
    )
    ap.add_argument(
        "--on-hold-transition",
        default="",
        help="Jira transition id for On Hold (default: env JIRA_ON_HOLD_TRANSITION_ID or 41)",
    )
    ap.add_argument("--attach", action="append", default=[], help="file to attach (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="print the payload, do not call Jira")
    ap.add_argument(
        "--plain-description",
        action="store_true",
        help="treat description as plain text (one paragraph per line); default is Markdown → ADF",
    )
    args = ap.parse_args()

    cfg = resolve_config(args.project)
    base = (cfg.get("JIRA_BASE_URL") or "").rstrip("/")
    email = cfg.get("JIRA_EMAIL")
    token = cfg.get("JIRA_API_TOKEN")
    project_key = cfg.get("JIRA_PROJECT_KEY")
    issue_type = args.issue_type or cfg.get("JIRA_ISSUE_TYPE") or "Bug"

    def placeholder(v: str) -> bool:
        return (not v) or ("your-company" in v) or v.startswith("paste-") or v == "ABC"

    not_configured = placeholder(base) or placeholder(email) or placeholder(token) or placeholder(project_key)
    if not_configured and not args.dry_run:
        # Jira integration not active for this project → do nothing (no-op, not an error).
        print(f"Jira not configured for {args.project} — skipping (no Jira action taken).")
        return

    description = args.description
    if args.description_file:
        with open(args.description_file, encoding="utf-8") as fh:
            description = fh.read()

    labels = ["qa-agent"] + [l.strip() for l in args.labels.split(",") if l.strip()]
    if args.severity:
        labels.append(SEVERITY_LABEL[args.severity])

    fields = {
        "project": {"key": project_key},
        "summary": args.summary,
        "description": adf_from_text(description, markdown=not args.plain_description),
        "issuetype": {"name": issue_type},
        "labels": labels,
    }
    if args.priority:
        fields["priority"] = {"name": args.priority}
    elif args.set_priority and args.severity:
        fields["priority"] = {"name": SEVERITY_PRIORITY[args.severity]}

    # Parent epic: team-managed projects use fields.parent; company-managed use an Epic Link custom field.
    parent_key = "" if args.no_parent else issue_key_from(
        args.parent or cfg.get("JIRA_PARENT_KEY") or cfg.get("JIRA_EPIC_FOR_TASKS_BUGS") or "")
    epic_field = args.epic_link_field or cfg.get("JIRA_EPIC_LINK_FIELD")
    if parent_key:
        if epic_field:
            fields[epic_field] = parent_key
        else:
            fields["parent"] = {"key": parent_key}

    if not args.no_assignee and cfg.get("JIRA_ASSIGNEE_ACCOUNT_ID"):
        fields["assignee"] = {"accountId": cfg["JIRA_ASSIGNEE_ACCOUNT_ID"]}

    points = args.points if args.points is not None else (SEVERITY_POINTS.get(args.severity) if args.severity else None)
    estimate = args.estimate if args.estimate else (f"{SEVERITY_HOURS[args.severity]}h" if args.severity else None)

    payload = {"fields": fields}

    if args.dry_run:
        import json
        print(f"DRY RUN → POST {base}/rest/api/3/issue")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"Story points: {points} · add-to-active-sprint: {not args.no_sprint} (board {cfg.get('JIRA_BOARD_ID')})")
        print(f"Attachments: {args.attach}")
        return

    auth = HTTPBasicAuth(email, token)
    r = requests.post(f"{base}/rest/api/3/issue", json=payload, auth=auth,
                      headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=30)
    if r.status_code >= 300:
        print(f"Jira create failed [{r.status_code}]:\n{r.text}", file=sys.stderr)
        sys.exit(1)

    key = r.json().get("key")
    url = f"{base}/browse/{key}"
    print(f"Created {key} → {url}")

    jh = {"Accept": "application/json", "Content-Type": "application/json"}
    # Story points — set field(s) discovered for this Jira site (jira_discover.py)
    if points is not None:
        sp_fields = [f for f in [cfg.get("JIRA_STORYPOINTS_FIELD"), cfg.get("JIRA_STORYPOINTS_FIELD_ALT")] if f]
        ok = []
        for fld in sp_fields:
            if requests.put(f"{base}/rest/api/3/issue/{key}", json={"fields": {fld: points}}, auth=auth, headers=jh, timeout=30).status_code < 300:
                ok.append(fld)
        print(f"  story points = {points} ({', '.join(ok) or 'no JIRA_STORYPOINTS_FIELD configured'})")

    # Original time estimate (timetracking.originalEstimate)
    if estimate:
        es = requests.put(f"{base}/rest/api/3/issue/{key}", json={"fields": {"timetracking": {"originalEstimate": estimate}}}, auth=auth, headers=jh, timeout=30)
        print(f"  original estimate = {estimate} ({'ok' if es.status_code < 300 else 'FAILED '+str(es.status_code)})")

    # Add to the active sprint (resolve dynamically from the board)
    if not args.no_sprint and cfg.get("JIRA_BOARD_ID"):
        try:
            sr = requests.get(f"{base}/rest/agile/1.0/board/{cfg['JIRA_BOARD_ID']}/sprint", params={"state": "active"},
                              auth=auth, headers={"Accept": "application/json"}, timeout=30)
            sprints = sr.json().get("values", []) if sr.status_code < 300 else []
            if sprints:
                sid = sprints[0]["id"]
                mr = requests.post(f"{base}/rest/agile/1.0/sprint/{sid}/issue", json={"issues": [key]}, auth=auth,
                                   headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=30)
                print(f"  sprint = {sprints[0]['name']} (#{sid}) → {'ok' if mr.status_code < 300 else 'FAILED '+str(mr.status_code)}")
            else:
                print("  ! no active sprint found on board", file=sys.stderr)
        except Exception as exc:
            print(f"  ! sprint assignment error: {exc}", file=sys.stderr)

    for path in args.attach:
        if not os.path.exists(path):
            print(f"  ! attachment not found: {path}", file=sys.stderr)
            continue
        with open(path, "rb") as fh:
            ar = requests.post(
                f"{base}/rest/api/3/issue/{key}/attachments",
                auth=auth,
                headers={"X-Atlassian-Token": "no-check", "Accept": "application/json"},
                files={"file": (os.path.basename(path), fh)},
                timeout=60,
            )
        status = "ok" if ar.status_code < 300 else f"FAILED [{ar.status_code}]"
        print(f"  attached {os.path.basename(path)} → {status}")

    if args.on_hold:
        tid = args.on_hold_transition or cfg.get("JIRA_ON_HOLD_TRANSITION_ID") or "41"
        tr = requests.post(
            f"{base}/rest/api/3/issue/{key}/transitions",
            json={"transition": {"id": tid}},
            auth=auth,
            headers=jh,
            timeout=30,
        )
        print(f"  on hold (transition {tid}) → {'ok' if tr.status_code < 300 else 'FAILED '+tr.text}")

    print(key)  # last line = key, for capture


if __name__ == "__main__":
    main()
