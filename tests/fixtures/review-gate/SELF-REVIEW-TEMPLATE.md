# Self-review draft (optional — before push)

Copy **from the `---` line below** into your own file, edit placeholders, then validate:

```bash
bash scripts/check_review_gate.sh /path/to/your-draft.md
```

Dry-run historical gate fixtures (runs in `gate:mr`):

```bash
bash scripts/check_review_gate_fixtures.sh
```

**Tips:** List blockers under `## Blocking issues` with `file:line` citations. When
truly clean, you may replace the whole draft with exactly:
`LGTM - no blocking issues found.`

---

## Summary

Replace with 1–3 sentences describing this MR.

## Blocking issues

None.

## Suggestions

None.
