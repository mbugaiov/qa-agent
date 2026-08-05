#!/usr/bin/env python3
"""Unit tests for acceptance smoke pack Done gate."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from smoke_pack_require import (  # noqa: E402
    has_smoke_pack_pass,
    pack_exists,
    require_smoke_pack_pass,
)


class SmokePackRequireTest(unittest.TestCase):
    def test_pack_missing_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            require_smoke_pack_pass(d, "app#1")  # no raise

    def test_pack_exists_blocks_without_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "automation", "specs"))
            with open(
                os.path.join(d, "automation", "specs", "acceptance-smoke.spec.js"),
                "w",
                encoding="utf-8",
            ) as fh:
                fh.write("// pack\n")
            self.assertTrue(pack_exists(d))
            with self.assertRaises(SystemExit) as cm:
                require_smoke_pack_pass(d, "myapp#1")
            self.assertEqual(cm.exception.code, 5)

    def test_dod_smoke_pack_pass(self) -> None:
        events = [
            {
                "event": "dod_check",
                "detail": {"verdict": "DONE", "smoke_pack": "pass"},
            }
        ]
        self.assertTrue(has_smoke_pack_pass(events))

    def test_smoke_pack_event_pass(self) -> None:
        events = [{"event": "smoke_pack", "detail": {"result": "pass"}}]
        self.assertTrue(has_smoke_pack_pass(events))
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "automation", "specs"))
            with open(
                os.path.join(d, "automation", "specs", "acceptance-smoke.spec.js"),
                "w",
                encoding="utf-8",
            ) as fh:
                fh.write("// pack\n")
            os.makedirs(os.path.join(d, "factory", "runs"))
            with open(
                os.path.join(d, "factory", "runs", "myapp#1.jsonl"),
                "w",
                encoding="utf-8",
            ) as fh:
                fh.write(json.dumps(events[0]) + "\n")
            require_smoke_pack_pass(d, "myapp#1")  # no raise


if __name__ == "__main__":
    unittest.main()
