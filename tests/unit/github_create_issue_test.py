#!/usr/bin/env python3
"""Unit tests for github_create_issue helpers."""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_create_issue import (  # noqa: E402
    build_labels,
    normalize_title,
    parse_related_number,
    project_gh_env,
)


class GithubCreateIssueTest(unittest.TestCase):
    def test_normalize_title(self) -> None:
        self.assertEqual(normalize_title("  Foo   BAR "), "foo bar")

    def test_confirmed_defect_adds_impl_dev(self) -> None:
        labels = build_labels(
            slug="myapp",
            raw_labels="myapp,confirmed-defect",
            severity="S2",
            no_impl_dev=False,
            pickup="impl-dev",
        )
        self.assertIn("qa-agent", labels)
        self.assertIn("myapp", labels)
        self.assertIn("confirmed-defect", labels)
        self.assertIn("severity-s2", labels)
        self.assertIn("impl-dev", labels)

    def test_no_impl_dev_flag(self) -> None:
        labels = build_labels(
            slug="myapp",
            raw_labels="confirmed-defect",
            severity=None,
            no_impl_dev=True,
            pickup="impl-dev",
        )
        self.assertNotIn("impl-dev", labels)

    def test_parse_related(self) -> None:
        self.assertEqual(parse_related_number("myapp#40"), 40)
        self.assertIsNone(parse_related_number("nope"))

    def test_project_gh_env_strips_ambient(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            sec = os.path.join(d, ".secrets")
            os.makedirs(sec)
            with open(os.path.join(sec, "github.env"), "w", encoding="utf-8") as fh:
                fh.write("GITHUB_TOKEN=project-token-xyz\n")
            prev = os.environ.get("GH_TOKEN")
            try:
                os.environ["GH_TOKEN"] = "ambient-should-not-win"
                env, ok = project_gh_env(d)
                self.assertTrue(ok)
                self.assertEqual(env.get("GH_TOKEN"), "project-token-xyz")
                self.assertEqual(env.get("GITHUB_TOKEN"), "project-token-xyz")
            finally:
                if prev is None:
                    os.environ.pop("GH_TOKEN", None)
                else:
                    os.environ["GH_TOKEN"] = prev


if __name__ == "__main__":
    unittest.main()
