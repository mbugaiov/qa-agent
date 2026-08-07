#!/usr/bin/env python3
"""Unit tests for recording_attached Done gate."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from recording_require import (  # noqa: E402
    has_recording_attached,
    has_recording_exempt,
    require_recording_attached,
)


class RecordingRequireTest(unittest.TestCase):
    def test_blocks_without_recording(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "factory", "runs"))
            with self.assertRaises(SystemExit) as cm:
                require_recording_attached(d, "myapp#1")
            self.assertEqual(cm.exception.code, 6)

    def test_dod_recording_pass(self) -> None:
        events = [
            {
                "event": "dod_check",
                "detail": {"verdict": "DONE", "recording_attached": "true"},
            }
        ]
        self.assertTrue(has_recording_attached(events))
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "factory", "runs"))
            with open(
                os.path.join(d, "factory", "runs", "myapp#1.jsonl"),
                "w",
                encoding="utf-8",
            ) as fh:
                fh.write(json.dumps(events[0]) + "\n")
            require_recording_attached(d, "myapp#1")

    def test_recording_event_pass(self) -> None:
        events = [{"event": "recording_attached", "detail": {"result": "pass"}}]
        self.assertTrue(has_recording_attached(events))

    def test_exempt_skips(self) -> None:
        events = [
            {
                "event": "dod_check",
                "detail": {"verdict": "DONE", "recording_exempt": "true"},
            }
        ]
        self.assertTrue(has_recording_exempt(events))
        require_recording_attached(
            "/tmp",
            "x#1",
            events=events,
        )

    def test_allow_missing(self) -> None:
        require_recording_attached("/tmp", "x#1", allow_missing=True)


if __name__ == "__main__":
    unittest.main()
