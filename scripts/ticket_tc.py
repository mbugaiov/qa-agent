#!/usr/bin/env python3
"""Persist or link a Jira scope ticket to a regression TC under test-cases/.

Usage:
    python3 scripts/ticket_tc.py --project projects/<slug> --ticket RQ-1 --title "…"
    python3 scripts/ticket_tc.py --project projects/<slug> --ticket RQ-1 --link TC-RQ-1
    python3 scripts/ticket_tc.py --project projects/<slug> --ticket RQ-1 --title "…" --log

Design source: OpenSpec + handoff (agent fills --title, --steps-file, --scenario, --req).
Creates test-cases/TC-<KEY>.md on first sight; idempotent if Jira key already mapped.
Updates project-memory.md ## Regression suite table. With --log, appends tc_linked to factory ledger.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JIRA_LINE = re.compile(r"^\s*-\s*\*\*Jira:\*\*\s*(\S+)", re.MULTILINE | re.IGNORECASE)
REGRESSION_SECTION = "## Regression suite (ticket → TC index)"
TABLE_RULER = "|------|-----|------|------------|"


def slug_from_project(project: str) -> str:
    return Path(project.rstrip("/")).name


def test_cases_dir(project: Path) -> Path:
    return project / "test-cases"


def find_tc_for_ticket(project: Path, ticket: str) -> Path | None:
    tc_dir = test_cases_dir(project)
    if not tc_dir.is_dir():
        return None
    for path in sorted(tc_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in JIRA_LINE.finditer(text):
            if m.group(1).upper() == ticket.upper():
                return path
    return None


def ticket_has_jira_line(text: str, ticket: str) -> bool:
    for m in JIRA_LINE.finditer(text):
        if m.group(1).upper() == ticket.upper():
            return True
    return False


def ensure_jira_line(text: str, ticket: str) -> str:
    """Ensure `- **Jira:** <ticket>` is present; leave other Jira keys intact."""
    if ticket_has_jira_line(text, ticket):
        return text
    line = f"- **Jira:** {ticket}"
    if "## Expected" in text:
        return text.replace("## Expected", f"{line}\n\n## Expected", 1)
    return text.rstrip() + f"\n{line}\n"


def default_tc_id(ticket: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9-]+", "-", ticket).strip("-")
    return f"TC-{safe}"


def default_tc_path(project: Path, ticket: str) -> Path:
    return test_cases_dir(project) / f"{default_tc_id(ticket)}.md"


def load_steps(steps_file: str | None) -> list[str]:
    if not steps_file:
        return [
            "1. (from OpenSpec + handoff) Preconditions met.",
            "2. Execute primary user flow for this ticket.",
            "3. Verify outcome against canonical source (detail / API / audit).",
        ]
    lines: list[str] = []
    for raw in Path(steps_file).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^\d+\.", line):
            lines.append(line)
        elif line.startswith("- "):
            lines.append(line[2:])
        else:
            lines.append(line)
    return lines or ["1. See steps file — fill retest plan."]


def render_tc(
    tc_id: str,
    ticket: str,
    title: str,
    scenario: str,
    req: str,
    steps: list[str],
) -> str:
    step_block = "\n".join(f"  {i + 1}. {s.lstrip('0123456789. ')}" for i, s in enumerate(steps))
    return f"""# {tc_id} — {title}

- **Type**: Acceptance
- **Priority**: P1
- **Regression**: yes
- **Jira:** {ticket}
- **Scenario**: {scenario}
- **REQ**: {req}

## Steps
{step_block}

