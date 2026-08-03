/**
 * Cursor sessionStart — inject pending QA_WAKE_EXECUTE contract.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import {
  QA_PENDING_EXECUTE_PATH,
  type QaPendingExecuteState,
} from "../lib/qaPendingExecute.ts";

function readPending(root: string): QaPendingExecuteState | null {
  const path = join(root, QA_PENDING_EXECUTE_PATH);
  if (!existsSync(path)) return null;
  try {
    const state = JSON.parse(readFileSync(path, "utf8")) as QaPendingExecuteState;
    return state.consumed ? null : state;
  } catch {
    return null;
  }
}

function main() {
  const pending = readPending(process.cwd());
  if (!pending) {
    console.log("{}");
    return;
  }
  console.log(
    JSON.stringify({
      additional_context:
        `QA FACTORY EXECUTION PENDING: ${pending.executePrompt} ` +
        `Do NOT reply with status-only summaries while this file exists.`,
    }),
  );
}

main();
