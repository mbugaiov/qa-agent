#!/usr/bin/env python3
"""Create a GitHub Issue bug for a github_issues QA factory (Pantheon L5 defect_loop).

Mirrors create_jira_issue.py for non-Jira trackers:
  - labels: qa-agent + caller labels; severity-sN; confirmed-defect → impl-dev
  - dedupe open issues by normalized title (default on)
  - optional --related-key comment on the feature ticket
  - --attach uploads secret gist via project GITHUB_TOKEN (never ambient-account mix)

Usage:
    python3 scripts/github_create_issue.py --project projects/<slug> \\
        --summary "PF-XX: one line" \\
        --description-file runs/<run>/bug-report.md \\
        --severity S2 --labels <slug>,confirmed-defect \\
        --attach runs/<run>/screenshots/fail.png \\
        --related-key <slug>#12

Exit 0 on success / inactive no-op / dedupe hit.
Last stdout line is the issue key (<slug>#N) for capture.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import (  # noqa: E402
    github_inactive,
    github_repo,
    load_env_file,
    pickup_label,
)

SEVERITY_LABEL = {"S1": "severity-s1", "S2": "severity-s2", "S3": "severity-s3", "S4": "severity-s4"}


def normalize_title(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def build_labels(
    *,
    slug: str,
    raw_labels: str,
    severity: str | None,
    no_impl_dev: bool,
    pickup: str,
) -> list[str]:
    labels = ["qa-agent"]
    if slug and slug not in labels:
        labels.append(slug)
    for part in raw_labels.split(","):
        p = part.strip()
        if p and p not in labels:
            labels.append(p)
    if severity:
        labels.append(SEVERITY_LABEL[severity])
    if not no_impl_dev and any(l.lower() == "confirmed-defect" for l in labels):
        if pickup not in labels:
            labels.append(pickup)
    return labels


def parse_related_number(key: str) -> int | None:
    m = re.search(r"(\d+)$", (key or "").strip())
    return int(m.group(1)) if m else None


def project_gh_env(project_dir: str) -> tuple[dict[str, str], bool]:
    """Build env for gh subprocesses.

    When projects/<slug>/.secrets/github.env has GITHUB_TOKEN|GH_TOKEN, strip ambient
    GH_* tokens and inject the project token (per-tenant isolation for evidence upload).
    """
    secrets = load_env_file(os.path.join(project_dir, ".secrets", "github.env"))
    token = (secrets.get("GITHUB_TOKEN") or secrets.get("GH_TOKEN") or "").strip()
    if token:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")
        }
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
        return env, True
    return dict(os.environ), False


def find_dedupe_hit(
    repo_ref: str,
    summary: str,
    *,
    env: dict[str, str],
    label_filter: str | None = "confirmed-defect",
) -> dict[str, Any] | None:
    """Return first open issue with the same normalized title (optional label filter)."""
    want = normalize_title(summary)
    if not want:
        return None
    cmd = [
        "gh",
        "issue",
        "list",
        "-R",
        repo_ref,
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,title,labels,url",
    ]
    if label_filter:
        cmd.extend(["--label", label_filter])
    try:
        raw = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, env=env)
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        items = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        return None
    for it in items:
        if normalize_title(str(it.get("title") or "")) == want:
            return it
    if label_filter:
        return find_dedupe_hit(repo_ref, summary, env=env, label_filter=None)
    return None


def ensure_labels_exist(repo_ref: str, labels: list[str], *, env: dict[str, str]) -> None:
    for name in labels:
        subprocess.run(
            [
                "gh",
                "label",
                "create",
                name,
                "-R",
                repo_ref,
                "--force",
                "--color",
                "0E8A16",
                "--description",
                "qa-agent factory",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )


def secret_gist_upload(path: str, desc: str, *, env: dict[str, str]) -> str | None:
    """Upload evidence as a *secret* gist using the project GH_TOKEN env only."""
    if not os.path.isfile(path):
        return None
    try:
        out = subprocess.check_output(
            ["gh", "gist", "create", "--secret", path, "--desc", desc[:80]],
            text=True,
            stderr=subprocess.DEVNULL,
            env=env,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a GitHub Issue bug for a QA project")
    ap.add_argument("--project", required=True, help="path to projects/<slug>")
    ap.add_argument("--summary", required=True, help="issue title (one line)")
    desc = ap.add_mutually_exclusive_group(required=True)
    desc.add_argument("--description", help="issue body text")
    desc.add_argument("--description-file", help="file whose contents become the body")
    ap.add_argument("--severity", choices=list(SEVERITY_LABEL), help="S1..S4 → severity-sN label")
    ap.add_argument(
        "--labels",
        default="",
        help="comma-separated labels (always adds qa-agent + slug; confirmed-defect → impl-dev)",
    )
    ap.add_argument(
        "--no-impl-dev",
        action="store_true",
        help="do not add pickup/impl-dev when confirmed-defect is present",
    )
    ap.add_argument(
        "--related-key",
        default="",
        help="feature ticket key (e.g. <slug>#12) — comment with link after create",
    )
    ap.add_argument(
        "--no-dedupe",
        action="store_true",
        help="skip open-issue title dedupe (default: dedupe on)",
    )
    ap.add_argument("--attach", action="append", default=[], help="evidence file (repeatable)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    slug = os.path.basename(a.project.rstrip("/"))
    pickup = pickup_label(a.project)
    labels = build_labels(
        slug=slug,
        raw_labels=a.labels,
        severity=a.severity,
        no_impl_dev=a.no_impl_dev,
        pickup=pickup,
    )

    description = a.description
    if a.description_file:
        with open(a.description_file, encoding="utf-8") as fh:
            description = fh.read()

    if github_inactive(a.project) and not a.dry_run:
        print(f"GitHub not configured for {a.project} — skipping (no GitHub action taken).")
        return 0

    if a.dry_run:
        print("DRY RUN → gh issue create")
        print(json.dumps(
            {
                "title": a.summary,
                "labels": labels,
                "body_preview": (description or "")[:400],
                "attach": a.attach,
                "related_key": a.related_key or None,
                "dedupe": not a.no_dedupe,
                "attach_requires_project_token": True,
            },
            indent=2,
            ensure_ascii=False,
        ))
        # Mirror jira dry-run: show impl-dev presence for tests
        print(f"labels={labels}")
        return 0

    owner, repo = github_repo(a.project)
    repo_ref = f"{owner}/{repo}"
    gh_env, has_project_token = project_gh_env(a.project)

    if not a.no_dedupe:
        hit = find_dedupe_hit(repo_ref, a.summary, env=gh_env)
        if hit:
            num = hit.get("number")
            key = f"{slug}#{num}"
            url = hit.get("url") or f"https://github.com/{repo_ref}/issues/{num}"
            print(f"GITHUB_DEDUPE_HIT {key} → {url}")
            print(key)
            return 0

    ensure_labels_exist(repo_ref, labels, env=gh_env)

    cmd = [
        "gh",
        "issue",
        "create",
        "-R",
        repo_ref,
        "--title",
        a.summary,
        "--body",
        description or "",
    ]
    for lab in labels:
        cmd.extend(["--label", lab])

    try:
        created = subprocess.check_output(
            cmd, text=True, stderr=subprocess.PIPE, env=gh_env
        ).strip()
    except subprocess.CalledProcessError as e:
        print(
            f"GitHub create failed:\n{e.stderr or e.stdout or e}",
            file=sys.stderr,
        )
        return 1

    # created is usually the HTML URL
    m = re.search(r"/issues/(\d+)\s*$", created)
    if not m:
        m = re.search(r"/issues/(\d+)", created)
    if not m:
        print(f"Created but could not parse issue number from: {created}", file=sys.stderr)
        return 2
    num = int(m.group(1))
    key = f"{slug}#{num}"
    url = created if created.startswith("http") else f"https://github.com/{repo_ref}/issues/{num}"
    print(f"Created {key} → {url}")

    # Evidence: secret gist via *project* GH_TOKEN only (never ambient-account gist mix).
    evidence_lines: list[str] = ["## Evidence attachments", ""]
    attached_ok = False
    if a.attach and not has_project_token:
        print(
            "  ! --attach skipped upload: set GITHUB_TOKEN in "
            f"{a.project}/.secrets/github.env (project token required; ambient gh ignored)",
            file=sys.stderr,
        )
        for path in a.attach:
            evidence_lines.append(f"- local path (not uploaded): `{path}`")
        # Comment paths, then fail so unattended DoD cannot treat create as evidence-complete
        subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(num),
                "-R",
                repo_ref,
                "--body",
                "\n".join(evidence_lines),
            ],
            check=False,
            env=gh_env,
        )
        print(key)
        print(
            "GITHUB_ATTACH_TOKEN_REQUIRED — issue created but evidence not uploaded",
            file=sys.stderr,
        )
        return 3
    for path in a.attach if has_project_token else []:
        if not os.path.isfile(path):
            print(f"  ! attachment not found: {path}", file=sys.stderr)
            evidence_lines.append(f"- missing: `{path}`")
            continue
        gist_url = secret_gist_upload(
            path, f"qa-agent evidence for {key}", env=gh_env
        )
        base = os.path.basename(path)
        if gist_url:
            attached_ok = True
            lower = base.lower()
            if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                evidence_lines.append(f"- ![{base}]({gist_url})")
            else:
                evidence_lines.append(f"- [{base}]({gist_url})")
            print(f"  attached {base} → secret gist {gist_url}")
        else:
            evidence_lines.append(f"- upload failed: `{path}`")
            print(f"  ! secret gist upload failed for {path}", file=sys.stderr)

    if a.attach:
        subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(num),
                "-R",
                repo_ref,
                "--body",
                "\n".join(evidence_lines),
            ],
            check=False,
            env=gh_env,
        )
        if attached_ok:
            if any(
                os.path.basename(p).lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp")
                )
                for p in a.attach
                if os.path.isfile(p)
            ):
                print("  bug_screenshot_attached=true (secret gist via project token)")
            if any(
                os.path.basename(p).lower().endswith(
                    (".mp4", ".webm", ".mov", ".m4v")
                )
                for p in a.attach
                if os.path.isfile(p)
            ):
                print("  bug_recording_attached=true (secret gist via project token)")

    related_num = parse_related_number(a.related_key) if a.related_key else None
    if related_num:
        body = (
            f"## QA filed separate bug\n\n"
            f"- Bug: {url} (`{key}`)\n"
            f"- Labels: {', '.join(labels)}\n"
            f"- Severity: {a.severity or 'n/a'}\n\n"
            f"Feature ticket stays in scope; Hephaestus should pick `{pickup}` on the bug."
        )
        subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(related_num),
                "-R",
                repo_ref,
                "--body",
                body,
            ],
            check=False,
            env=gh_env,
        )
        print(f"  related comment → #{related_num}")

    # Capture line (parity with create_jira_issue.py)
    print(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
