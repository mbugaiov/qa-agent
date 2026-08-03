/**
 * Cursor stop hook — force Argus drain when QA_WAKE_EXECUTE pending unconsumed.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import {
  QA_PENDING_EXECUTE_PATH,
  shouldForceQaDrainFollowup,
  type QaPendingExecuteState,
} from "../lib/qaPendingExecute.ts";

type StopHookInput = {
  status?: "completed" | "aborted" | "error";
  loop_count?: number;
};

function readStdin(): StopHookInput {
  try {
    const raw = readFileSync(0, "utf8");
    if (!raw.trim()) return { status: "completed", loop_count: 0 };
    return JSON.parse(raw) as StopHookInput;
  } catch {
    return { status: "completed", loop_count: 0 };
  }
}

function readPending(root: string): QaPendingExecuteState | null {
  const path = join(root, QA_PENDING_EXECUTE_PATH);
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, "utf8")) as QaPendingExecuteState;
  } catch {
    return null;
  }
}

function main() {
  const input = readStdin();
  if (input.status !== "completed") {
    console.log("{}");
    return;
  }
  const decision = shouldForceQaDrainFollowup({
    pending: readPending(process.cwd()),
    loopCount: input.loop_count ?? 0,
  });
  if (decision.force) {
    console.log(JSON.stringify({ followup_message: decision.message }));
  } else {
    console.log("{}");
  }
}

main();