## Expected
Behaviour matches governing OpenSpec scenario (THEN clause) on live STG; two-pass execution required.
"""


def _regression_section_body(text: str) -> str:
    """Return the body of the Regression suite section (until next ## heading)."""
    if REGRESSION_SECTION not in text:
        return ""
    return text.split(REGRESSION_SECTION, 1)[1].split("##", 1)[0]


def _ticket_indexed(section_body: str, ticket: str) -> bool:
    """True when ticket is an exact Jira-column cell (not a substring of a longer key)."""
    pat = re.compile(
        rf"^\|\s*{re.escape(ticket)}\s*\|",
        re.MULTILINE | re.IGNORECASE,
    )
    return bool(pat.search(section_body))


def upsert_regression_index(project: Path, ticket: str, tc_id: str, rel_path: str) -> None:
    memory = project / "project-memory.md"
    if not memory.is_file():
        return
    text = memory.read_text(encoding="utf-8")
    row = f"| {ticket} | {tc_id} | `{rel_path}` | yes |"
    if REGRESSION_SECTION not in text:
        block = (
            f"\n{REGRESSION_SECTION}\n"
            "Persisted when a ticket first enters loop scope (`ticket_tc.sh`). "
            "Included in `regression` run scope.\n\n"
            "| Jira | TC | File | Regression |\n"
            f"{TABLE_RULER}\n"
            f"{row}\n"
        )
        # Match template order: after Coverage ledger, before Security ledger.
        after = "## Security ledger"
        if after in text:
            text = text.replace(after, block.lstrip("\n") + "\n" + after, 1)
        elif "## Coverage ledger" in text:
            cov_idx = text.find("## Coverage ledger")
            rest = text[cov_idx + len("## Coverage ledger") :]
            next_h = re.search(r"\n## ", rest)
            if next_h:
                insert_at = cov_idx + len("## Coverage ledger") + next_h.start()
                text = text[:insert_at] + "\n" + block + text[insert_at:]
            else:
                text = text.rstrip() + block
        else:
            text = text.rstrip() + block
    else:
        section = _regression_section_body(text)
        if not _ticket_indexed(section, ticket):
            # Insert after the table ruler inside this section only.
            sec_start = text.find(REGRESSION_SECTION)
            sec_end = sec_start + len(REGRESSION_SECTION) + len(section)
            sec_full = text[sec_start:sec_end]
            ruler_at = sec_full.find(TABLE_RULER)
            if ruler_at != -1:
                abs_ruler = sec_start + ruler_at
                line_end = text.find("\n", abs_ruler)
                text = text[: line_end + 1] + row + "\n" + text[line_end + 1 :]
            else:
                text = text[:sec_end] + row + "\n" + text[sec_end:]
    memory.write_text(text, encoding="utf-8")


def log_tc_linked(slug: str, ticket: str, tc_id: str, path: Path, created: bool) -> None:
    script = ROOT / "scripts" / "factory_log.sh"
    rel = path.relative_to(ROOT / "projects" / slug)
    flag = "created=true" if created else "existing=true"
    subprocess.run(
        [
            str(script),
            slug,
            ticket,
            "tc_linked",
            f"tc_id={tc_id}",
            f"path={rel}",
            flag,
        ],
        check=False,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="projects/<slug>")
    ap.add_argument("--ticket", required=True, help="Jira key e.g. RQ-1")
    ap.add_argument("--title", help="TC title (required when creating)")
    ap.add_argument("--link", help="Existing TC id to link (add Jira line if missing)")
    ap.add_argument("--steps-file", help="Optional steps (numbered lines)")
    ap.add_argument("--scenario", default="SC-TBD", help="Governing SC-* id")
    ap.add_argument("--req", default="REQ-TBD", help="Governing REQ-* id")
    ap.add_argument("--log", action="store_true", help="Append tc_linked to factory ledger")
    a = ap.parse_args()

    project = Path(a.project)
    if not project.is_dir():
        print(f"ERROR: no project at {project}", file=sys.stderr)
        return 1

    ticket = a.ticket.strip().upper()
    slug = slug_from_project(a.project)

    existing = find_tc_for_ticket(project, ticket)
    if existing:
        rel = str(existing.relative_to(project))
        upsert_regression_index(project, ticket, existing.stem, rel)
        print(f"linked {ticket} -> {existing} (existing)")
        if a.log:
            log_tc_linked(slug, ticket, existing.stem, existing, created=False)
        return 0

    if a.link:
        tc_id = a.link.strip()
        path = test_cases_dir(project) / f"{tc_id}.md"
        if not path.is_file():
            path = (
                next(test_cases_dir(project).rglob(f"{tc_id}.md"), None)
                if test_cases_dir(project).is_dir()
                else None
            )
        if not path or not path.is_file():
            print(f"ERROR: TC file not found for --link {a.link}", file=sys.stderr)
            return 1
        text = ensure_jira_line(path.read_text(encoding="utf-8"), ticket)
        path.write_text(text, encoding="utf-8")
        rel = str(path.relative_to(project))
        upsert_regression_index(project, ticket, path.stem, rel)
        print(f"linked {ticket} -> {path}")
        if a.log:
            log_tc_linked(slug, ticket, path.stem, path, created=False)
        return 0

    if not a.title:
        print("ERROR: --title required when creating a new TC", file=sys.stderr)
        return 1

    tc_id = default_tc_id(ticket)
    path = default_tc_path(project, ticket)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        # Heal: file may exist without this ticket's Jira marker / index row.
        text = ensure_jira_line(path.read_text(encoding="utf-8"), ticket)
        path.write_text(text, encoding="utf-8")
        rel = str(path.relative_to(project))
        upsert_regression_index(project, ticket, tc_id, rel)
        print(f"linked {ticket} -> {path} (existing file)")
        if a.log:
            log_tc_linked(slug, ticket, tc_id, path, created=False)
        return 0

    steps = load_steps(a.steps_file)
    path.write_text(
        render_tc(tc_id, ticket, a.title.strip(), a.scenario.strip(), a.req.strip(), steps),
        encoding="utf-8",
    )
    rel = str(path.relative_to(project))
    upsert_regression_index(project, ticket, tc_id, rel)
    print(f"created {path}")
    if a.log:
        log_tc_linked(slug, ticket, tc_id, path, created=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
