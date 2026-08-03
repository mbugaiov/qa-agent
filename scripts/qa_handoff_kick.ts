/**
 * Issue (or re-issue) a QA_WAKE_EXECUTE latch after Hephaestus handoff.
 *
 * Usage:
 *   npx tsx scripts/qa_handoff_kick.ts <slug> --ticket <KEY> [--source handoff|manual]
 *   npx tsx scripts/qa_handoff_kick.ts <slug> --ticket pantheon#66
 *
 * Writes .cursor/qa-pending-execute.json and prints QA_WAKE_EXECUTE line.
 * Exit 0 on success. Does not run the tick itself — Cursor agent / loop must execute.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildQaPendingExecuteState,
  formatQaWakeExecuteLine,
  QA_PENDING_EXECUTE_PATH,
  type QaPendingExecuteState,
} from "../lib/qaPendingExecute.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

function arg(name: string): string {
  const i = process.argv.indexOf(name);
  return i >= 0 ? (process.argv[i + 1] ?? "") : "";
}

const slug = process.argv[2] ?? "";
const ticket = arg("--ticket");
const sourceRaw = arg("--source") || "handoff";
const source =
  sourceRaw === "manual" || sourceRaw === "loop" ? sourceRaw : "handoff";

if (!slug || !ticket) {
  console.error(
    "Usage: qa_handoff_kick.ts <slug> --ticket <KEY> [--source handoff|manual|loop]",
  );
  process.exit(1);
}

const state: QaPendingExecuteState = buildQaPendingExecuteState({
  slug,
  ticketKey: ticket,
  source,
});

const path = join(ROOT, QA_PENDING_EXECUTE_PATH);
mkdirSync(dirname(path), { recursive: true });
writeFileSync(path, JSON.stringify(state, null, 2) + "\n", "utf8");

console.log(formatQaWakeExecuteLine(state));
console.log(
  `QA_PENDING_EXECUTE_WRITTEN {"slug":"${slug}","ticket":"${ticket}","path":"${QA_PENDING_EXECUTE_PATH}"}`,
);
