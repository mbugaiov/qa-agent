#!/usr/bin/env python3
"""Collect agent usage: Tier A (exact), B (countable), C (proxy), D (estimated from local logs).

Methodology version 2.0 — see .cursor/skills/usage-accounting/SKILL.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

METHODOLOGY_VERSION = "2.0"

ROOT = Path(__file__).resolve().parent.parent
CURSOR_PROJECTS = Path.home() / ".cursor" / "projects"
CURSOR_LOGS = Path.home() / "Library/Application Support/Cursor/logs"
AGENT_REQUEST_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2})T.*span_completed name="agent\.request" .*durationMs=(\d+)'
)
DEFAULT_CALIBRATION = {
    "tokens_per_ms": 0.15,
    "tokens_per_ci_review": 120_000,
    "tokens_per_qa_tick": 200_000,
    "usd_per_mtok": 3.0,
    "cap_request_ms": 1_800_000,  # 30 min per agent.request — ignore idle overnight spans
}
TIMESTAMP_RE = re.compile(
    r"<timestamp>([^<]+)</timestamp>", re.IGNORECASE
)


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def parse_day(s: str) -> str | None:
    if not s:
        return None
    s = s.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    for fmt in (
        "%A, %b %d, %Y",
        "%A, %B %d, %Y",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            if fmt.endswith("%z") and s.endswith("Z"):
                s2 = s.replace("Z", "+00:00")
                return datetime.fromisoformat(s2).strftime("%Y-%m-%d")
            dt = datetime.strptime(s.replace(" (UTC-6)", "").replace(" (UTC+0)", ""), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def in_window(day: str, start: date, end: date) -> bool:
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return False
    return start <= d <= end


def gather_ledger(slug: str, start: date, end: date) -> dict:
    runs = ROOT / "projects" / slug / "factory" / "runs"
    if not runs.exists():
        return {"available": False, "reason": f"no ledger at projects/{slug}/factory/runs"}

    daily: dict[str, dict] = defaultdict(lambda: {
        "qa_ticks": 0,
        "tick_starts": 0,
        "ledger_events": 0,
        "events_by_agent": Counter(),
        "events_by_type": Counter(),
    })
    totals = Counter()

    for path in sorted(runs.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = ev.get("ts", "")
            day = ts[:10] if len(ts) >= 10 else None
            if not day or not in_window(day, start, end):
                continue
            bucket = daily[day]
            bucket["ledger_events"] += 1
            agent = ev.get("agent", "unknown")
            bucket["events_by_agent"][agent] += 1
            et = ev.get("event", "")
            bucket["events_by_type"][et] += 1
            totals["ledger_events"] += 1
            if et == "tick_end" or ev.get("ticket") == "tick_end":
                bucket["qa_ticks"] += 1
                totals["qa_ticks"] += 1
            if et == "tick_start":
                bucket["tick_starts"] += 1
                totals["tick_starts"] += 1

    by_day = {}
    for day, data in sorted(daily.items()):
        by_day[day] = {
            "qa_ticks": data["qa_ticks"],
            "tick_starts": data["tick_starts"],
            "ledger_events": data["ledger_events"],
            "events_by_agent": dict(data["events_by_agent"]),
            "events_by_type": dict(data["events_by_type"]),
        }

    return {
        "available": True,
        "tier": "B",
        "metric": "countable_invocations",
        "by_day": by_day,
        "totals": dict(totals),
    }


def gather_transcripts(start: date, end: date, workspace_glob: str | None) -> dict:
    if not CURSOR_PROJECTS.is_dir():
        return {
            "available": False,
            "tier": "C",
            "metric": "context_proxy_not_tokens",
            "reason": f"no Cursor projects dir at {CURSOR_PROJECTS}",
            "sessions_scanned": 0,
            "by_day": {},
            "totals": {"user_turns": 0, "assistant_turns": 0, "transcript_bytes": 0},
            "warning": "NOT LLM tokens — activity proxy only",
        }

    roots = []
    if workspace_glob:
        roots = list(CURSOR_PROJECTS.glob(workspace_glob))
    else:
        roots = [p for p in CURSOR_PROJECTS.iterdir() if p.is_dir()]

    daily: dict[str, dict] = defaultdict(lambda: {
        "user_turns": 0,
        "assistant_turns": 0,
        "transcript_bytes": 0,
    })
    sessions = 0

    for proj in roots:
        at = proj / "agent-transcripts"
        if not at.exists():
            continue
        for tf in at.glob("**/*.jsonl"):
            sessions += 1
            size = tf.stat().st_size
            day_from_file = datetime.fromtimestamp(
                tf.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%d")
            if in_window(day_from_file, start, end):
                daily[day_from_file]["transcript_bytes"] += size

            for line in tf.read_text(errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role = row.get("role")
                content = row.get("message", {}).get("content", [])
                text = ""
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text += part.get("text", "")
                day = None
                if role == "user":
                    m = TIMESTAMP_RE.search(text)
                    if m:
                        day = parse_day(m.group(1))
                if not day:
                    day = day_from_file
                if not in_window(day, start, end):
                    continue
                if role == "user":
                    daily[day]["user_turns"] += 1
                elif role == "assistant":
                    daily[day]["assistant_turns"] += 1

    by_day = {k: dict(v) for k, v in sorted(daily.items())}
    return {
        "available": sessions > 0,
        "tier": "C",
        "metric": "context_proxy_not_tokens",
        "sessions_scanned": sessions,
        "by_day": by_day,
        "totals": {
            "user_turns": sum(d["user_turns"] for d in by_day.values()),
            "assistant_turns": sum(d["assistant_turns"] for d in by_day.values()),
            "transcript_bytes": sum(d["transcript_bytes"] for d in by_day.values()),
        },
        "warning": "NOT LLM tokens — activity proxy only",
    }


def gather_bitbucket_daily(start: date, end: date, bb_env: Path) -> dict:
    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError:
        return {"available": False, "reason": "requests not installed"}

    cfg = load_env(bb_env)
    email = cfg.get("BITBUCKET_USERNAME", "")
    token = cfg.get("BITBUCKET_TOKEN", "")
    repo = cfg.get("BITBUCKET_REPO_SLUG", "")
    workspace = cfg.get("BITBUCKET_WORKSPACE", "")
    if not email or not token or not repo or not workspace:
        return {"available": False, "reason": "incomplete bitbucket.env (need USERNAME, TOKEN, WORKSPACE, REPO_SLUG)"}

    base = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}"
    auth = HTTPBasicAuth(email, token)
    daily: dict[str, dict] = defaultdict(lambda: {
        "pr_pipelines": 0,
        "main_pipelines": 0,
        "ci_cursor_review_runs": 0,
    })

    url = f"{base}/pipelines?sort=-created_on&pagelen=100"
    fetched = 0
    while url and fetched < 400:
        r = requests.get(url, auth=auth, timeout=60)
        if r.status_code != 200:
            return {"available": False, "reason": f"bitbucket HTTP {r.status_code}"}
        data = r.json()
        stop = False
        for p in data.get("values", []):
            created = p.get("created_on", "")
            day = created[:10] if created else None
            if not day:
                continue
            d = date.fromisoformat(day)
            if d < start:
                stop = True
                break
            if d > end:
                continue
            ref = (p.get("target") or {}).get("ref_name", "")
            bucket = daily[day]
            if ref == "main":
                bucket["main_pipelines"] += 1
            else:
                bucket["pr_pipelines"] += 1
                bucket["ci_cursor_review_runs"] += 1
            fetched += 1
        if stop:
            break
        url = data.get("next")

    return {
        "available": True,
        "tier": "B",
        "metric": "ci_cursor_agent_invocations",
        "note": "Each PR pipeline runs cursor-agent once (parallel with tests)",
        "by_day": {k: dict(v) for k, v in sorted(daily.items())},
        "totals": {
            "pr_pipelines": sum(d["pr_pipelines"] for d in daily.values()),
            "main_pipelines": sum(d["main_pipelines"] for d in daily.values()),
            "ci_cursor_review_runs": sum(d["ci_cursor_review_runs"] for d in daily.values()),
        },
    }


def _ms_range(start: date, end: date) -> tuple[int, int]:
    start_ms = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime.combine(end, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc).timestamp() * 1000)
    return start_ms, end_ms


def _accumulate_usage_event(daily: dict, ev: dict, start: date, end: date) -> bool:
    """Return True if event is before window (stop pagination)."""
    ts = ev.get("timestamp") or ev.get("createdAt") or ""
    if isinstance(ts, (int, float)):
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    elif isinstance(ts, str) and len(ts) >= 13 and ts.isdigit():
        day = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    else:
        return False
    d = date.fromisoformat(day)
    if d < start:
        return True
    if d > end:
        return False
    tu = ev.get("tokenUsage") or {}
    bucket = daily[day]
    bucket["input_tokens"] += int(tu.get("inputTokens") or 0)
    bucket["output_tokens"] += int(tu.get("outputTokens") or 0)
    bucket["cache_write_tokens"] += int(tu.get("cacheWriteTokens") or 0)
    bucket["cache_read_tokens"] = bucket.get("cache_read_tokens", 0) + int(tu.get("cacheReadTokens") or 0)
    bucket["events"] += 1
    charged = ev.get("chargedCents")
    if charged is None and tu:
        charged = tu.get("totalCents", 0)
    bucket["charged_cents"] += int(charged or 0)
    if ev.get("isHeadless"):
        bucket["headless_events"] += 1
    return False


def gather_cursor_admin_api(start: date, end: date, cursor_env: Path) -> dict:
    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except ImportError:
        return {"available": False, "reason": "requests not installed"}

    cfg = load_env(cursor_env)
    api_key = os.environ.get("CURSOR_API_KEY", "") or cfg.get("CURSOR_API_KEY", "")
    if not api_key:
        return {"available": False, "reason": "no CURSOR_API_KEY"}

    start_ms, end_ms = _ms_range(start, end)
    auth = HTTPBasicAuth(api_key, "")
    daily: dict[str, dict] = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "events": 0,
        "charged_cents": 0,
        "headless_events": 0,
    })

    page = 1
    page_size = 100
    total_events = 0
    while page <= 50:
        body = {
            "startDate": start_ms,
            "endDate": end_ms,
            "page": page,
            "pageSize": page_size,
        }
        r = requests.post(
            "https://api.cursor.com/teams/filtered-usage-events",
            auth=auth,
            json=body,
            timeout=60,
        )
        if r.status_code == 401:
            return {
                "available": False,
                "reason": "CURSOR_API_KEY rejected (needs Admin/usage scope, or Enterprise team)",
            }
        if r.status_code != 200:
            return {"available": False, "reason": f"cursor admin API HTTP {r.status_code}"}
        data = r.json()
        events = data.get("usageEvents") or data.get("events") or []
        if not events:
            break
        stop = False
        for ev in events:
            if _accumulate_usage_event(daily, ev, start, end):
                stop = True
            else:
                total_events += 1
        if stop:
            break
        total = data.get("totalUsageEventsCount") or data.get("totalCount") or 0
        if page * page_size >= total:
            break
        page += 1

    by_day = {k: dict(v) for k, v in sorted(daily.items())}
    return {
        "available": total_events > 0,
        "tier": "A",
        "metric": "measured_tokens_and_cost",
        "source": "api.cursor.com/teams/filtered-usage-events",
        "auth": "CURSOR_API_KEY (Admin API)",
        "by_day": by_day,
        "totals": {
            "input_tokens": sum(d["input_tokens"] for d in by_day.values()),
            "output_tokens": sum(d["output_tokens"] for d in by_day.values()),
            "cache_write_tokens": sum(d["cache_write_tokens"] for d in by_day.values()),
            "cache_read_tokens": sum(d.get("cache_read_tokens", 0) for d in by_day.values()),
            "events": sum(d["events"] for d in by_day.values()),
            "charged_cents": sum(d["charged_cents"] for d in by_day.values()),
            "headless_events": sum(d["headless_events"] for d in by_day.values()),
        },
    }


def gather_cursor_dashboard_session(start: date, end: date, cursor_env: Path) -> dict:
    try:
        import requests
    except ImportError:
        return {"available": False, "reason": "requests not installed"}

    cfg = load_env(cursor_env)
    session = os.environ.get("CURSOR_SESSION_TOKEN", "") or cfg.get("CURSOR_SESSION_TOKEN", "")
    team_id = cfg.get("CURSOR_TEAM_ID", "")
    user_id = cfg.get("CURSOR_USER_ID", "")
    if not session:
        return {
            "available": False,
            "reason": "no CURSOR_SESSION_TOKEN — Tier A unavailable",
            "setup": "projects/<slug>/.secrets/cursor.env — see cursor.env.example",
        }

    headers = {
        "Cookie": f"WorkosCursorSessionToken={session}",
        "Origin": "https://cursor.com",
        "Content-Type": "application/json",
    }
    daily: dict[str, dict] = defaultdict(lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_write_tokens": 0,
        "events": 0,
        "charged_cents": 0,
        "headless_events": 0,
    })

    page = 1
    page_size = 100
    total_events = 0
    while page <= 50:
        body: dict = {"page": page, "pageSize": page_size}
        if team_id:
            body["teamId"] = int(team_id)
        if user_id:
            body["userId"] = int(user_id)
        r = requests.post(
            "https://cursor.com/api/dashboard/get-filtered-usage-events",
            headers=headers,
            json=body,
            timeout=60,
        )
        if r.status_code != 200:
            return {"available": False, "reason": f"cursor dashboard HTTP {r.status_code}"}
        data = r.json()
        events = data.get("usageEvents") or data.get("events") or []
        if not events:
            break
        stop = False
        for ev in events:
            ts = str(ev.get("timestamp", ""))
            if len(ts) >= 13:
                day = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            else:
                continue
            d = date.fromisoformat(day)
            if d < start:
                stop = True
                break
            if d > end:
                continue
            tu = ev.get("tokenUsage") or {}
            bucket = daily[day]
            bucket["input_tokens"] += int(tu.get("inputTokens") or 0)
            bucket["output_tokens"] += int(tu.get("outputTokens") or 0)
            bucket["cache_write_tokens"] += int(tu.get("cacheWriteTokens") or 0)
            bucket["events"] += 1
            charged = ev.get("chargedCents")
            if charged is None and tu:
                charged = tu.get("totalCents", 0)
            bucket["charged_cents"] += int(charged or 0)
            if ev.get("isHeadless"):
                bucket["headless_events"] += 1
            total_events += 1
        if stop:
            break
        total = data.get("totalUsageEventsCount") or 0
        if page * page_size >= total:
            break
        page += 1

    by_day = {k: dict(v) for k, v in sorted(daily.items())}
    return {
        "available": total_events > 0,
        "tier": "A",
        "metric": "measured_tokens_and_cost",
        "source": "cursor.com/api/dashboard/get-filtered-usage-events",
        "by_day": by_day,
        "totals": {
            "input_tokens": sum(d["input_tokens"] for d in by_day.values()),
            "output_tokens": sum(d["output_tokens"] for d in by_day.values()),
            "cache_write_tokens": sum(d["cache_write_tokens"] for d in by_day.values()),
            "events": sum(d["events"] for d in by_day.values()),
            "charged_cents": sum(d["charged_cents"] for d in by_day.values()),
            "headless_events": sum(d["headless_events"] for d in by_day.values()),
        },
    }


def gather_cursor_tier_a(start: date, end: date, cursor_env: Path) -> dict:
    """Admin API key (bitbucket-ci) first, then dashboard session cookie."""
    admin = gather_cursor_admin_api(start, end, cursor_env)
    if admin.get("available"):
        return admin
    session = gather_cursor_dashboard_session(start, end, cursor_env)
    if session.get("available"):
        return session
    return {
        "available": False,
        "reason": " · ".join(
            r for r in (admin.get("reason"), session.get("reason")) if r
        ),
        "setup": "projects/<slug>/.secrets/cursor.env — see cursor.env.example",
        "bitbucket_hint": (
            "Optional: projects/<slug>/.secrets/bitbucket.env for PR pipeline counts"
        ),
    }


def gather_cursor_dashboard(start: date, end: date, cursor_env: Path) -> dict:
    return gather_cursor_tier_a(start, end, cursor_env)


def load_calibration(cursor_env: Path) -> dict[str, float | int]:
    cfg = load_env(cursor_env)
    out = dict(DEFAULT_CALIBRATION)
    if cfg.get("USAGE_TOKENS_PER_MS"):
        out["tokens_per_ms"] = float(cfg["USAGE_TOKENS_PER_MS"])
    if cfg.get("USAGE_TOKENS_PER_CI"):
        out["tokens_per_ci_review"] = int(cfg["USAGE_TOKENS_PER_CI"])
    if cfg.get("USAGE_TOKENS_PER_QA_TICK"):
        out["tokens_per_qa_tick"] = int(cfg["USAGE_TOKENS_PER_QA_TICK"])
    if cfg.get("USAGE_USD_PER_MTOK"):
        out["usd_per_mtok"] = float(cfg["USAGE_USD_PER_MTOK"])
    if cfg.get("USAGE_CAP_REQUEST_MS"):
        out["cap_request_ms"] = int(cfg["USAGE_CAP_REQUEST_MS"])
    return out


def gather_request_traces(start: date, end: date, cap_request_ms: int = 0) -> dict:
    """IDE agent.request spans from cursor.requestTraces.log (local, durable)."""
    daily: dict[str, dict] = defaultdict(lambda: {
        "agent_requests": 0,
        "agent_active_ms": 0,
    })
    log_files = 0
    if not CURSOR_LOGS.exists():
        return {
            "available": False,
            "reason": f"no Cursor logs at {CURSOR_LOGS}",
        }

    for log in CURSOR_LOGS.glob("**/cursor.requestTraces.log"):
        log_files += 1
        for line in log.read_text(errors="replace").splitlines():
            m = AGENT_REQUEST_RE.match(line)
            if not m:
                continue
            day = m.group(1)
            if not in_window(day, start, end):
                continue
            bucket = daily[day]
            bucket["agent_requests"] += 1
            ms = int(m.group(2))
            if cap_request_ms > 0:
                ms = min(ms, cap_request_ms)
            bucket["agent_active_ms"] += ms

    by_day = {k: dict(v) for k, v in sorted(daily.items())}
    totals = {
        "agent_requests": sum(d["agent_requests"] for d in by_day.values()),
        "agent_active_ms": sum(d["agent_active_ms"] for d in by_day.values()),
    }
    return {
        "available": log_files > 0 and totals["agent_requests"] > 0,
        "tier": "D_source",
        "metric": "ide_agent_request_spans",
        "source": str(CURSOR_LOGS / "**/cursor.requestTraces.log"),
        "log_files_scanned": log_files,
        "by_day": by_day,
        "totals": totals,
        "note": "Top-level agent.request durationMs — local telemetry, not billing",
    }


def build_tier_d(
    start: date,
    end: date,
    traces: dict,
    ledger: dict,
    ci: dict,
    calibration: dict[str, float | int],
) -> dict:
    """Estimated tokens from durable local sources when Tier A is unavailable."""
    if not traces.get("available"):
        return {
            "available": False,
            "reason": traces.get("reason", "no request traces"),
        }

    tpm = float(calibration["tokens_per_ms"])
    tpci = int(calibration["tokens_per_ci_review"])
    tpqt = int(calibration["tokens_per_qa_tick"])
    usd_m = float(calibration["usd_per_mtok"])

    ledger_by = (ledger.get("by_day") or {}) if ledger.get("available") else {}
    ci_by = (ci.get("by_day") or {}) if ci.get("available") else {}
    traces_by = traces.get("by_day") or {}

    daily: dict[str, dict] = {}
    cur = start
    while cur <= end:
        day = cur.isoformat()
        t = traces_by.get(day, {})
        l = ledger_by.get(day, {})
        c = ci_by.get(day, {})

        agent_requests = int(t.get("agent_requests", 0))
        agent_active_ms = int(t.get("agent_active_ms", 0))
        qa_ticks = int(l.get("qa_ticks", 0))
        ci_runs = int(c.get("ci_cursor_review_runs", 0))

        est_ide = int(agent_active_ms * tpm)
        est_qa = qa_ticks * tpqt
        est_ci = ci_runs * tpci
        est_total = est_ide + est_qa + est_ci
        est_usd_cents = int(round(est_total / 1_000_000 * usd_m * 100))

        if any((agent_requests, qa_ticks, ci_runs)):
            daily[day] = {
                "agent_requests": agent_requests,
                "agent_active_ms": agent_active_ms,
                "qa_ticks": qa_ticks,
                "ci_review_runs": ci_runs,
                "est_tokens_ide": est_ide,
                "est_tokens_qa": est_qa,
                "est_tokens_ci": est_ci,
                "est_tokens_total": est_total,
                "est_usd_cents": est_usd_cents,
                "spend_index": (
                    agent_requests * 100 + qa_ticks * 50 + ci_runs * 30
                ),
            }
        cur += timedelta(days=1)

    totals = {
        "agent_requests": sum(d["agent_requests"] for d in daily.values()),
        "agent_active_ms": sum(d["agent_active_ms"] for d in daily.values()),
        "qa_ticks": sum(d["qa_ticks"] for d in daily.values()),
        "ci_review_runs": sum(d["ci_review_runs"] for d in daily.values()),
        "est_tokens_ide": sum(d["est_tokens_ide"] for d in daily.values()),
        "est_tokens_qa": sum(d["est_tokens_qa"] for d in daily.values()),
        "est_tokens_ci": sum(d["est_tokens_ci"] for d in daily.values()),
        "est_tokens_total": sum(d["est_tokens_total"] for d in daily.values()),
        "est_usd_cents": sum(d["est_usd_cents"] for d in daily.values()),
        "spend_index": sum(d["spend_index"] for d in daily.values()),
    }

    return {
        "available": totals["est_tokens_total"] > 0,
        "tier": "D",
        "metric": "estimated_tokens_local",
        "label": "ESTIMATED — not billed; calibrate in cursor.env",
        "sources": [
            "cursor.requestTraces.log (IDE agent.request durationMs)",
            "factory/runs/*.jsonl (qa_ticks)",
            "bitbucket PR pipelines (ci_review_runs)",
        ],
        "calibration": calibration,
        "formula": {
            "est_tokens_ide": "agent_active_ms × USAGE_TOKENS_PER_MS",
            "est_tokens_qa": "qa_ticks × USAGE_TOKENS_PER_QA_TICK",
            "est_tokens_ci": "ci_review_runs × USAGE_TOKENS_PER_CI",
            "est_usd": "est_tokens_total / 1e6 × USAGE_USD_PER_MTOK",
        },
        "by_day": daily,
        "totals": totals,
        "request_traces": {
            "log_files_scanned": traces.get("log_files_scanned", 0),
            "totals": traces.get("totals", {}),
        },
    }


def merge_daily(start: date, end: date, *sources: dict) -> list[dict]:
    days = []
    cur = start
    while cur <= end:
        days.append(cur.isoformat())
        cur += timedelta(days=1)

    rows = []
    for day in days:
        row: dict = {"date": day}
        for src in sources:
            if not src.get("available"):
                continue
            tier = src.get("tier", "?")
            data = (src.get("by_day") or {}).get(day, {})
            if tier == "A":
                row["tokens_input"] = data.get("input_tokens", 0)
                row["tokens_output"] = data.get("output_tokens", 0)
                row["tokens_total"] = (
                    data.get("input_tokens", 0)
                    + data.get("output_tokens", 0)
                    + data.get("cache_write_tokens", 0)
                )
                row["usd_cents"] = data.get("charged_cents", 0)
                row["cursor_events"] = data.get("events", 0)
            elif src.get("metric") == "countable_invocations":
                row["qa_ticks"] = data.get("qa_ticks", 0)
                row["ledger_events"] = data.get("ledger_events", 0)
            elif src.get("metric") == "ci_cursor_agent_invocations":
                row["ci_review_runs"] = data.get("ci_cursor_review_runs", 0)
                row["pr_pipelines"] = data.get("pr_pipelines", 0)
            elif src.get("metric") == "context_proxy_not_tokens":
                row["ide_user_turns"] = data.get("user_turns", 0)
                row["ide_assistant_turns"] = data.get("assistant_turns", 0)
            elif src.get("metric") == "estimated_tokens_local":
                row["agent_requests"] = data.get("agent_requests", 0)
                row["agent_active_ms"] = data.get("agent_active_ms", 0)
                row["est_tokens_ide"] = data.get("est_tokens_ide", 0)
                row["est_tokens_qa"] = data.get("est_tokens_qa", 0)
                row["est_tokens_ci"] = data.get("est_tokens_ci", 0)
                row["est_tokens_total"] = data.get("est_tokens_total", 0)
                row["est_usd_cents"] = data.get("est_usd_cents", 0)
                row["spend_index"] = data.get("spend_index", 0)
        rows.append(row)
    return rows


def weekly_summary(daily: list[dict], tiers: dict) -> dict:
    keys = (
        "qa_ticks", "ci_review_runs", "ide_user_turns", "ide_assistant_turns",
        "tokens_total", "usd_cents", "ledger_events", "cursor_events",
        "agent_requests", "agent_active_ms",
        "est_tokens_ide", "est_tokens_qa", "est_tokens_ci",
        "est_tokens_total", "est_usd_cents", "spend_index",
    )
    row = {k: sum(d.get(k, 0) or 0 for d in daily) for k in keys}
    a = tiers.get("A_exact", {})
    if a.get("available") and a.get("totals"):
        t = a["totals"]
        row["tokens_input"] = t.get("input_tokens", 0)
        row["tokens_output"] = t.get("output_tokens", 0)
        row["tokens_cache_write"] = t.get("cache_write_tokens", 0)
        row["usd_dollars"] = round(t.get("charged_cents", 0) / 100, 2)
    d = tiers.get("D_estimated", {})
    if d.get("available") and d.get("totals"):
        t = d["totals"]
        row["est_usd_dollars"] = round(t.get("est_usd_cents", 0) / 100, 2)
        row["agent_active_hours"] = round(t.get("agent_active_ms", 0) / 3_600_000, 2)
    return row


def print_summary(payload: dict) -> None:
    print(f"Usage report · methodology v{payload['methodology_version']}")
    print(f"Window: {payload['window']['start']} → {payload['window']['end']}")
    tiers = payload["tiers"]
    for key in (
        "A_exact", "D_estimated", "B_countable_ledger", "B_countable_ci", "C_proxy",
    ):
        t = tiers.get(key, {})
        status = "✓" if t.get("available") else "—"
        label = t.get("label") or t.get("metric", t.get("reason", "n/a"))
        print(f"  [{status}] {key}: {label}")

    w = payload.get("weekly", {})
    print("\nWeek totals:")
    if tiers.get("A_exact", {}).get("available"):
        print(
            f"  Tier A — tokens: {w.get('tokens_total', 0):,} · "
            f"${w.get('usd_dollars', 0):.2f} · events: {w.get('cursor_events', 0)}"
        )
    elif tiers.get("D_estimated", {}).get("available"):
        cal = tiers["D_estimated"].get("calibration", {})
        print(
            f"  Tier D — ESTIMATED: {w.get('est_tokens_total', 0):,} tokens · "
            f"~${w.get('est_usd_dollars', 0):.2f} · "
            f"{w.get('agent_requests', 0)} IDE requests · "
            f"{w.get('agent_active_hours', 0):.1f}h agent time"
        )
        print(
            f"           calibration: {cal.get('tokens_per_ms')} tok/ms · "
            f"{cal.get('tokens_per_qa_tick'):,}/tick · "
            f"{cal.get('tokens_per_ci_review'):,}/CI · "
            f"${cal.get('usd_per_mtok')}/Mtok"
        )
    else:
        print("  Tier A/D — $/tokens: unavailable (no billing API, no local traces)")
    print(
        f"  Tier B — QA ticks: {w.get('qa_ticks', 0)} · "
        f"CI reviews: {w.get('ci_review_runs', 0)} · "
        f"ledger events: {w.get('ledger_events', 0)}"
    )
    print(
        f"  Tier C — IDE user turns: {w.get('ide_user_turns', 0)} · "
        f"assistant turns: {w.get('ide_assistant_turns', 0)} (proxy, not tokens)"
    )

    print("\nDaily (merged):")
    show_est = not tiers.get("A_exact", {}).get("available")
    if show_est:
        hdr = (
            f"{'date':<12} {'ticks':>5} {'CI':>4} {'req':>4} "
            f"{'est-M':>7} {'~USD':>7}"
        )
    else:
        hdr = (
            f"{'date':<12} {'ticks':>5} {'CI-CR':>5} "
            f"{'IDE-u':>5} {'tokens':>10} {'USD¢':>8}"
        )
    print(hdr)
    for row in payload["daily"]:
        if show_est:
            if not any(
                row.get(k, 0)
                for k in ("qa_ticks", "ci_review_runs", "agent_requests", "est_tokens_total")
            ):
                continue
            est_m = (row.get("est_tokens_total", 0) or 0) / 1_000_000
            usd = (row.get("est_usd_cents", 0) or 0) / 100
            print(
                f"{row['date']:<12} "
                f"{row.get('qa_ticks', 0):>5} "
                f"{row.get('ci_review_runs', 0):>4} "
                f"{row.get('agent_requests', 0):>4} "
                f"{est_m:>7.2f} "
                f"{usd:>7.2f}"
            )
        else:
            if not any(
                row.get(k, 0)
                for k in (
                    "qa_ticks", "ci_review_runs", "ide_user_turns",
                    "tokens_total", "usd_cents",
                )
            ):
                continue
            print(
                f"{row['date']:<12} "
                f"{row.get('qa_ticks', 0):>5} "
                f"{row.get('ci_review_runs', 0):>5} "
                f"{row.get('ide_user_turns', 0):>5} "
                f"{row.get('tokens_total', 0):>10} "
                f"{row.get('usd_cents', 0):>8}"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect agent usage by methodology tiers")
    ap.add_argument("--slug", required=True, help="Project slug under projects/")
    ap.add_argument("--days", type=int, default=14, help="Lookback window (days)")
    ap.add_argument("--offline", action="store_true", help="Skip network (ledger + transcripts only)")
    ap.add_argument("--workspace", default=None, help="Glob under ~/.cursor/projects for transcripts")
    ap.add_argument("--out", default=None, help="Write JSON (default: projects/<slug>/factory/usage.json)")
    args = ap.parse_args()

    end = date.today()
    start = end - timedelta(days=max(args.days - 1, 0))

    slug = args.slug
    secrets = ROOT / "projects" / slug / ".secrets"
    bb_env = secrets / "bitbucket.env"
    cursor_env = secrets / "cursor.env"
    calibration = load_calibration(cursor_env)

    ledger = gather_ledger(slug, start, end)
    transcripts = gather_transcripts(start, end, args.workspace)
    traces = gather_request_traces(
        start, end, int(calibration.get("cap_request_ms", 0))
    )
    ci = {"available": False, "reason": "skipped (--offline)"}
    cursor = {"available": False, "reason": "skipped (--offline)"}
    if not args.offline:
        ci = gather_bitbucket_daily(start, end, bb_env)
        cursor = gather_cursor_dashboard(start, end, cursor_env)

    tier_d = build_tier_d(start, end, traces, ledger, ci, calibration)
    daily = merge_daily(start, end, ledger, transcripts, ci, cursor, tier_d)
    tiers = {
        "A_exact": cursor,
        "D_estimated": tier_d,
        "B_countable_ledger": ledger,
        "B_countable_ci": ci,
        "C_proxy": transcripts,
    }
    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "methodology_version": METHODOLOGY_VERSION,
        "slug": slug,
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": args.days},
        "tiers": tiers,
        "weekly": weekly_summary(daily, tiers),
        "daily": daily,
        "methodology": {
            "A": "Measured LLM tokens + USD — Admin API or dashboard (optional; needs billing scope)",
            "D": (
                "ESTIMATED tokens from local logs: cursor.requestTraces.log agent.request "
                "durationMs + factory qa_ticks + CI reviews — primary when A unavailable"
            ),
            "B_ledger": "Factory JSONL events — qa_ticks = tick_end lines per day (NOT tokens)",
            "B_ci": "Bitbucket PR pipelines per day ≈ cursor-agent headless review runs",
            "C": "IDE transcript user/assistant turns + bytes — activity proxy, NEVER report as tokens",
            "rule": (
                "Only Tier A 'tokens_*' and 'usd_cents' are billed. "
                "Tier D is ESTIMATED — always label as such; tune coefficients in cursor.env"
            ),
        },
    }

    out = Path(args.out) if args.out else ROOT / "projects" / slug / "factory" / "usage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print_summary(payload)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
