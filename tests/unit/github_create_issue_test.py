#!/usr/bin/env python3
"""Unit tests for github_create_issue helpers and attach/dedupe isolation gate."""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import github_create_issue as gci  # noqa: E402
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

    def test_project_gh_env_no_token(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".secrets"))
            env, ok = project_gh_env(d)
            self.assertFalse(ok)
            self.assertIsInstance(env, dict)


class GithubCreateIssueAttachGateTest(unittest.TestCase):
    """Isolation contract: --attach requires project token; dedupe still uploads."""

    def _argv(self, project: str, *extra: str) -> list[str]:
        return [
            "github_create_issue.py",
            "--project",
            project,
            "--summary",
            "PF: attach gate title",
            "--description",
            "body",
            "--severity",
            "S2",
            "--labels",
            "confirmed-defect",
            *extra,
        ]

    def test_attach_without_project_token_exits_3_before_create(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            shot = os.path.join(d, "fail.png")
            with open(shot, "wb") as fh:
                fh.write(b"fake-png")
            argv = self._argv(d, "--attach", shot)
            err = io.StringIO()
            out = io.StringIO()
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                gci, "github_inactive", return_value=False
            ), mock.patch.object(
                gci, "github_repo", return_value=("acme", "demo")
            ), mock.patch.object(
                gci, "project_gh_env", return_value=({"PATH": "/usr/bin"}, False)
            ), mock.patch.object(
                gci, "find_dedupe_hit"
            ) as dedupe, mock.patch.object(
                gci.subprocess, "check_output"
            ) as check_out, mock.patch.object(
                gci.subprocess, "run"
            ) as run, redirect_stdout(out), redirect_stderr(err):
                rc = gci.main()
            self.assertEqual(rc, 3)
            self.assertIn("GITHUB_ATTACH_TOKEN_REQUIRED", err.getvalue())
            dedupe.assert_not_called()
            check_out.assert_not_called()
            # Must not create an issue (or comment) when gate fails early
            run.assert_not_called()

    def test_dedupe_hit_with_attach_uploads_to_existing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            shot = os.path.join(d, "fail.png")
            with open(shot, "wb") as fh:
                fh.write(b"fake-png")
            slug = os.path.basename(d)
            argv = self._argv(d, "--attach", shot)
            err = io.StringIO()
            out = io.StringIO()
            hit = {
                "number": 42,
                "title": "PF: attach gate title",
                "url": "https://github.com/acme/demo/issues/42",
            }
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                gci, "github_inactive", return_value=False
            ), mock.patch.object(
                gci, "github_repo", return_value=("acme", "demo")
            ), mock.patch.object(
                gci,
                "project_gh_env",
                return_value=({"GH_TOKEN": "proj", "GITHUB_TOKEN": "proj"}, True),
            ), mock.patch.object(
                gci, "find_dedupe_hit", return_value=hit
            ), mock.patch.object(
                gci,
                "secret_gist_upload",
                return_value="https://gist.github.com/abc",
            ) as gist, mock.patch.object(
                gci.subprocess, "check_output"
            ) as check_out, mock.patch.object(
                gci.subprocess, "run"
            ) as run, redirect_stdout(out), redirect_stderr(err):
                rc = gci.main()
            self.assertEqual(rc, 0)
            stdout = out.getvalue()
            self.assertIn("GITHUB_DEDUPE_HIT", stdout)
            self.assertIn(f"{slug}#42", stdout)
            self.assertIn("bug_screenshot_attached=true", stdout)
            gist.assert_called_once()
            # Must not create a new issue on dedupe hit
            create_calls = [
                c
                for c in check_out.call_args_list
                if c.args and isinstance(c.args[0], list) and "create" in c.args[0]
            ]
            self.assertEqual(create_calls, [])
            # Evidence comment targets the existing issue number
            comment_cmds = [
                c.args[0]
                for c in run.call_args_list
                if c.args and isinstance(c.args[0], list) and "comment" in c.args[0]
            ]
            self.assertTrue(comment_cmds, "expected gh issue comment on dedupe+attach")
            self.assertIn("42", comment_cmds[0])

    def test_dedupe_hit_without_attach_skips_upload(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            argv = self._argv(d)
            out = io.StringIO()
            hit = {
                "number": 7,
                "title": "PF: attach gate title",
                "url": "https://github.com/acme/demo/issues/7",
            }
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                gci, "github_inactive", return_value=False
            ), mock.patch.object(
                gci, "github_repo", return_value=("acme", "demo")
            ), mock.patch.object(
                gci,
                "project_gh_env",
                return_value=({"GH_TOKEN": "proj"}, True),
            ), mock.patch.object(
                gci, "find_dedupe_hit", return_value=hit
            ), mock.patch.object(
                gci, "upload_attachments"
            ) as upload, mock.patch.object(
                gci.subprocess, "check_output"
            ) as check_out, redirect_stdout(out):
                rc = gci.main()
            self.assertEqual(rc, 0)
            upload.assert_not_called()
            check_out.assert_not_called()
            self.assertIn("GITHUB_DEDUPE_HIT", out.getvalue())


if __name__ == "__main__":
    unittest.main()
