# Automation (Phase 2 — optional)

Manual-first: only generate automated tests **after** the cases have been verified by hand in
the live browser. Each generated spec mirrors a verified `TC-*` id so the suite stays traceable
to requirements.

## Setup

```bash
cd automation
npm init -y
npm install -D @playwright/test
npx playwright install
```

## Layout

This folder is the **shared guide + example config**. Actual specs live per project
under `projects/<slug>/automation/specs/`. Copy the example config into the project:

```
automation/                       (shared)
  README.md                       this guide
  playwright.config.example.js    copy → projects/<slug>/automation/playwright.config.js

projects/<slug>/automation/
  playwright.config.js            baseURL = the project's URL
  specs/                          generated specs, one file per feature area
  helpers/                        auth.js (gitignored — credentials), fixtures
```

## Generating specs from verified cases

Ask the agent: "Generate Playwright specs from the verified cases in `test-cases/<target>.md`."
It will, per the `salesforce-fsl-testing` / `release-testing` patterns:

- one spec file per feature area, one `test()` per case
- name each test with its `TC-*` id and reference the `REQ-*` in a comment
- use `test.describe.serial` for multi-step business flows (create → read → update → delete)
- capture a screenshot on failure for evidence
- run the final retest pass with `--workers=1` to avoid rate-limit cascades

## Run

```bash
npx playwright test                 # full run
npx playwright test --workers=1     # clean retest pass
npx playwright show-report
```

## CLI-first browser driving (integrated from openai/skills)

For ad-hoc browser automation **without** writing test files (quick repro,
data extraction, debugging a flow), use the Playwright CLI skill from
`openai/skills` instead of `@playwright/test`:

```bash
# Prerequisite: npx must be available (Node.js/npm)
command -v npx >/dev/null 2>&1 || echo "install Node.js/npm first"

# Drive a real browser from the terminal
npx --package @playwright/cli playwright-cli open https://staging.example.com --headed
npx --package @playwright/cli playwright-cli snapshot       # get stable element refs (e1, e2, …)
npx --package @playwright/cli playwright-cli fill e1 "user@example.com"
npx --package @playwright/cli playwright-cli fill e2 "password123"
npx --package @playwright/cli playwright-cli click e3
npx --package @playwright/cli playwright-cli screenshot
```

Core loop: **open → snapshot → interact by ref → re-snapshot after navigation/DOM change → capture artifacts.**
Re-snapshot whenever a ref goes stale. Put artifacts in `../runs/<date>/screenshots/`.

> Source: `openai/skills` `.curated/playwright` and `.curated/playwright-interactive`.
> Note: this is **CLI automation**, complementary to — not a replacement for —
> the live `cursor-ide-browser` MCP used for the *manual* two-pass execution in
> `AGENTS.md`. Use the MCP for human-visible manual testing; use the CLI here for
> fast scripted automation once cases are verified.
