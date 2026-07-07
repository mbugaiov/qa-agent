# <slug> — Playwright automation (phase 2)

Manual-first: only add specs **after** cases are verified by hand in the live browser.
Each spec mirrors a verified `TC-*` id for traceability to requirements.

See the shared guide: [`../../../automation/README.md`](../../../automation/README.md).

## Setup (once)

```bash
cd projects/<slug>/automation
npm install
npx playwright install chromium
```

## Run

From the **engine repo root** (where `scripts/` lives):

```bash
# STG (no local server)
scripts/run_automation.sh <slug> --stg

# Local app (sync + up + test + down when server.manage is true in project.yaml)
scripts/run_automation.sh <slug>

# Explicit URL (no server autostart)
scripts/run_automation.sh <slug> --url https://staging.example.com

# Skip server management even when server.manage is true
scripts/run_automation.sh <slug> --no-server
```

Credentials: `../.secrets/credentials.json` (gitignored; copy from `.secrets/credentials.json.example`).
