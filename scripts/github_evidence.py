#!/usr/bin/env python3
"""Upload QA evidence so it is *viewable* in GitHub Issue comments.

GitHub gists reject binary files; base64-wrapped ``.txt`` gists are not playable
or previewable in the issue UI. This module stores media on a dedicated
``qa-evidence`` branch via the Contents API and embeds PNG/JPEG (and video
preview frames) with markdown image syntax so they render inline in comments.

Text-only attachments may still use a secret gist.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

EVIDENCE_BRANCH = "qa-evidence"
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")
VIDEO_EXT = (".mp4", ".webm", ".mov", ".m4v")


def _gh_json(
    args: list[str],
    *,
    env: dict[str, str],
    quiet_http: set[int] | None = None,
) -> Any | None:
    try:
        out = subprocess.check_output(
            ["gh", "api", *args],
            text=True,
            stderr=subprocess.PIPE,
            env=env,
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        quiet = quiet_http or set()
        # gh prints "gh: Not Found (HTTP 404)" — suppress expected misses
        if any(f"HTTP {code}" in err for code in quiet):
            return None
        if err:
            print(f"gh api error: {err}", file=__import__("sys").stderr)
        return None
    try:
        return json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        return None


def ensure_evidence_branch(owner: str, repo: str, *, env: dict[str, str]) -> bool:
    """Create ``qa-evidence`` from default branch HEAD if missing."""
    ref = _gh_json(
        [f"repos/{owner}/{repo}/git/ref/heads/{EVIDENCE_BRANCH}"],
        env=env,
        quiet_http={404},
    )
    if isinstance(ref, dict) and ref.get("object"):
        return True
    meta = _gh_json([f"repos/{owner}/{repo}"], env=env) or {}
    default = str(meta.get("default_branch") or "main")
    head = _gh_json(
        [f"repos/{owner}/{repo}/git/ref/heads/{default}"],
        env=env,
    )
    if not isinstance(head, dict) or not head.get("object", {}).get("sha"):
        print(f"cannot resolve default branch {default} for {owner}/{repo}", file=__import__("sys").stderr)
        return False
    sha = head["object"]["sha"]
    created = _gh_json(
        [
            f"repos/{owner}/{repo}/git/refs",
            "-f",
            f"ref=refs/heads/{EVIDENCE_BRANCH}",
            "-f",
            f"sha={sha}",
        ],
        env=env,
    )
    return isinstance(created, dict) and bool(created.get("ref") or created.get("object"))


def repo_evidence_upload(
    path: str,
    *,
    owner: str,
    repo: str,
    issue_key: str,
    env: dict[str, str],
    message: str | None = None,
) -> str | None:
    """Put ``path`` on ``qa-evidence`` and return a raw URL (commit-pinned)."""
    if not os.path.isfile(path):
        return None
    if not ensure_evidence_branch(owner, repo, env=env):
        return None

    base = os.path.basename(path)
    safe_key = re.sub(r"[^A-Za-z0-9._-]+", "-", issue_key.strip()) or "ticket"
    dest = f"qa-evidence/{safe_key}/{int(time.time())}-{base}"

    with open(path, "rb") as fh:
        content_b64 = base64.b64encode(fh.read()).decode("ascii")

    msg = message or f"qa-agent evidence for {issue_key}: {base}"
    # Prefer --input JSON to avoid argv size limits on large media.
    payload = {
        "message": msg[:200],
        "content": content_b64,
        "branch": EVIDENCE_BRANCH,
    }
    try:
        raw = subprocess.check_output(
            [
                "gh",
                "api",
                f"repos/{owner}/{repo}/contents/{dest}",
                "-X",
                "PUT",
                "--input",
                "-",
            ],
            text=True,
            stderr=subprocess.PIPE,
            env=env,
            input=json.dumps(payload),
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        if err:
            print(f"evidence upload error: {err}", file=__import__("sys").stderr)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("evidence upload: invalid JSON response", file=__import__("sys").stderr)
        return None

    commit_sha = (data.get("commit") or {}).get("sha") or ""
    if not commit_sha:
        print("evidence upload: missing commit sha", file=__import__("sys").stderr)
        return None
    # Commit-pinned raw URL — renders for users with repo access (private OK).
    return f"https://github.com/{owner}/{repo}/raw/{commit_sha}/{dest}"


def extract_video_preview_frames(video_path: str, *, count: int = 4) -> list[str]:
    """Return paths to PNG frames extracted with ffmpeg (temp files)."""
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found — skipping video preview frames", file=__import__("sys").stderr)
        return []
    if not os.path.isfile(video_path):
        return []

    # Duration via ffprobe when available; else sample fixed offsets.
    duration = 0.0
    if shutil.which("ffprobe"):
        try:
            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            duration = float(out)
        except (subprocess.CalledProcessError, ValueError):
            duration = 0.0

    if duration <= 0:
        stamps = [0.5, 2.0, 4.0, 6.0][:count]
    else:
        # Avoid exact end-of-file; sample interior frames.
        stamps = [
            max(0.05, duration * (i + 1) / (count + 1))
            for i in range(count)
        ]

    tmp = tempfile.mkdtemp(prefix="qa-ev-frames-")
    frames: list[str] = []
    for i, ts in enumerate(stamps):
        out = os.path.join(tmp, f"preview-{i + 1:02d}.png")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{ts:.3f}",
                    "-i",
                    video_path,
                    "-frames:v",
                    "1",
                    out,
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            continue
        if os.path.isfile(out) and os.path.getsize(out) > 100:
            frames.append(out)
    return frames


def secret_gist_upload_text(path: str, desc: str, *, env: dict[str, str]) -> str | None:
    """Upload a *text* file as a secret gist (binaries rejected by GitHub)."""
    if not os.path.isfile(path):
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
            print(f"secret gist upload error: {err}", file=__import__("sys").stderr)
        return None
    except OSError as e:
        print(f"secret gist upload error: {e}", file=__import__("sys").stderr)
        return None
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def build_evidence_markdown(
    path: str,
    *,
    owner: str,
    repo: str,
    issue_key: str,
    caption: str,
    env: dict[str, str],
) -> tuple[str, str] | None:
    """Upload ``path`` and return ``(markdown_body, flag)`` or None on failure.

    ``flag`` is one of ``bug_screenshot_attached=true``,
    ``bug_recording_attached=true``, ``evidence_attached=true``.
    """
    base = os.path.basename(path)
    lower = base.lower()

    if lower.endswith(IMAGE_EXT):
        url = repo_evidence_upload(
            path, owner=owner, repo=repo, issue_key=issue_key, env=env
        )
        if not url:
            return None
        body = f"## {caption}\n\n![{base}]({url})\n"
        return body, "bug_screenshot_attached=true"

    if lower.endswith(VIDEO_EXT):
        lines = [f"## {caption}", "", "### Preview (inline)", ""]
        frames = extract_video_preview_frames(path)
        for i, frame in enumerate(frames, start=1):
            furl = repo_evidence_upload(
                frame,
                owner=owner,
                repo=repo,
                issue_key=issue_key,
                env=env,
                message=f"qa-agent preview frame {i} for {issue_key}",
            )
            try:
                os.remove(frame)
            except OSError:
                pass
            if furl:
                lines.append(f"![preview {i}]({furl})")
                lines.append("")
        # Best-effort cleanup of frame temp dir
        if frames:
            parent = os.path.dirname(frames[0])
            shutil.rmtree(parent, ignore_errors=True)

        vurl = repo_evidence_upload(
            path, owner=owner, repo=repo, issue_key=issue_key, env=env
        )
        # Recording attach succeeds only when the mp4 lands. Preview frames are
        # optional; returning bug_recording_attached without vurl would let
        # record_and_attach.sh delete the local clip while DoD still sees success.
        if not vurl:
            return None
        lines.append("### Full recording")
        lines.append("")
        lines.append(f"- [{base}]({vurl}) — open on GitHub to download / play")
        lines.append("")
        return "\n".join(lines), "bug_recording_attached=true"

    # Text / other: gist when possible (viewable as text in gist UI)
    gist = secret_gist_upload_text(path, f"{caption} ({issue_key})", env=env)
    if gist:
        body = f"## {caption}\n\n- [{base}]({gist})\n"
        return body, "evidence_attached=true"

    # Fallback: store on evidence branch even if not an image
    url = repo_evidence_upload(
        path, owner=owner, repo=repo, issue_key=issue_key, env=env
    )
    if not url:
        return None
    body = f"## {caption}\n\n- [{base}]({url})\n"
    return body, "evidence_attached=true"
