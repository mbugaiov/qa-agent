#!/usr/bin/env python3
"""Require smoke_pack=pass when projects/<slug>/automation has an acceptance smoke pack.

Pack exists when any of:
  - automation/specs/acceptance-smoke.spec.js
  - automation/SMOKE_PACK (marker file)

Used by factory_tick_gate (DONE) and github_close_issue / jira_close_issue.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

PASS_VALUES = frozenset({"pass", "true", "1", "yes", "ok", "green"})


def smoke_pack_path(project_dir: str) -> str | None:
    auto = os.path.join(project_dir, "automation")
    candidates = [
        os.path.join(auto, "specs", "acceptance-smoke.spec.js"),
        os.path.join(auto, "SMOKE_PACK"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def pack_exists(project_dir: str) -> bool:
    return smoke_pack_path(project_dir) is not None


def _ledger_candidates(project_dir: str, key: str) -> list[str]:
    runs = os.path.join(project_dir, "factory", "runs")
    key = key.strip()
    names = {key, key.upper(), key.lower()}
    if "#" in key:
        slug, _, num = key.partition("#")
        names.add(f"{slug.upper()}#{num}")
        names.add(f"{slug.lower()}#{num}")
    return [os.path.join(runs, f"{n}.jsonl") for n in names]


def load_events(project_dir: str, key: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in _ledger_candidates(project_dir, key):
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    # Also scan _loop for smoke_pack events this project
    loop = os.path.join(project_dir, "factory", "runs", "_loop.jsonl")
    if os.path.isfile(loop):
        with open(loop, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    return out


def has_smoke_pack_pass(
    events: list[dict[str, Any]], dod: dict[str, Any] | None = None
) -> bool:
    if dod is not None:
        detail = dod.get("detail") if isinstance(dod.get("detail"), dict) else dod
        if str(detail.get("smoke_pack", "")).lower() in PASS_VALUES:
            return True
    for ev in events:
        if ev.get("event") != "smoke_pack":
            continue
        detail = ev.get("detail") if isinstance(ev.get("detail"), dict) else {}
        if str(detail.get("result", "")).lower() in PASS_VALUES:
            return True
        if str(detail.get("smoke_pack", "")).lower() in PASS_VALUES:
            return True
    # Latest terminal dod_check may carry smoke_pack=
    for ev in reversed(events):
        if ev.get("event") != "dod_check":
            continue
        detail = ev.get("detail") if isinstance(ev.get("detail"), dict) else {}
        if str(detail.get("verdict", "")).upper() != "DONE":
            continue
        if str(detail.get("smoke_pack", "")).lower() in PASS_VALUES:
            return True
        break
    return False


def require_smoke_pack_pass(
    project_dir: str,
    key: str,
    *,
    allow_missing: bool = False,
    events: list[dict[str, Any]] | None = None,
    dod: dict[str, Any] | None = None,
) -> None:
    """Exit 5 when pack exists and ledger lacks smoke_pack=pass."""
    if allow_missing or not pack_exists(project_dir):
        return
    evs = events if events is not None else load_events(project_dir, key)
    if has_smoke_pack_pass(evs, dod):
        return
    pack = smoke_pack_path(project_dir)
    print(
        f"SMOKE_PACK_REQUIRED {key}: acceptance smoke pack exists ({pack}) "
        f"but ledger has no smoke_pack=pass — run "
        f"`scripts/run_automation.sh <slug> --stg --suite acceptance-smoke.spec.js` "
        f"then `factory_log … smoke_pack result=pass` (or dod_check smoke_pack=pass). "
        f"Done blocked.",
        file=sys.stderr,
    )
    raise SystemExit(5)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--allow-missing-smoke-pack", action="store_true")
    a = ap.parse_args()
    try:
        require_smoke_pack_pass(
            a.project,
            a.key,
            allow_missing=a.allow_missing_smoke_pack,
        )
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1
    print(f"SMOKE_PACK_OK {a.key}" if pack_exists(a.project) else f"SMOKE_PACK_N/A {a.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
