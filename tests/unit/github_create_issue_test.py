#!/usr/bin/env python3
"""Unit tests for github_create_issue helpers."""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from github_create_issue import build_labels, normalize_title, parse_related_number  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
