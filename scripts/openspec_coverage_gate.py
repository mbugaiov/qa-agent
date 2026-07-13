#!/usr/bin/env python3
"""OpenSpec regression coverage gate for qa-agent projects.

Reads:
  projects/<slug>/requirements/openspec-requirements.md  -> in-scope REQ count
  projects/<slug>/runs/.../traceability-matrix.md        -> per-REQ status

Counts REQs with status containing Pass/✅ as covered.
Exit 0 if covered/in_scope >= --min (default 0.90), else 1.

Usage:
    python3 scripts/openspec_coverage_gate.py projects/<slug> [--min 0.90] [--matrix PATH]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQ_RE = re.compile(r"REQ-[A-Z]+-\d+")
PASS_MARKERS = ("✅", "pass", "covered")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def in_scope_reqs(project: Path) -> set[str]:
    text = read(project / "requirements" / "openspec-requirements.md")
    return set(REQ_RE.findall(text))


def matrix_coverage(matrix_path: Path) -> dict[str, str]:
    """Return {REQ-ID: status cell text} from traceability matrix rows."""
    text = read(matrix_path)
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 7:
            continue
        req = cells[0]
        if not REQ_RE.fullmatch(req):
            continue
        status = cells[6] if len(cells) > 6 else ""
        out[req] = status
    return out


def is_covered(status: str) -> bool:
    s = status.lower()
    if "⬜" in status or "gap" in s or "not run" in s:
        return False
    if "⚠" in status or "partial" in s or "known" in s:
        return False
    return any(m in s for m in PASS_MARKERS)


def find_latest_matrix(project: Path) -> Path | None:
    runs = project / "runs"
    if not runs.is_dir():
        return None
    candidates = sorted(runs.glob("*/traceability-matrix.md"))
    return candidates[-1] if candidates else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="projects/<slug>")
    ap.add_argument("--min", type=float, default=0.90, help="minimum fraction (0.90 = 90%%)")
    ap.add_argument(
        "--matrix",
        default="",
        help="path to traceability-matrix.md (default: latest full-regression run)",
    )
    args = ap.parse_args()

    project = Path(args.project.rstrip("/"))
    if not project.is_dir():
        print(f"ERROR: not a directory: {project}", file=sys.stderr)
        return 1

    matrix = Path(args.matrix) if args.matrix else find_latest_matrix(project)
    if matrix is None or not matrix.is_file():
        print(
            "ERROR: no traceability-matrix.md under runs/ (pass --matrix PATH)",
            file=sys.stderr,
        )
        return 1

    scope = in_scope_reqs(project)
    if not scope:
        print("ERROR: no REQs in openspec-requirements.md", file=sys.stderr)
        return 1

    matrix_map = matrix_coverage(matrix)
    covered = {r for r in scope if is_covered(matrix_map.get(r, ""))}
    missing = sorted(scope - covered)
    pct = len(covered) / len(scope)

    print(f"OpenSpec coverage gate — {project.name}")
    print(f"  Matrix: {matrix}")
    print(f"  In scope: {len(scope)} REQs")
    print(f"  Covered:  {len(covered)} REQs ({pct:.1%})")
    print(f"  Threshold: {args.min:.0%}")

    if missing and pct < args.min:
        print(f"\nUncovered ({len(missing)}):")
        for r in missing[:30]:
            print(f"  - {r}: {matrix_map.get(r, '(no row)')}")
        if len(missing) > 30:
            print(f"  ... and {len(missing) - 30} more")

    if pct >= args.min:
        print("\nGATE OPEN — coverage meets threshold")
        return 0

    print(f"\nGATE CLOSED — need {int(args.min * len(scope)) - len(covered)} more REQ(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
