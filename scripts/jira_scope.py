#!/usr/bin/env python3
"""Query Jira for QA loop retest scope (Validate/Testing + In Progress under epic).

Usage:
    python3 scripts/jira_scope.py --project projects/<slug>
    python3 scripts/jira_scope.py --project projects/<slug> --json
    python3 scripts/jira_scope.py --project projects/<slug> --log

Reads JIRA_SCOPE_JQL from projects/<slug>/.secrets/jira.env when set; otherwise
derives from JIRA_EPIC_FOR_TASKS_BUGS with:
  parent = <EPIC> AND status in ("In Progress", "Validate/Testing")
If no epic but JIRA_PROJECT_KEY is set:
  project = <KEY> AND status in ("In Progress", "Validate/Testing")
(Never uses a bare project key as parent= — parent expects an issue key.)

Prints keys (comma-separated) and count on stdout; --json emits {"keys":[],"count":N,"jql":"..."}.
With --log, appends scope_check to the factory ledger via factory_log.sh.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("The 'requests' package is required: pip install requests")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_CLAUSE = 'status in ("In Progress", "Validate/Testing")'


def is_placeholder(v: str) -> bool:
    """Match jira_status.sh / create_jira_issue.py inactive gating.

    Template values in projects/_template/jira.env.example (your-company, paste-*, ABC)
    must be treated as unconfigured — never call the API.
    """
    return (not v) or ("your-company" in v) or v.startswith("paste-") or v == "ABC"


def log_scope_check(slug: str, keys: list[str]) -> None:
    script = os.path.join(ROOT, "scripts", "factory_log.sh")
    # Always quiet: jira_scope owns stdout (--json/--shell/plain); ledger is the side effect.
    subprocess.run(
        [script, slug, "_loop", "scope_check", f"keys={','.join(keys)}", f"count={len(keys)}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


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


def default_jql(cfg: dict[str, str]) -> str:
    explicit = cfg.get("JIRA_SCOPE_JQL", "").strip()
    if explicit:
        return explicit
    epic_url = cfg.get("JIRA_EPIC_FOR_TASKS_BUGS", "")
    m = re.search(r"([A-Z][A-Z0-9]+-\d+)", epic_url)
    if m:
        return f"parent={m.group(1)} AND {STATUS_CLAUSE}"
    project = cfg.get("JIRA_PROJECT_KEY", "").strip()
    if project and re.fullmatch(r"[A-Z][A-Z0-9]+", project):
        return f"project={project} AND {STATUS_CLAUSE}"
    return STATUS_CLAUSE


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="projects/<slug>")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--shell", action="store_true", help="Shell exports: keys= count= jql= (for eval)")
    ap.add_argument("--log", action="store_true", help="Log scope_check to factory ledger")
    ap.add_argument("--jql", help="Override JQL (default: JIRA_SCOPE_JQL or epic-derived)")
    a = ap.parse_args()

    slug = os.path.basename(a.project.rstrip("/"))
    cfg = load_env_file(os.path.join(a.project, ".secrets", "jira.env"))
    base = cfg.get("JIRA_BASE_URL", "")
    email = cfg.get("JIRA_EMAIL", "")
    token = cfg.get("JIRA_API_TOKEN", "")
    project_key = cfg.get("JIRA_PROJECT_KEY", "")
    inactive = (
        is_placeholder(base)
        or is_placeholder(email)
        or is_placeholder(token)
        or is_placeholder(project_key)
    )
    if inactive:
        # Offline/no-op when unconfigured (same contract as create_jira_issue.py).
        payload = {"keys": [], "count": 0, "jql": "", "inactive": True}
        if a.json:
            print(json.dumps(payload))
        else:
            if a.shell:
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
        if a.log:
            log_scope_check(slug, [])
        return 0

    jql = a.jql or default_jql(cfg)
    base = base.rstrip("/")
    auth = HTTPBasicAuth(email, token)
    url = f"{base}/rest/api/3/search/jql"
    params = {
        "jql": jql,
        "maxResults": 50,
        "fields": "key,summary,status",
    }
    r = requests.get(url, auth=auth, headers={"Accept": "application/json"}, params=params, timeout=30)
    if r.status_code >= 300:
        print(f"ERROR jira search: {r.status_code} {r.text}", file=sys.stderr)
        return 1
    data = r.json()
    issues = data.get("issues") or []
    keys = [i["key"] for i in issues]
    payload = {"keys": keys, "count": len(keys), "jql": jql, "inactive": False}
    if a.json:
        print(json.dumps(payload, indent=2))
    elif a.shell:
        joined = ",".join(keys)
        n = len(keys)
        # Export both short names (keys/count) and SCOPE_* aliases — agents often check the wrong one.
        print(f"keys={shlex.quote(joined)}")
        print(f"count={n}")
        print(f"SCOPE_KEYS={shlex.quote(joined)}")
        print(f"SCOPE_COUNT={n}")
        print(f"SCOPE_JQL={shlex.quote(jql)}")
        print(f"jql={shlex.quote(jql)}")
    else:
        print(f"keys={','.join(keys)}")
        print(f"count={len(keys)}")
        print(f"jql={jql}")

    if a.log:
        log_scope_check(slug, keys)
    return 0


if __name__ == "__main__":
    sys.exit(main())
