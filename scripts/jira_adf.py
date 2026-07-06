"""Convert a subset of Markdown into Jira Atlassian Document Format (ADF).

Used by create_jira_issue.py so ticket descriptions render with headings, lists,
bold/italic/code, links, horizontal rules, and fenced code blocks (e.g. Gherkin).
"""
from __future__ import annotations

import re
from typing import Any

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_UL_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^(\s*)\d+\.\s+(.*)$")
_FENCE_RE = re.compile(r"^```(\w*)$")
_HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")


def _text_node(text: str, marks: list[dict[str, str]] | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def _parse_inline(text: str) -> list[dict[str, Any]]:
    """Parse inline markdown: **bold**, *italic*, `code`, [label](url)."""
    if not text:
        return [_text_node("")]

    pattern = re.compile(
        r"(\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_|`[^`]+`|\[[^\]]+\]\([^)]+\))"
    )
    parts = pattern.split(text)
    nodes: list[dict[str, Any]] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            nodes.append(_text_node(part[2:-2], [{"type": "strong"}]))
        elif part.startswith("*") and part.endswith("*"):
            nodes.append(_text_node(part[1:-1], [{"type": "em"}]))
        elif part.startswith("_") and part.endswith("_"):
            nodes.append(_text_node(part[1:-1], [{"type": "em"}]))
        elif part.startswith("`") and part.endswith("`"):
            nodes.append(_text_node(part[1:-1], [{"type": "code"}]))
        elif part.startswith("[") and "](" in part:
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
            if m:
                nodes.append(
                    {
                        "type": "text",
                        "text": m.group(1),
                        "marks": [{"type": "link", "attrs": {"href": m.group(2)}}],
                    }
                )
            else:
                nodes.append(_text_node(part))
        else:
            nodes.append(_text_node(part))

    return nodes or [_text_node("")]


def _paragraph(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": _parse_inline(text)}


def _heading(level: int, text: str) -> dict[str, Any]:
    level = max(1, min(6, level))
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": _parse_inline(text),
    }


def _list_item(text: str) -> dict[str, Any]:
    return {"type": "listItem", "content": [_paragraph(text)]}


def _bullet_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [_list_item(item) for item in items],
    }


def _ordered_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "orderedList",
        "attrs": {"order": 1},
        "content": [_list_item(item) for item in items],
    }


def _code_block(body: str, language: str = "") -> dict[str, Any]:
    attrs: dict[str, str] = {}
    if language:
        attrs["language"] = language
    node: dict[str, Any] = {"type": "codeBlock", "content": [_text_node(body.rstrip("\n"))]}
    if attrs:
        node["attrs"] = attrs
    return node


def markdown_to_adf(text: str) -> dict[str, Any]:
    """Convert markdown text to a Jira ADF document."""
    content: list[dict[str, Any]] = []
    lines = text.splitlines()
    i = 0
    ul_buffer: list[str] = []
    ol_buffer: list[str] = []

    def flush_lists() -> None:
        nonlocal ul_buffer, ol_buffer
        if ul_buffer:
            content.append(_bullet_list(ul_buffer))
            ul_buffer = []
        if ol_buffer:
            content.append(_ordered_list(ol_buffer))
            ol_buffer = []

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        if line.strip() == "":
            flush_lists()
            i += 1
            continue

        fence = _FENCE_RE.match(line.strip())
        if fence:
            flush_lists()
            lang = fence.group(1) or ""
            i += 1
            body_lines: list[str] = []
            while i < len(lines) and not _FENCE_RE.match(lines[i].strip()):
                body_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # closing fence
            content.append(_code_block("\n".join(body_lines), lang))
            continue

        if _HR_RE.match(line.strip()):
            flush_lists()
            content.append({"type": "rule"})
            i += 1
            continue

        hm = _HEADING_RE.match(line)
        if hm:
            flush_lists()
            content.append(_heading(len(hm.group(1)), hm.group(2).strip()))
            i += 1
            continue

        ulm = _UL_RE.match(line)
        if ulm:
            if ol_buffer:
                content.append(_ordered_list(ol_buffer))
                ol_buffer = []
            ul_buffer.append(ulm.group(2).strip())
            i += 1
            continue

        olm = _OL_RE.match(line)
        if olm:
            if ul_buffer:
                content.append(_bullet_list(ul_buffer))
                ul_buffer = []
            ol_buffer.append(olm.group(2).strip())
            i += 1
            continue

        if line.startswith("> "):
            flush_lists()
            content.append(_paragraph(line[2:].strip()))
            i += 1
            continue

        flush_lists()
        content.append(_paragraph(line.strip()))
        i += 1

    flush_lists()

    if not content:
        content = [_paragraph("(no description)")]

    return {"type": "doc", "version": 1, "content": content}


def adf_from_text(text: str, *, markdown: bool = True) -> dict[str, Any]:
    """Public entry: markdown when True (default), plain lines otherwise."""
    if markdown:
        return markdown_to_adf(text)
    content = []
    for line in text.splitlines():
        line = line.rstrip()
        if line.strip() == "":
            continue
        content.append(_paragraph(line))
    if not content:
        content = [_paragraph("(no description)")]
    return {"type": "doc", "version": 1, "content": content}
