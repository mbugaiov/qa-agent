#!/usr/bin/env python3
"""Offline tests for jira_adf.markdown_to_adf."""
from __future__ import annotations

import json
import unittest

from jira_adf import markdown_to_adf


class TestMarkdownToAdf(unittest.TestCase):
    def test_heading_and_paragraph(self) -> None:
        doc = markdown_to_adf("## Business context\n\nSome **bold** text.\n")
        types = [n["type"] for n in doc["content"]]
        self.assertEqual(types, ["heading", "paragraph"])
        self.assertEqual(doc["content"][0]["attrs"]["level"], 2)
        marks = doc["content"][1]["content"][1].get("marks", [])
        self.assertEqual(marks[0]["type"], "strong")

    def test_bullet_list(self) -> None:
        doc = markdown_to_adf("- one\n- two\n")
        self.assertEqual(doc["content"][0]["type"], "bulletList")
        self.assertEqual(len(doc["content"][0]["content"]), 2)

    def test_ordered_list(self) -> None:
        doc = markdown_to_adf("1. first\n2. second\n")
        self.assertEqual(doc["content"][0]["type"], "orderedList")

    def test_gherkin_code_block(self) -> None:
        md = "```gherkin\nGiven a user\nWhen they log in\nThen they see home\n```\n"
        doc = markdown_to_adf(md)
        block = doc["content"][0]
        self.assertEqual(block["type"], "codeBlock")
        self.assertEqual(block["attrs"]["language"], "gherkin")
        self.assertIn("Given a user", block["content"][0]["text"])

    def test_horizontal_rule(self) -> None:
        doc = markdown_to_adf("## A\n\n---\n\n## B\n")
        types = [n["type"] for n in doc["content"]]
        self.assertIn("rule", types)

    def test_link(self) -> None:
        doc = markdown_to_adf("See [epic](https://test-co.atlassian.net/browse/TST-1).\n")
        node = doc["content"][0]["content"][1]
        self.assertEqual(node["marks"][0]["type"], "link")
        self.assertIn("TST-1", node["marks"][0]["attrs"]["href"])

    def test_full_task_shape(self) -> None:
        md = """# Business context

Factory needs blocking review.

# Requirement

**As a** dev agent
**I need** merge blocked on review
**So that** defects do not ship

## Scenario — gate

```gherkin
Given a PR with blocking review
When pipeline runs
Then merge is blocked
```

# Acceptance criteria

- Pipeline fails on blockers
"""
        doc = markdown_to_adf(md)
        types = [n["type"] for n in doc["content"]]
        self.assertIn("heading", types)
        self.assertIn("codeBlock", types)
        self.assertIn("bulletList", types)
        # sanity: serializable for Jira API
        json.dumps(doc)


if __name__ == "__main__":
    unittest.main()
