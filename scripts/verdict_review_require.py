#!/usr/bin/env python3
"""Require qa-verdict-review pass in the factory ledger before Done / FAIL / RETURN.

Used by jira_close_issue / github_close_issue / return scripts so projects cannot
bypass the engine gate by closing tracker tickets without a ledgered review.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

PASS_VALUES = frozenset({"pass", "true", "1", "yes"})
TERMINAL = frozenset({"DONE", "FAIL", "RETURN_DEV"})


def _ledger_candidates(project_dir: str, key: str) -> list[str]:
    runs = os.path.join(project_dir, "factory", "runs")
    key = key.strip()
    names = {key, key.upper(), key.lower()}
    if "#" in key:
        slug, _, num = key.partition("#")
        names.add(f"{slug.upper()}#{num}")
        names.add(f"{slug.lower()}#{num}")
    return [os.path.join(runs, f"{n}.jsonl") for n in names]


def find_ledger_path(project_dir: str, key: str) -> str | None:
    for path in _ledger_candidates(project_dir, key):
        if os.path.isfile(path):
            return path
    return None


def load_events(project_dir: str, key: str) -> list[dict[str, Any]]:
    path = find_ledger_path(project_dir, key)
    if not path:
        return []
    out: list[dict[str, Any]] = []
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
    return out


def latest_terminal_dod(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for ev in events:
        if ev.get("event") != "dod_check":
            continue
        detail = ev.get("detail") if isinstance(ev.get("detail"), dict) else {}
        verdict = str(detail.get("verdict", "")).upper()
        if verdict in TERMINAL:
            latest = ev
    return latest


def has_verdict_review_pass(
    events: list[dict[str, Any]], dod: dict[str, Any] | None = None
) -> bool:
    """Mirror factory_tick_gate.has_verdict_review_pass (full ticket ledger)."""
    if dod is None:
        dod = latest_terminal_dod(events)
    if dod is not None:
        detail = dod.get("detail") if isinstance(dod.get("detail"), dict) else {}
        if str(detail.get("verdict_review", "")).lower() in PASS_VALUES:
            return True
    for ev in events:
        if ev.get("event") != "verdict_review":
            continue
        detail = ev.get("detail") if isinstance(ev.get("detail"), dict) else {}
        if str(detail.get("result", "")).lower() in PASS_VALUES:
            return True
    return False


def require_verdict_review_pass(
    project_dir: str,
    key: str,
    *,
    allow_missing: bool = False,
    require_terminal_dod: bool = True,
) -> None:
    """Exit non-zero when ledger lacks verdict_review=pass for this ticket."""
    if allow_missing:
        print(
            f"WARNING: skipping verdict_review ledger check for {key} (--allow-missing-verdict-review)",
            file=sys.stderr,
        )
        return

    events = load_events(project_dir, key)
    dod = latest_terminal_dod(events)
    if require_terminal_dod and dod is None:
        print(
            f"VERDICT_REVIEW_REQUIRED {key}: missing terminal dod_check "
            f"(DONE/FAIL/RETURN_DEV) in factory/runs — log dod_check with "
            f"verdict_review=pass after skill qa-verdict-review + check_verdict_review.sh",
            file=sys.stderr,
        )
        raise SystemExit(4)
    if has_verdict_review_pass(events, dod):
        return
    print(
        f"VERDICT_REVIEW_REQUIRED {key}: no verdict_review=pass in ledger "
        f"(skill qa-verdict-review → check_verdict_review.sh → "
        f"factory_log … verdict_review result=pass OR dod_check verdict_review=pass). "
        f"Close/return blocked.",
        file=sys.stderr,
    )
    raise SystemExit(4)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--allow-missing-verdict-review", action="store_true")
    a = ap.parse_args()
    try:
        require_verdict_review_pass(
            a.project,
            a.key,
            allow_missing=a.allow_missing_verdict_review,
        )
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1
    print(f"VERDICT_REVIEW_OK {a.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
