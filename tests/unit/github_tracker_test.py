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
    tracker_provider,
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


if __name__ == "__main__":
    unittest.main()
