---
name: usage-accounting
description: >-
  Collect and report agent token spend using four-tier methodology: exact billing
  (optional), estimated from local logs (primary without Admin API), countable
  invocations, and activity proxies. Use when the user asks about tokens per day,
  cost, spend, billing, usage metrics, or factory economics.
---

# Usage accounting — methodology & collection

## Four tiers (never mix without labels)

| Tier | What | Source | Report as |
|------|------|--------|-----------|
| **A — Exact** | `input_tokens`, `output_tokens`, `charged_cents` | Cursor Admin API or dashboard | **Real tokens / USD** |
| **D — Estimated** | `est_tokens_*`, `est_usd_cents` | Local logs + factory + CI | **ESTIMATED tokens / ~USD** — always label |
| **B — Countable** | `qa_ticks`, `ci_review_runs`, `ledger_events` | Factory JSONL + Bitbucket | **Invocations** — not tokens |
| **C — Proxy** | `ide_user_turns`, `transcript_bytes` | Agent transcripts | **Activity index** — not tokens |

**Hard rules:**
- Only Tier **A** may be reported as exact billing.
- Tier **D** is the **primary spend signal** when A is unavailable (no Admin key, no cookies).
- Tier **B/C** must never be called "tokens".

## Collect (default)

```bash
cd qa-agent
python3 scripts/collect_usage.py --slug <slug> --days 14
```

Offline (ledger + traces + transcripts; skips Bitbucket + Cursor API):

```bash
python3 scripts/collect_usage.py --slug <slug> --days 14 --offline
```

Output: `projects/<slug>/factory/usage.json`

## Tier D — how we count spend without cookies

**Sources (all local / durable):**

1. **`~/Library/Application Support/Cursor/logs/**/cursor.requestTraces.log`**
   - Count `span_completed name="agent.request"` per day
   - Sum `durationMs` → `agent_active_ms`
   - `est_tokens_ide = agent_active_ms × USAGE_TOKENS_PER_MS` (default **0.15** ≈ 150 tok/s)

2. **Factory ledger** — `qa_ticks` per day
   - `est_tokens_qa = qa_ticks × USAGE_TOKENS_PER_QA_TICK` (default **200,000**)

3. **Bitbucket PR pipelines** — `ci_review_runs` per day
   - `est_tokens_ci = ci_review_runs × USAGE_TOKENS_PER_CI` (default **120,000**)

4. **USD proxy:** `est_usd = est_tokens_total / 1e6 × USAGE_USD_PER_MTOK` (default **$3/Mtok**)

**Calibrate** in `projects/<slug>/.secrets/cursor.env`:

```bash
USAGE_TOKENS_PER_MS=0.15
USAGE_TOKENS_PER_QA_TICK=200000
USAGE_TOKENS_PER_CI=120000
USAGE_USD_PER_MTOK=3.0
```

Compare one known billing day from Cursor dashboard (manual) and adjust coefficients.

## Tier A setup (optional — only if you have billing scope)

`CURSOR_API_KEY` with Admin `usage:*` scope, or Enterprise team. The CI key (`bitbucket-ci`, `crsr_…`) runs `cursor-agent` but **cannot** fetch usage — do not expect Tier A from it.

`CURSOR_SESSION_TOKEN` (browser cookie) also works but expires quickly — **not recommended**; use Tier D instead.

## Per-metric definitions

### B — `qa_ticks`

- Lines where `event=tick_end` OR `ticket=tick_end` in `factory/runs/*.jsonl`
- One completed QA loop iteration (5m cadence when loop armed)

### B — `ci_review_runs`

- PR pipelines (`target.ref_name != main`) per day
- Each runs `cursor-agent` once (parallel with tests)

### C — IDE proxy

- Transcript user/assistant turns — trend only, not spend

## Report template (A unavailable — use D)

```markdown
## Agent usage — {start} → {end}

**Tier D (ESTIMATED):** ~{est_tokens_total} tokens · ~${est_usd_dollars}
  · {agent_requests} IDE requests · {agent_active_hours}h agent time
**Tier B:** {qa_ticks} QA ticks · {ci_review_runs} CI reviews
**Tier C:** {ide_user_turns} IDE user turns (proxy)

| date | QA ticks | CI | IDE req | est Mtok | ~USD |
|------|----------|----|---------|----------|------|
...
```

## Presentation / scorecard

- Label Tier D as **"estimated"** on slides
- Cross-check factory: `collect_metrics.py` (ship) vs `collect_usage.py` (spend)
- Regenerate both before deck updates

## References

- Script: `scripts/collect_usage.py` (`methodology_version`)
- Calibration: `projects/_template/.secrets/cursor.env.example`
- Token-efficiency ops: skill `token-efficient-ops` (minimize spend, not measure it)
