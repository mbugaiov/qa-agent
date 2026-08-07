#!/usr/bin/env python3
"""Unit tests for VERDICT_REVIEW_PASS tracker comment gate."""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from verdict_review_comment_require import (  # noqa: E402
    comment_has_verdict_review_blocked,
    comment_has_verdict_review_pass,
    format_pass_comment,
    latest_pass_or_blocked,
    require_verdict_review_comment,
)


class VerdictReviewCommentTest(unittest.TestCase):
    def test_pass_sentinel_line(self) -> None:
        self.assertTrue(
            comment_has_verdict_review_pass("VERDICT_REVIEW_PASS\nartifact: x\n")
        )
        self.assertTrue(
            comment_has_verdict_review_pass("## VERDICT_REVIEW_PASS\nsummary: ok\n")
        )
        self.assertFalse(
            comment_has_verdict_review_pass(
                "Wait for VERDICT_REVIEW_PASS before close.\n"
            )
        )

    def test_blocked(self) -> None:
        self.assertTrue(
            comment_has_verdict_review_blocked("VERDICT_REVIEW_BLOCKED\n- gap\n")
        )

    def test_latest_wins(self) -> None:
        bodies = [
            "VERDICT_REVIEW_PASS\nartifact: a\n",
            "VERDICT_REVIEW_BLOCKED\n- no\n",
        ]
        self.assertEqual(latest_pass_or_blocked(bodies), "blocked")
        bodies.append("VERDICT_REVIEW_PASS\nartifact: b\n")
        self.assertEqual(latest_pass_or_blocked(bodies), "pass")

    def test_require_blocks_without_comment(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            require_verdict_review_comment("/tmp", "app#1", bodies=[])
        self.assertEqual(cm.exception.code, 7)

    def test_require_pass_with_bodies(self) -> None:
        require_verdict_review_comment(
            "/tmp",
            "app#1",
            bodies=[format_pass_comment(artifact="runs/x.md", summary="ok")],
        )

    def test_format_includes_sentinel(self) -> None:
        body = format_pass_comment(artifact="runs/vr.md", summary="PASS candidate")
        self.assertIn("VERDICT_REVIEW_PASS", body)
        self.assertIn("artifact: runs/vr.md", body)

    def test_jira_inactive_placeholder_skips(self) -> None:
        import tempfile
        from pathlib import Path

        from verdict_review_comment_require import is_jira_inactive

        with tempfile.TemporaryDirectory() as td:
            secrets = Path(td) / ".secrets"
            secrets.mkdir()
            (secrets / "jira.env").write_text(
                "\n".join(
                    [
                        "JIRA_BASE_URL=https://your-company.atlassian.net",
                        "JIRA_EMAIL=paste-email@example.com",
                        "JIRA_API_TOKEN=paste-token",
                        "JIRA_PROJECT_KEY=ABC",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertTrue(is_jira_inactive(td))
            # Must no-op (not exit 7) when fetching without injected bodies.
            require_verdict_review_comment(td, "ABC-1")



if __name__ == "__main__":
    unittest.main()
