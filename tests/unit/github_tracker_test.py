#!/usr/bin/env python3
"""Unit tests for GitHub Issues QA tracker helpers."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_tracker import (  # noqa: E402
    extract_hints,
    is_dev_handoff_comment,
    load_project_yaml,
    resolve_github_repo,
    tracker_provider,
    validate_label,
)


class GithubTrackerTest(unittest.TestCase):
    def test_extract_hints_github_pr(self) -> None:
        text = """
What was implemented: seals
Merged PR: https://github.com/example-corp/my-app/pull/42
Pipeline build: #9
STG buildId: abcdef1234567890 (main abcdef1234567890)
"""
        h = extract_hints(text)
        self.assertEqual(h.get("buildId"), "abcdef1234567890")
        self.assertIn("github.com/example-corp/my-app/pull/42", h.get("pr", ""))
        self.assertEqual(h.get("pipeline"), "9")

    def test_is_dev_handoff(self) -> None:
        self.assertTrue(
            is_dev_handoff_comment(
                "What was implemented: x\nMerged PR: https://x\nPipeline build: #1\n"
            )
        )
        self.assertFalse(is_dev_handoff_comment("just a note"))

    def test_tracker_provider_github(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "project.yaml"), "w", encoding="utf-8") as fh:
                fh.write(
                    "slug: myapp\n"
                    "tracker:\n  provider: github_issues\n"
                    "jira:\n  enabled: false\n"
                    "git:\n  provider: github\n  workspace: example-corp\n  repo: my-app\n"
                )
            self.assertEqual(tracker_provider(d), "github_issues")

    def test_git_github_jira_disabled_no_tracker_stays_jira(self) -> None:
        """git.provider=github + jira disabled must not imply github_issues."""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "project.yaml"), "w", encoding="utf-8") as fh:
                fh.write(
                    "slug: myapp\n"
                    "jira:\n  enabled: false\n"
                    "git:\n  provider: github\n  workspace: example-corp\n  repo: my-app\n"
                )
            self.assertEqual(tracker_provider(d), "jira")

    def test_ambient_github_env_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "project.yaml"), "w", encoding="utf-8") as fh:
                fh.write("slug: myapp\njira:\n  enabled: false\n")
            prev_o = os.environ.get("GITHUB_OWNER")
            prev_r = os.environ.get("GITHUB_REPO")
            try:
                os.environ["GITHUB_OWNER"] = "evil-corp"
                os.environ["GITHUB_REPO"] = "evil-repo"
                self.assertIsNone(resolve_github_repo(d))
                self.assertEqual(tracker_provider(d), "jira")
            finally:
                if prev_o is None:
                    os.environ.pop("GITHUB_OWNER", None)
                else:
                    os.environ["GITHUB_OWNER"] = prev_o
                if prev_r is None:
                    os.environ.pop("GITHUB_REPO", None)
                else:
                    os.environ["GITHUB_REPO"] = prev_r

    def test_commented_tracker_not_active(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "project.yaml"), "w", encoding="utf-8") as fh:
                fh.write(
                    "slug: myapp\n"
                    "jira:\n  enabled: false\n"
                    "# tracker:\n"
                    "#   provider: github_issues\n"
                    "# git:\n"
                    "#   provider: github\n"
                    "#   workspace: example-corp\n"
                    "#   repo: my-app\n"
                )
            cfg = load_project_yaml(d)
            self.assertNotEqual((cfg.get("tracker") or {}).get("provider"), "github_issues")
            self.assertEqual(tracker_provider(d), "jira")

    def test_noyaml_fallback_scopes_provider_under_tracker(self) -> None:
        """git.provider before tracker.provider must not win when PyYAML is absent."""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "project.yaml"), "w", encoding="utf-8") as fh:
                fh.write(
                    "slug: myapp\n"
                    "git:\n  provider: github\n  workspace: example-corp\n  repo: my-app\n"
                    "jira:\n  enabled: false\n"
                    "tracker:\n  provider: github_issues\n"
                    "  validate_label: qa-validate\n"
                )
            import builtins

            real_import = builtins.__import__

            def _block_yaml(name: str, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
                if name == "yaml" or name.startswith("yaml."):
                    raise ImportError("forced no PyYAML")
                return real_import(name, *args, **kwargs)

            builtins.__import__ = _block_yaml  # type: ignore[assignment]
            try:
                cfg = load_project_yaml(d)
                self.assertEqual((cfg.get("tracker") or {}).get("provider"), "github_issues")
                self.assertEqual((cfg.get("tracker") or {}).get("validate_label"), "qa-validate")
                self.assertEqual((cfg.get("git") or {}).get("provider"), "github")
                self.assertEqual((cfg.get("git") or {}).get("workspace"), "example-corp")
                self.assertEqual(tracker_provider(d), "github_issues")
                self.assertEqual(validate_label(d), "qa-validate")
            finally:
                builtins.__import__ = real_import  # type: ignore[assignment]

    def test_validate_label_custom(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "project.yaml"), "w", encoding="utf-8") as fh:
                fh.write(
                    "slug: myapp\n"
                    "tracker:\n  provider: github_issues\n  validate_label: qa-validate\n"
                )
            self.assertEqual(validate_label(d), "qa-validate")


if __name__ == "__main__":
    unittest.main()
