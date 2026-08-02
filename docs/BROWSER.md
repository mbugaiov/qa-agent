# Browser policy (Argus)

**Default: headless.** Do not open a visible browser window on the operator machine
for routine factory work.

## Prefer (cheapest → dearest)

1. **`playwright test` / CLI specs** — always headless (`--reporter=dot`)
2. **Playwright MCP / browser tools in headless mode** — when no spec exists yet
3. **Headed (visible) — opt-in only** — see below

`scripts/record_retest.cjs` launches Chromium **headless** by default (video via
`recordVideo`, no window required).

## Headed allowed only when

| Case | Why |
|------|-----|
| Human explicitly asks to watch | Operator debugging |
| FAIL is ambiguous after headless evidence | Need visual confirmation |
| Tooling cannot capture required evidence headless | Rare codec/GPU edge |

Log `BROWSER_HEADED: <reason>` in `run.md` when opting in.

## Still mandatory (headless or headed)

- Viewport screenshots / evidence attachments
- Two-pass execution semantics (real input vs fill) via MCP APIs — **does not require a visible window**
- E2E recording via `record_and_attach.sh` (headless Chromium + recordVideo)

## Forbidden

- Opening a side-panel / visible browser “so the human can follow along” by default
- Using headed MCP for every Validate/Testing retest tick
