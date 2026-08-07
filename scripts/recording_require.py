#!/usr/bin/env python3
"""Require ledger recording_attached=true (or recording_exempt) before Done close.

Inline GIF/PNG via record_and_attach.sh / github_attach_evidence.py must land on the
tracker before github_close_issue / jira_close_issue. Escape hatch only:
--allow-missing-recording.
"""
from __future__ import annotations

import os
import sys
from typing import Any

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

# Reuse ledger loaders from the smoke-pack gate (same factory/runs layout).
from smoke_pack_require import load_events  # noqa: E402

TRUE_VALUES = frozenset({"true", "1", "yes", "pass", "ok"})


def _detail(ev_or_dod: dict[str, Any] | None) -> dict[str, Any]:
    if not ev_or_dod:
        return {}
    if isinstance(ev_or_dod.get("detail"), dict):
        return ev_or_dod["detail"]  # type: ignore[return-value]
    return ev_or_dod


def has_recording_exempt(
    events: list[dict[str, Any]], dod: dict[str, Any] | None = None
) -> bool:
    detail = _detail(dod)
    if str(detail.get("recording_exempt", "")).lower() in TRUE_VALUES:
        return True
    for ev in events:
        if ev.get("event") not in ("dod_check", "recording_attached", "recording_exempt"):
            continue
        d = _detail(ev)
        if str(d.get("recording_exempt", "")).lower() in TRUE_VALUES:
            return True
        if str(d.get("result", "")).lower() == "exempt":
            return True
    return False


def has_recording_attached(
    events: list[dict[str, Any]], dod: dict[str, Any] | None = None
) -> bool:
    detail = _detail(dod)
    if str(detail.get("recording_attached", "")).lower() in TRUE_VALUES:
        return True
    for ev in events:
        if ev.get("event") == "recording_attached":
            d = _detail(ev)
            if str(d.get("result", "")).lower() in TRUE_VALUES:
                return True
            if str(d.get("recording_attached", "")).lower() in TRUE_VALUES:
                return True
        if ev.get("event") != "dod_check":
            continue
        d = _detail(ev)
        if str(d.get("verdict", "")).upper() != "DONE":
            continue
        if str(d.get("recording_attached", "")).lower() in TRUE_VALUES:
            return True
    return False


def require_recording_attached(
    project_dir: str,
    key: str,
    *,
    allow_missing: bool = False,
    events: list[dict[str, Any]] | None = None,
    dod: dict[str, Any] | None = None,
) -> None:
    """Exit 6 when ledger lacks recording_attached and is not exempt."""
    if allow_missing:
        return
    evs = events if events is not None else load_events(project_dir, key)
    if has_recording_exempt(evs, dod):
        return
    if has_recording_attached(evs, dod):
        return
    print(
        f"RECORDING_REQUIRED {key}: ledger has no recording_attached=true "
        f"(and no recording_exempt) — run "
        f"`scripts/record_and_attach.sh <slug> <KEY> <steps.json> \"caption\"` "
        f"then factory_log <slug> <KEY> recording_attached result=pass "
        f"(or dod_check recording_attached=true). "
        f"GitHub: one inline GIF in the issue comment. Done blocked.",
        file=sys.stderr,
    )
    raise SystemExit(6)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--allow-missing-recording", action="store_true")
    a = ap.parse_args()
    try:
        require_recording_attached(
            a.project,
            a.key,
            allow_missing=a.allow_missing_recording,
        )
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1
    print(f"RECORDING_OK {a.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
