#!/usr/bin/env python3
"""Parse Cursor code-review output for blocking issues (engine CR gate).

Port of LRM lib/reviewGate.ts — pure parsing, no I/O except CLI wrapper.
"""
from __future__ import annotations

import re
import sys

LGTM_LINE = re.compile(r"^LGTM - no blocking issues found\.?\s*$", re.I)
NO_OUTPUT_PLACEHOLDER = re.compile(
    r"^Cursor review produced no output \(see build log above\)\.\s*$", re.I
)

# Historical RQ-1647 failure modes + clean passes (see tests/fixtures/review-gate/)
REVIEW_GATE_FIXTURES: dict[str, str] = {
    "lgtm.md": "pass",
    "blocking-none.md": "pass",
    "blocking-items.md": "fail",
    "no-output.md": "fail",
    "unstructured-error.md": "fail",
    "empty-blocking-section.md": "fail",
    "missing-blocking-header.md": "fail",
    "false-lgtm-after-blockers.md": "fail",
}


def is_lgtm_only(text: str) -> bool:
    trimmed = text.strip()
    return bool(trimmed) and "\n" not in trimmed and bool(LGTM_LINE.match(trimmed))


def extract_blocking_section(text: str) -> str | None:
    lines = text.split("\n")
    in_section = False
    body: list[str] = []
    for line in lines:
        if re.match(r"^## Blocking issues\s*$", line, re.I):
            in_section = True
            continue
        if in_section and re.match(r"^## ", line):
            break
        if in_section:
            body.append(line)
    if not in_section:
        return None
    return "\n".join(body).strip()


def review_has_blockers(text: str) -> bool:
    trimmed = text.strip()
    if not trimmed:
        return True
    if is_lgtm_only(trimmed):
        return False
    if NO_OUTPUT_PLACEHOLDER.match(trimmed):
        return True

    section = extract_blocking_section(text)
    if section is None:
        return True
    if re.match(r"^None\.?\s*$", section, re.I):
        return False
    if not section:
        return True
    return True


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "review.md"
    text = open(path, encoding="utf-8").read()

    if review_has_blockers(text):
        section = extract_blocking_section(text)
        print("Review gate FAILED — blocking issues found:", file=sys.stderr)
        if section:
            print(section, file=sys.stderr)
        return 1

    print("Review gate: pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
