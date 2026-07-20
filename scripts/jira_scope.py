#!/usr/bin/env python3
"""Query Jira for QA loop retest scope (Validate/Testing + In Progress under epic).

Usage:
    python3 scripts/jira_scope.py --project projects/<slug>
    python3 scripts/jira_scope.py --project projects/<slug> --json
    python3 scripts/jira_scope.py --project projects/<slug> --log

Reads JIRA_SCOPE_JQL from projects/<slug>/.secrets/jira.env when set; otherwise
derives from JIRA_EPIC_FOR_TASKS_BUGS with:
  parent = <EPIC> AND status in ("In Progress", "Validate/Testing")

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
import urllib.parse

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("The 'requests' package is required: pip install requests")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER = {"", "<atlassian api token>", "you@company.com", "https://<company>.atlassian.net"}


def log_scope_check(slug: str, keys: list[str], shell_mode: bool) -> None:
    script = os.path.join(ROOT, "scripts", "factory_log.sh")
    subprocess.run(
        [script, slug, "_loop", "scope_check", f"keys={','.join(keys)}", f"count={len(keys)}"],
        check=False,
        stdout=subprocess.DEVNULL if shell_mode else None,
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
    epic = m.group(1) if m else cfg.get("JIRA_PROJECT_KEY", "")
    if not epic:
        return 'status in ("In Progress", "Validate/Testing")'
    return f'parent={epic} AND status in ("In Progress", "Validate/Testing")'


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
    if base in PLACEHOLDER or email in PLACEHOLDER or token in PLACEHOLDER or not (base and email and token):
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
            log_scope_check(slug, [], a.shell)
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
        log_scope_check(slug, keys, a.shell)
    return 0


if __name__ == "__main__":
    sys.exit(main())
