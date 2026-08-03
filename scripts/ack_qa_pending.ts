/**
 * Mark qa-pending-execute consumed after Argus starts drain (or ticket closed).
 * Usage: npx tsx scripts/ack_qa_pending.ts [--ticket KEY]
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  consumeQaPendingExecuteState,
  QA_PENDING_EXECUTE_PATH,
  type QaPendingExecuteState,
} from "../lib/qaPendingExecute.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

function arg(name: string): string {
  const i = process.argv.indexOf(name);
  return i >= 0 ? (process.argv[i + 1] ?? "") : "";
}

const path = join(ROOT, QA_PENDING_EXECUTE_PATH);
if (!existsSync(path)) {
  console.log("QA_PENDING_ACK_SKIP {\"reason\":\"no-pending\"}");
  process.exit(0);
}

const pending = JSON.parse(readFileSync(path, "utf8")) as QaPendingExecuteState;
const ticket = arg("--ticket");
if (ticket && pending.oldest !== ticket && !pending.keys.includes(ticket)) {
  console.log(
    `QA_PENDING_ACK_SKIP ${JSON.stringify({ reason: "ticket-mismatch", pending: pending.oldest, ticket })}`,
  );
  process.exit(0);
}

writeFileSync(
  path,
  JSON.stringify(consumeQaPendingExecuteState(pending), null, 2) + "\n",
  "utf8",
);
console.log(
  `QA_PENDING_ACK_OK ${JSON.stringify({ ticket: pending.oldest, slug: pending.slug })}`,
);
