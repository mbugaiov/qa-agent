#!/usr/bin/env python3
"""Parse Argus verdict-review output (## Blocking gaps) — same spirit as review_gate.py."""
from __future__ import annotations

import re
import sys

LGTM_LINE = re.compile(r"^LGTM - no blocking gaps found\.?\s*$", re.I)


def is_lgtm_only(text: str) -> bool:
    trimmed = text.strip()
    return bool(trimmed) and "\n" not in trimmed and bool(LGTM_LINE.match(trimmed))


def extract_blocking_gaps(text: str) -> str | None:
    lines = text.split("\n")
    in_section = False
    body: list[str] = []
    for line in lines:
        if re.match(r"^## Blocking gaps\s*$", line, re.I):
            in_section = True
            continue
        if in_section and re.match(r"^## ", line):
            break
        if in_section:
            body.append(line)
    if not in_section:
        return None
    return "\n".join(body).strip()


def verdict_review_has_blockers(text: str) -> bool:
    trimmed = text.strip()
    if not trimmed:
        return True
    if is_lgtm_only(trimmed):
        return False
    section = extract_blocking_gaps(text)
    if section is None:
        return True
    if re.match(r"^None\.?\s*$", section, re.I):
        return False
    if not section:
        return True
    return True


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "verdict-review.md"
    text = open(path, encoding="utf-8").read()
    if verdict_review_has_blockers(text):
        section = extract_blocking_gaps(text)
        print("Verdict review FAILED — blocking gaps found:", file=sys.stderr)
        if section:
            print(section, file=sys.stderr)
        return 1
    print("Verdict review gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
