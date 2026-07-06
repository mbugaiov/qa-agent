#!/usr/bin/env python3
"""Check spec-driven coverage for a project: REQ -> SC -> TC.

Reads, for projects/<slug>/:
  requirements/requirements.md   -> all REQ-* ids
  specs/*.md                     -> SC-* ids and the REQ-* each one "Covers:"
  test-cases/test-cases.md       -> TC-* ids and the SC-* each one references

Reports gaps:
  - REQ with no covering scenario        (requirements gap)
  - SC  with no deriving test case       (coverage gap)
  - SC  covering an unknown REQ          (typo / stale)
  - TC  referencing an unknown SC        (typo / stale)

Exit code: 0 if no gaps, 1 if any gap (so it can act as a gate).
Use --warn to always exit 0 (informational only).

Usage:
    python3 scripts/check_coverage.py projects/<slug> [--warn]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

REQ_RE = re.compile(r"REQ-\d+")
SC_RE = re.compile(r"SC-\d+")
TC_RE = re.compile(r"TC-[A-Z0-9]+-\d+")


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def collect_requirements(project: str) -> set[str]:
    text = read(os.path.join(project, "requirements", "requirements.md"))
    return set(REQ_RE.findall(text))


def collect_scenarios(project: str) -> tuple[dict[str, set[str]], list[str]]:
    """Return {SC id -> set(REQ it covers)} and a list of spec files scanned."""
    scenarios: dict[str, set[str]] = {}
    files = sorted(glob.glob(os.path.join(project, "specs", "*.md")))
    for f in files:
        lines = read(f).splitlines()
        current: str | None = None
        for line in lines:
            heading = re.match(r"^#{1,6}\s+(SC-\d+)", line.strip())
            if heading:
                current = heading.group(1)
                scenarios.setdefault(current, set())
                continue
            if current and "covers" in line.lower():
                scenarios[current].update(REQ_RE.findall(line))
    return scenarios, files


def collect_testcases(project: str) -> tuple[set[str], set[str]]:
    """Return (set of TC ids, set of SC ids referenced by any TC)."""
    text = read(os.path.join(project, "test-cases", "test-cases.md"))
    return set(TC_RE.findall(text)), set(SC_RE.findall(text))


def main() -> None:
    ap = argparse.ArgumentParser(description="REQ -> SC -> TC coverage check")
    ap.add_argument("project", help="path to projects/<slug>")
    ap.add_argument("--warn", action="store_true", help="always exit 0 (informational)")
    args = ap.parse_args()

    project = args.project.rstrip("/")
    if not os.path.isdir(project):
        sys.exit(f"Not a directory: {project}")

    reqs = collect_requirements(project)
    scenarios, spec_files = collect_scenarios(project)
    tc_ids, sc_referenced = collect_testcases(project)

    covered_reqs: set[str] = set()
    for covers in scenarios.values():
        covered_reqs |= covers

    sc_defined = set(scenarios.keys())

    req_without_sc = sorted(reqs - covered_reqs)
    sc_without_tc = sorted(sc_defined - sc_referenced)
    unknown_reqs = sorted(covered_reqs - reqs)
    unknown_scs = sorted(sc_referenced - sc_defined)

    slug = os.path.basename(project)
    print(f"Coverage check — {slug}")
    print(f"  requirements: {len(reqs)} REQ"
          f"  ·  scenarios: {len(sc_defined)} SC ({len(spec_files)} spec file(s))"
          f"  ·  test cases: {len(tc_ids)} TC")
    print("")

    def report(label: str, items: list[str]) -> None:
        if items:
            print(f"  ✗ {label}: {', '.join(items)}")

    gaps = bool(req_without_sc or sc_without_tc or unknown_reqs or unknown_scs)

    if not gaps:
        print("  ✓ Full chain intact: every REQ has a scenario, every scenario has a test.")
    else:
        report("REQ with no scenario (requirements gap)", req_without_sc)
        report("SC with no test case (coverage gap)", sc_without_tc)
        report("SC covers unknown REQ (typo/stale)", unknown_reqs)
        report("TC references unknown SC (typo/stale)", unknown_scs)

    print("")
    if reqs:
        pct = round(100 * len(reqs & covered_reqs) / len(reqs))
        print(f"  Requirement→scenario coverage: {pct}%")

    if gaps and not args.warn:
        sys.exit(1)


if __name__ == "__main__":
    main()
