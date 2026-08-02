"""Shared helpers for GitHub Issues tracker (non-Jira QA factories)."""
from __future__ import annotations

import os
import re
import subprocess
from typing import Any


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


def load_project_yaml(project_dir: str) -> dict[str, Any]:
    path = os.path.join(project_dir, "project.yaml")
    if not os.path.exists(path):
        return {}
    try:
        import yaml  # type: ignore

        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        # Minimal fallback: regex for tracker/git keys
        text = open(path, encoding="utf-8").read()
        out: dict[str, Any] = {}
        m = re.search(r"tracker:\s*\n(?:[ \t]+.+\n)*?", text)
        prov = re.search(r"provider:\s*(\S+)", text)
        if prov:
            out.setdefault("tracker", {})["provider"] = prov.group(1).strip('"')
        owner = re.search(r"workspace:\s*(\S+)", text)
        repo = re.search(r"^\s*repo:\s*(\S+)", text, re.M)
        if owner or repo:
            git: dict[str, str] = {}
            if owner:
                git["workspace"] = owner.group(1).strip('"')
            if repo:
                git["repo"] = repo.group(1).strip('"')
            out["git"] = git
        return out


def tracker_provider(project_dir: str) -> str:
    cfg = load_project_yaml(project_dir)
    t = cfg.get("tracker") or {}
    if isinstance(t, dict) and t.get("provider"):
        return str(t["provider"])
    jira = cfg.get("jira") or {}
    if isinstance(jira, dict) and jira.get("enabled") is False:
        git = cfg.get("git") or {}
        if isinstance(git, dict) and git.get("provider") == "github":
            return "github_issues"
    return "jira"


def resolve_github_repo(project_dir: str) -> tuple[str, str] | None:
    """Return (owner, repo) or None when unconfigured (offline / template)."""
    cfg = load_project_yaml(project_dir)
    git = cfg.get("git") or {}
    tracker = cfg.get("tracker") or {}
    owner = (
        (tracker.get("owner") if isinstance(tracker, dict) else None)
        or (git.get("workspace") if isinstance(git, dict) else None)
        or os.environ.get("GITHUB_OWNER", "")
    )
    repo = (
        (tracker.get("repo") if isinstance(tracker, dict) else None)
        or (git.get("repo") if isinstance(git, dict) else None)
        or os.environ.get("GITHUB_REPO", "")
    )
    env = load_env_file(os.path.join(project_dir, ".secrets", "github.env"))
    owner = env.get("GITHUB_OWNER", owner) or owner
    repo = env.get("GITHUB_REPO", repo) or repo
    if not owner or not repo:
        return None
    return str(owner), str(repo)


def github_repo(project_dir: str) -> tuple[str, str]:
    resolved = resolve_github_repo(project_dir)
    if not resolved:
        raise SystemExit(
            f"GitHub owner/repo missing in {project_dir}/project.yaml tracker/git "
            "or .secrets/github.env"
        )
    return resolved


def github_inactive(project_dir: str) -> bool:
    """True when GitHub tracker cannot run (no repo config or no gh CLI)."""
    if resolve_github_repo(project_dir) is None:
        return True
    try:
        subprocess.run(
            ["gh", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return True
    return False


def validate_label(project_dir: str) -> str:
    cfg = load_project_yaml(project_dir)
    t = cfg.get("tracker") or {}
    if isinstance(t, dict) and t.get("validate_label"):
        return str(t["validate_label"])
    return "validate-testing"


def pickup_label(project_dir: str) -> str:
    cfg = load_project_yaml(project_dir)
    t = cfg.get("tracker") or {}
    if isinstance(t, dict) and t.get("pickup_label"):
        return str(t["pickup_label"])
    return "impl-dev"


def done_label(project_dir: str) -> str:
    cfg = load_project_yaml(project_dir)
    t = cfg.get("tracker") or {}
    if isinstance(t, dict) and t.get("done_label"):
        return str(t["done_label"])
    return "done"


def gh_json(args: list[str]) -> Any:
    import json

    raw = subprocess.check_output(["gh", *args], text=True)
    return json.loads(raw) if raw.strip() else None


def gh_run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        check=check,
        text=True,
        capture_output=True,
    )


def extract_hints(text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    m = re.search(r"STG buildId[:\s]+([0-9a-f]{7,40})", text, re.I)
    if not m:
        m = re.search(r"buildId[:\s]+([0-9a-f]{7,40})", text, re.I)
    if m:
        hints["buildId"] = m.group(1)
    prs = re.findall(
        r"https?://(?:bitbucket\.org/\S+pull-requests/\d+|github\.com/\S+/pull/\d+)",
        text,
        re.I,
    )
    if prs:
        hints["pr"] = prs[0]
    pipe = re.search(r"Pipeline build[:\s#]+(\S+)", text, re.I)
    if pipe:
        hints["pipeline"] = pipe.group(1).lstrip("#")
    return hints


def is_dev_handoff_comment(text: str) -> bool:
    t = text or ""
    return (
        "What was implemented:" in t
        and "Merged PR:" in t
        and re.search(r"Pipeline build:", t, re.I) is not None
    )
