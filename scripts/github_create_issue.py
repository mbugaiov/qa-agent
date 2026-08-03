#!/usr/bin/env python3
"""Create a GitHub Issue bug for a github_issues QA factory (Pantheon L5 defect_loop).

Mirrors create_jira_issue.py for non-Jira trackers:
  - labels: qa-agent + caller labels; severity-sN; confirmed-defect → impl-dev
  - dedupe open issues by normalized title (default on)
  - optional --related-key comment on the feature ticket
  - --attach uploads real media to branch qa-evidence (Contents API) via project
    GITHUB_TOKEN; text-only may still use secret gist. Never ambient-account mix.

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


EVIDENCE_BRANCH = "qa-evidence"
_MEDIA_SUFFIXES = (
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
)


def _is_media_path(path: str) -> bool:
    lower = path.lower()
    if lower.endswith(_MEDIA_SUFFIXES):
        return True
    try:
        with open(path, "rb") as fh:
            fh.read(4096).decode("utf-8")
    except UnicodeDecodeError:
        return True
    except OSError:
        return False
    return False


def _safe_evidence_dir(issue_key: str) -> str:
    """pantheon#71 → pantheon-71"""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (issue_key or "evidence").strip()).strip("-") or "evidence"


def ensure_evidence_branch(
    owner: str, repo: str, *, env: dict[str, str], branch: str = EVIDENCE_BRANCH
) -> bool:
    """Create orphan-ish qa-evidence branch from default HEAD if missing."""
    repo_ref = f"{owner}/{repo}"
    ref = f"repos/{repo_ref}/git/ref/heads/{branch}"
    probe = subprocess.run(
        ["gh", "api", ref],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return True
    meta = subprocess.run(
        ["gh", "api", f"repos/{repo_ref}", "--jq", ".default_branch"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if meta.returncode != 0:
        print(f"evidence branch: cannot read default_branch: {meta.stderr}", file=sys.stderr)
        return False
    default_branch = (meta.stdout or "").strip() or "main"
    sha_r = subprocess.run(
        ["gh", "api", f"repos/{repo_ref}/git/ref/heads/{default_branch}", "--jq", ".object.sha"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if sha_r.returncode != 0:
        print(f"evidence branch: cannot read {default_branch} sha: {sha_r.stderr}", file=sys.stderr)
        return False
    sha = (sha_r.stdout or "").strip()
    create = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo_ref}/git/refs",
            "-f",
            f"ref=refs/heads/{branch}",
            "-f",
            f"sha={sha}",
        ],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if create.returncode != 0:
        # race: branch appeared
        probe2 = subprocess.run(
            ["gh", "api", ref],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        if probe2.returncode == 0:
            return True
        print(f"evidence branch create failed: {create.stderr or create.stdout}", file=sys.stderr)
        return False
    return True


def github_repo_evidence_upload(
    path: str,
    *,
    owner: str,
    repo: str,
    issue_key: str,
    message: str,
    env: dict[str, str],
    branch: str = EVIDENCE_BRANCH,
) -> str | None:
    """Upload a real binary/text file to ``qa-evidence`` and return the blob URL.

    Gists cannot host viewable PNG/MP4 (``gh gist create`` rejects binary; the old
    ``.b64.txt`` workaround opens as plaintext). Repo Contents API stores the real
    file; GitHub's blob page renders images and plays short videos when logged in.
    """
    if not os.path.isfile(path):
        return None
    import base64

    if not ensure_evidence_branch(owner, repo, env=env, branch=branch):
        return None

    repo_ref = f"{owner}/{repo}"
    base = os.path.basename(path)
    rel = f"{_safe_evidence_dir(issue_key)}/{base}"
    api_path = f"repos/{repo_ref}/contents/{rel}"

    try:
        with open(path, "rb") as fh:
            content_b64 = base64.b64encode(fh.read()).decode("ascii")
    except OSError as e:
        print(f"evidence read error: {e}", file=sys.stderr)
        return None

    # Update existing file if present (Contents API requires sha).
    existing_sha = ""
    get_r = subprocess.run(
        ["gh", "api", f"{api_path}?ref={branch}", "--jq", ".sha"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if get_r.returncode == 0:
        existing_sha = (get_r.stdout or "").strip()

    # Prefer JSON body — large base64 blows past ARG_MAX with repeated -f flags.
    import tempfile

    body: dict[str, str] = {
        "message": (message[:200] or f"qa-agent evidence {base}"),
        "content": content_b64,
        "branch": branch,
    }
    if existing_sha:
        body["sha"] = existing_sha

    tmp_json: str | None = None
    try:
        fd, tmp_json = tempfile.mkstemp(prefix="qa-evidence-", suffix=".json")
        os.close(fd)
        with open(tmp_json, "w", encoding="utf-8") as out_fh:
            json.dump(body, out_fh)
        put = subprocess.run(
            ["gh", "api", "--method", "PUT", api_path, "--input", tmp_json],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
    finally:
        if tmp_json and os.path.isfile(tmp_json):
            try:
                os.remove(tmp_json)
            except OSError:
                pass

    if put.returncode != 0:
        print(f"evidence upload error: {put.stderr or put.stdout}", file=sys.stderr)
        return None
    try:
        payload = json.loads(put.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    html_url = (payload.get("content") or {}).get("html_url") or ""
    if not html_url:
        html_url = f"https://github.com/{repo_ref}/blob/{branch}/{rel}"
    return html_url


def secret_gist_upload(path: str, desc: str, *, env: dict[str, str]) -> str | None:
    """Upload *text* evidence as a secret gist (project GH_TOKEN only).

    Current `gh gist create` defaults to secret; `--secret` was removed (use `--public`
    only when deliberately sharing). Never pass `--public` for QA evidence.

    Do **not** use for PNG/MP4 — call ``github_repo_evidence_upload`` instead.
    """
    if not os.path.isfile(path):
        return None
    if _is_media_path(path):
        print(
            "secret_gist_upload refused media file — use github_repo_evidence_upload",
            file=sys.stderr,
        )
        return None
    try:
        out = subprocess.check_output(
            ["gh", "gist", "create", path, "--desc", desc[:80]],
            text=True,
            stderr=subprocess.PIPE,
            env=env,
        ).strip()
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        if err:
            print(f"secret gist upload error: {err}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"secret gist upload error: {e}", file=sys.stderr)
        return None
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def evidence_markdown_line(basename: str, url: str) -> str:
    """Markdown that opens the real file on GitHub (blob page), not a .b64.txt gist."""
    lower = basename.lower()
    if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        # Blob URLs render the image in-browser; raw may 404 camo on private repos.
        return f"- [{basename}]({url}) — open to view image"
    if lower.endswith((".mp4", ".webm", ".mov", ".m4v")):
        return f"- [{basename}]({url}) — open to play / download video"
    return f"- [{basename}]({url})"


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

    # Fail before create when evidence was requested without a project token —
    # otherwise a retry hits dedupe and never uploads.
    if a.attach and not has_project_token:
        print(
            "GITHUB_ATTACH_TOKEN_REQUIRED — set GITHUB_TOKEN in "
            f"{a.project}/.secrets/github.env before --attach",
            file=sys.stderr,
        )
        return 3

    num: int | None = None
    url = ""
    if not a.no_dedupe:
        hit = find_dedupe_hit(repo_ref, a.summary, env=gh_env)
        if hit:
            num = int(hit["number"])
            url = str(hit.get("url") or f"https://github.com/{repo_ref}/issues/{num}")
            print(f"GITHUB_DEDUPE_HIT {slug}#{num} → {url}")
            if not a.attach:
                print(f"{slug}#{num}")
                return 0

    if num is None:
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
        m = re.search(r"/issues/(\d+)\s*$", created) or re.search(r"/issues/(\d+)", created)
        if not m:
            print(f"Created but could not parse issue number from: {created}", file=sys.stderr)
            return 2
        num = int(m.group(1))
        url = created if created.startswith("http") else f"https://github.com/{repo_ref}/issues/{num}"
        print(f"Created {slug}#{num} → {url}")

    key = f"{slug}#{num}"

    evidence_lines: list[str] = ["## Evidence attachments", ""]
    attached_ok = False
    screenshot_ok = False
    recording_ok = False
    for path in a.attach:
        if not os.path.isfile(path):
            print(f"  ! attachment not found: {path}", file=sys.stderr)
            evidence_lines.append(f"- missing: `{path}`")
            continue
        base = os.path.basename(path)
        url = github_repo_evidence_upload(
            path,
            owner=owner,
            repo=repo,
            issue_key=key,
            message=f"qa-agent evidence for {key}: {base}",
            env=gh_env,
        )
        if not url and not _is_media_path(path):
            url = secret_gist_upload(path, f"qa-agent evidence for {key}", env=gh_env)
        if url:
            attached_ok = True
            lower = base.lower()
            if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                screenshot_ok = True
            elif lower.endswith((".mp4", ".webm", ".mov", ".m4v")):
                recording_ok = True
            evidence_lines.append(evidence_markdown_line(base, url))
            print(f"  attached {base} → {url}")
        else:
            evidence_lines.append(f"- upload failed: `{path}`")
            print(f"  ! evidence upload failed for {path}", file=sys.stderr)

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
        if screenshot_ok:
            print("  bug_screenshot_attached=true (qa-evidence branch via project token)")
        if recording_ok:
            print("  bug_recording_attached=true (qa-evidence branch via project token)")
        if not attached_ok:
            print(key)
            print(
                "GITHUB_ATTACH_UPLOAD_FAILED — issue exists but no evidence uploaded",
                file=sys.stderr,
            )
            return 3

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

    print(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
