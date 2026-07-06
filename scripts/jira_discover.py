#!/usr/bin/env python3
"""Discover per-project Jira ids to fill .secrets/jira.env.

Reads the connection block (JIRA_BASE_URL/EMAIL/API_TOKEN/PROJECT_KEY) from
projects/<slug>/.secrets/jira.env and prints, for THIS Jira instance:
  - assignee accountId (the token owner)
  - scrum board id(s) for the project + the active sprint
  - the board's estimation field (e.g. timeoriginalestimate)
  - Story Points field id(s)

Usage: python3 scripts/jira_discover.py <slug>
Then paste the suggested values into projects/<slug>/.secrets/jira.env.
"""
from __future__ import annotations
import os, sys
try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("pip install requests")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(slug: str) -> dict:
    path = os.path.join(ROOT, "projects", slug, ".secrets", "jira.env")
    if not os.path.exists(path):
        sys.exit(f"Missing {path}")
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: jira_discover.py <slug>")
    cfg = load_env(sys.argv[1])
    b = cfg["JIRA_BASE_URL"].rstrip("/")
    auth = HTTPBasicAuth(cfg["JIRA_EMAIL"], cfg["JIRA_API_TOKEN"])
    H = {"Accept": "application/json"}
    pk = cfg.get("JIRA_PROJECT_KEY", "")

    me = requests.get(f"{b}/rest/api/3/myself", auth=auth, headers=H, timeout=30).json()
    print(f"JIRA_ASSIGNEE_ACCOUNT_ID={me.get('accountId')}   # {me.get('displayName')}")

    fields = requests.get(f"{b}/rest/api/3/field", auth=auth, headers=H, timeout=30).json()
    sp = [f for f in fields if "story point" in f.get("name", "").lower()]
    sprint = [f for f in fields if f.get("name", "").lower() == "sprint"]
    for f in sp:
        print(f"# Story-points candidate: {f['id']}  ({f['name']})")
    if sprint:
        print(f"JIRA_SPRINT_FIELD={sprint[0]['id']}")

    boards = requests.get(f"{b}/rest/agile/1.0/board", params={"projectKeyOrId": pk}, auth=auth, headers=H, timeout=30).json().get("values", [])
    for bd in boards:
        print(f"JIRA_BOARD_ID={bd['id']}   # {bd['name']} ({bd['type']})")
        cfgr = requests.get(f"{b}/rest/agile/1.0/board/{bd['id']}/configuration", auth=auth, headers=H, timeout=30)
        if cfgr.status_code < 300:
            est = cfgr.json().get("estimation", {}).get("field", {})
            print(f"#   board estimation field: {est.get('fieldId')} ({est.get('displayName')})")
        sr = requests.get(f"{b}/rest/agile/1.0/board/{bd['id']}/sprint", params={"state": "active"}, auth=auth, headers=H, timeout=30)
        for s in (sr.json().get("values", []) if sr.status_code < 300 else []):
            print(f"#   active sprint: {s['id']} — {s['name']}")
    print("\n# Paste the JIRA_* lines above into projects/<slug>/.secrets/jira.env")
    print("# Pick the Story-points candidate the UI shows (often the higher id) as JIRA_STORYPOINTS_FIELD.")


if __name__ == "__main__":
    main()
