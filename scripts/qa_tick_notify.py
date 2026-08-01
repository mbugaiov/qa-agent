#!/usr/bin/env python3
"""Teams Adaptive Card notification for QA factory tick (wake / idle).

Mirrors Hephaestus / dev-factory tick notify (Adaptive Card + optional webhook).

Webhook (optional; same Power Automate channel as Hephaestus when URLs match):
  QA_FACTORY_TEAMS_WEBHOOK_URL  (preferred)
  AGENT_TEAMS_WEBHOOK_URL       (shared fallback)
  DEV_FACTORY_TEAMS_WEBHOOK_URL (shared fallback)

Usage:
  python3 scripts/qa_tick_notify.py --slug <slug> --wake --keys ABC-1,ABC-2 [--summaries 'ABC-1: a|ABC-2: b']
  python3 scripts/qa_tick_notify.py --slug <slug> --idle
  python3 scripts/qa_tick_notify.py --slug <slug> --smoke [--idle]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TICK_NOTIFY_FAILED = "QA_TICK_NOTIFY_FAILED"
DEFAULT_INTERVAL_SEC = 1200
DEFAULT_POST_TIMEOUT_SEC = 8.0


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


def get_teams_webhook_url(env: dict[str, str] | None = None) -> str | None:
    src = env if env is not None else os.environ
    for name in (
        "QA_FACTORY_TEAMS_WEBHOOK_URL",
        "AGENT_TEAMS_WEBHOOK_URL",
        "DEV_FACTORY_TEAMS_WEBHOOK_URL",
    ):
        url = (src.get(name) or "").strip()
        if url:
            return url
    return None


def check_webhook_url(raw: str | None) -> dict[str, Any]:
    url = (raw or "").strip()
    if not url:
        return {
            "ok": False,
            "problem": "not_configured",
            "detail": "QA_FACTORY_TEAMS_WEBHOOK_URL is not set — Teams tick notification disabled",
        }
    from urllib.parse import urlparse, parse_qs

    try:
        parsed = urlparse(url)
    except Exception:
        return {
            "ok": False,
            "problem": "not_absolute",
            "detail": f"not a valid absolute URL (length {len(url)}) — likely truncated",
        }
    if not parsed.scheme or not parsed.netloc:
        return {
            "ok": False,
            "problem": "not_absolute",
            "detail": f"not a valid absolute URL (length {len(url)}) — likely truncated",
        }
    if parsed.scheme != "https":
        return {
            "ok": False,
            "problem": "not_https",
            "detail": f"expected https, got {parsed.scheme}:",
        }
    host = parsed.hostname or ""
    needs_sig = host.endswith("logic.azure.com") or host.endswith("azure.com") or "powerplatform.com" in host
    if needs_sig:
        qs = parse_qs(parsed.query)
        if not qs.get("sig"):
            return {
                "ok": False,
                "problem": "missing_signature",
                "detail": "missing sig query parameter — value was truncated (quote the URL in .secrets/jira.env)",
            }
    return {"ok": True, "url": url}


def format_next_wake_utc(
    next_wake_utc: str | None = None,
    *,
    interval_sec: int | None = None,
    epoch_env: str | None = None,
) -> str:
    if next_wake_utc and next_wake_utc.strip():
        return next_wake_utc.strip()
    epoch_raw = epoch_env if epoch_env is not None else os.environ.get("QA_FACTORY_NEXT_WAKE_EPOCH", "")
    if epoch_raw.strip().isdigit():
        dt = datetime.fromtimestamp(int(epoch_raw.strip()), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    sec = interval_sec
    if sec is None:
        try:
            sec = int(os.environ.get("QA_LOOP_INTERVAL_SEC", str(DEFAULT_INTERVAL_SEC)))
        except ValueError:
            sec = DEFAULT_INTERVAL_SEC
    dt = datetime.now(timezone.utc) + timedelta(seconds=max(0, sec))
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def build_tick_notify_summary(
    *,
    slug: str,
    kind: str,
    count: int = 0,
    issues: list[dict[str, str]] | None = None,
    next_wake_utc: str | None = None,
) -> str:
    nxt = format_next_wake_utc(next_wake_utc)
    if kind == "idle":
        return f"[{slug}] QA factory idle — no retest tickets. Next tick: {nxt}"
    issues = issues or []
    pick = issues[0] if issues else {"key": "?", "summary": "(empty)"}
    others = f" (+{count - 1} more in scope)" if count > 1 else ""
    return (
        f"[{slug}] QA factory execute — scope {pick['key']}: {pick['summary']}{others}. "
        f"Next tick: {nxt}"
    )


# Adaptive Card title colour for Argus / QA (distinct from Hephaestus/Athena).
QA_FACTORY_CARD_COLOR = "Warning"
QA_FACTORY_AGENT_ID = "Argus / QA"


def build_tick_notify_webhook_body(
    *,
    slug: str,
    kind: str,
    count: int = 0,
    issues: list[dict[str, str]] | None = None,
    next_wake_utc: str | None = None,
) -> dict[str, Any]:
    issues = issues or []
    summary = build_tick_notify_summary(
        slug=slug, kind=kind, count=count, issues=issues, next_wake_utc=next_wake_utc
    )
    title = (
        "Argus · QA factory idle" if kind == "idle" else "Argus · QA factory execute"
    )
    facts: list[dict[str, str]] = [
        {"title": "Agent", "value": QA_FACTORY_AGENT_ID},
        {"title": "Project", "value": slug},
        {"title": "Tick", "value": "idle" if kind == "idle" else "retest scope"},
        {"title": "Next tick (UTC)", "value": format_next_wake_utc(next_wake_utc)},
    ]
    if kind == "wake":
        facts.insert(0, {"title": "Scope", "value": str(count)})
        if issues:
            pick = issues[0]
            facts.insert(0, {"title": "Pick", "value": f"{pick['key']} — {pick['summary']}"})
        if len(issues) > 1:
            facts.append(
                {
                    "title": "Queue",
                    "value": " · ".join(
                        f"{i['key']}: {i['summary']}" for i in issues[:5]
                    ),
                }
            )
    return {
        "type": "message",
        "summary": summary,
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "msteams": {"width": "Full"},
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": title,
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": QA_FACTORY_CARD_COLOR,
                            "wrap": True,
                        },
                        {"type": "FactSet", "facts": facts, "spacing": "Medium"},
                    ],
                },
            }
        ],
    }


def should_report_outcome(outcome: dict[str, Any]) -> bool:
    return (not outcome.get("delivered")) and outcome.get("reason") != "not_configured"


def format_tick_notify_failure(slug: str, kind: str, outcome: dict[str, Any]) -> str:
    if not should_report_outcome(outcome):
        raise ValueError("format_tick_notify_failure called on delivered/unconfigured outcome")
    payload: dict[str, Any] = {
        "slug": slug,
        "tick": kind,
        "reason": outcome.get("reason"),
        "detail": outcome.get("detail"),
        "remediation": (
            "Teams tick notification was NOT delivered. Verify QA_FACTORY_TEAMS_WEBHOOK_URL "
            "is quoted in projects/<slug>/.secrets/jira.env (same URL as DEV_FACTORY_TEAMS_WEBHOOK_URL)."
        ),
    }
    if "status" in outcome and outcome["status"] is not None:
        payload["status"] = outcome["status"]
    return f"{TICK_NOTIFY_FAILED} {json.dumps(payload)}"


def post_qa_tick_notify(
    *,
    slug: str,
    kind: str,
    count: int = 0,
    issues: list[dict[str, str]] | None = None,
    next_wake_utc: str | None = None,
    webhook_url: str | None = None,
    timeout: float = DEFAULT_POST_TIMEOUT_SEC,
) -> dict[str, Any]:
    check = check_webhook_url(webhook_url if webhook_url is not None else get_teams_webhook_url())
    if not check["ok"]:
        if check["problem"] == "not_configured":
            return {"delivered": False, "reason": "not_configured", "detail": check["detail"]}
        return {
            "delivered": False,
            "reason": "invalid_webhook_url",
            "detail": f"{check['problem']}: {check['detail']}",
        }

    body = build_tick_notify_webhook_body(
        slug=slug, kind=kind, count=count, issues=issues, next_wake_utc=next_wake_utc
    )
    data = json.dumps(body).encode("utf-8")
    req = Request(
        check["url"],
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as res:
            status = getattr(res, "status", 200)
            if 200 <= int(status) < 300:
                return {"delivered": True, "status": int(status)}
            detail = f"webhook responded {status}"
            try:
                text = res.read().decode("utf-8", errors="replace").strip()
                if text:
                    detail += f": {text[:300]}"
            except Exception:
                pass
            return {"delivered": False, "reason": "http_error", "detail": detail, "status": int(status)}
    except HTTPError as err:
        detail = f"webhook responded {err.code}"
        try:
            text = err.read().decode("utf-8", errors="replace").strip()
            if text:
                detail += f": {text[:300]}"
        except Exception:
            pass
        return {"delivered": False, "reason": "http_error", "detail": detail, "status": err.code}
    except URLError as err:
        return {"delivered": False, "reason": "exception", "detail": str(err.reason or err)}
    except Exception as err:
        return {"delivered": False, "reason": "exception", "detail": str(err)}


def notify_from_scope(
    *,
    slug: str,
    keys: list[str],
    issues: list[dict[str, str]] | None = None,
    cfg: dict[str, str] | None = None,
    report: bool = True,
) -> dict[str, Any]:
    """Post wake/idle card after jira_scope --log. Quiet when webhook unset.

    STRICT per-project isolation: when ``cfg`` is provided (project
    ``.secrets/jira.env``), the webhook is resolved from that file only —
    ambient ``*_TEAMS_WEBHOOK_URL`` env vars are ignored (Unset = quiet).
    """
    # Webhook: file-only when cfg provided (match create_jira_issue.resolve_config).
    if cfg is not None:
        webhook = get_teams_webhook_url(cfg)
    else:
        webhook = get_teams_webhook_url()
    # Timing hints may come from ambient or file; not used for cross-project secrets.
    env = dict(os.environ)
    if cfg:
        env.update({k: v for k, v in cfg.items() if v})
    issue_list = issues or [{"key": k, "summary": k} for k in keys]
    kind = "idle" if not keys else "wake"
    try:
        interval = int(env.get("QA_LOOP_INTERVAL_SEC", str(DEFAULT_INTERVAL_SEC)))
    except ValueError:
        interval = DEFAULT_INTERVAL_SEC
    next_wake = format_next_wake_utc(
        epoch_env=env.get("QA_FACTORY_NEXT_WAKE_EPOCH", ""),
        interval_sec=interval,
    )
    # Pass "" (not None) so post_qa_tick_notify does not fall back to ambient env.
    outcome = post_qa_tick_notify(
        slug=slug,
        kind=kind,
        count=len(keys),
        issues=issue_list if kind == "wake" else None,
        next_wake_utc=next_wake,
        webhook_url=webhook or "",
    )
    if report and should_report_outcome(outcome):
        print(format_tick_notify_failure(slug, kind, outcome), file=sys.stderr)
    return outcome


def _parse_summaries(raw: str | None, keys: list[str]) -> list[dict[str, str]]:
    if not raw:
        return [{"key": k, "summary": k} for k in keys]
    # Format: KEY: summary|KEY2: summary2
    by_key: dict[str, str] = {}
    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            k, s = part.split(":", 1)
            by_key[k.strip()] = s.strip()
        else:
            by_key[part] = part
    return [{"key": k, "summary": by_key.get(k, k)} for k in keys]


def main() -> int:
    ap = argparse.ArgumentParser(description="QA factory Teams tick notify")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--project", help="projects/<slug> (loads .secrets/jira.env)")
    ap.add_argument("--wake", action="store_true")
    ap.add_argument("--idle", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="Send a sample card (exit 1 if not delivered)")
    ap.add_argument("--keys", default="", help="Comma-separated issue keys")
    ap.add_argument("--summaries", default="", help="KEY: summary|KEY2: summary2")
    ap.add_argument("--next-wake", default="", help="Override next wake UTC string")
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proj = a.project or os.path.join(root, "projects", a.slug)
    cfg = load_env_file(os.path.join(proj, ".secrets", "jira.env"))
    # File wins over ambient (setdefault would let a leftover shell webhook win).
    for k, v in cfg.items():
        if v:
            os.environ[k] = v
    # Resolve webhook from project file only — ambient unset/leftover ignored.
    webhook = get_teams_webhook_url(cfg)

    if a.smoke:
        kind = "idle" if a.idle else "wake"
        issues = [
            {
                "key": "SMOKE-TEST",
                "summary": "QA tick notify smoke test — safe to ignore",
            }
        ]
        outcome = post_qa_tick_notify(
            slug=a.slug,
            kind=kind,
            count=1 if kind == "wake" else 0,
            issues=issues if kind == "wake" else None,
            next_wake_utc=a.next_wake
            or format_next_wake_utc(interval_sec=DEFAULT_INTERVAL_SEC),
            webhook_url=webhook or "",
        )
        if outcome.get("delivered"):
            print(
                f'TICK_NOTIFY_SMOKE_OK {{"slug":"{a.slug}","status":{outcome.get("status")},"kind":"{kind}"}}'
            )
            return 0
        check = check_webhook_url(webhook or "")
        if not check["ok"] and check["problem"] == "not_configured":
            print(
                f'TICK_NOTIFY_SMOKE_FAILED {{"slug":"{a.slug}","problem":"not_configured","detail":{json.dumps(check["detail"])}}}',
                file=sys.stderr,
            )
            print(
                "Teams notification is optional. Set a QUOTED QA_FACTORY_TEAMS_WEBHOOK_URL "
                f"(same URL as DEV_FACTORY) in projects/{a.slug}/.secrets/jira.env",
                file=sys.stderr,
            )
            return 1
        if should_report_outcome(outcome):
            print(format_tick_notify_failure(a.slug, kind, outcome), file=sys.stderr)
        return 1

    if a.idle and a.wake:
        print("Pass only one of --wake / --idle", file=sys.stderr)
        return 2
    kind = "idle" if a.idle or (not a.wake and not a.keys) else "wake"
    keys = [k.strip() for k in a.keys.split(",") if k.strip()]
    issues = _parse_summaries(a.summaries or None, keys)
    outcome = post_qa_tick_notify(
        slug=a.slug,
        kind=kind,
        count=len(keys),
        issues=issues if kind == "wake" else None,
        next_wake_utc=a.next_wake or None,
        webhook_url=webhook or "",
    )
    if outcome.get("delivered"):
        print(json.dumps({"delivered": True, "kind": kind, "status": outcome.get("status")}))
        return 0
    if should_report_outcome(outcome):
        print(format_tick_notify_failure(a.slug, kind, outcome), file=sys.stderr)
        return 1
    print(json.dumps({"delivered": False, "reason": outcome.get("reason")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
