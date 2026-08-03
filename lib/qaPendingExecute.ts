/** Argus pending-execute latch — written on Hephaestus handoff kick. */

export const QA_WAKE_EXECUTE_SENTINEL = "QA_WAKE_EXECUTE" as const;

export const QA_PENDING_EXECUTE_PATH = ".cursor/qa-pending-execute.json";

export type QaPendingExecuteState = {
  slug: string;
  oldest: string;
  keys: string[];
  count: number;
  issuedAt: string;
  consumed: boolean;
  /** Why this wake was issued (handoff | manual | loop). */
  source: "handoff" | "manual" | "loop";
  executePrompt: string;
};

export function buildQaPendingExecuteState(input: {
  slug: string;
  ticketKey: string;
  keys?: string[];
  source?: QaPendingExecuteState["source"];
}): QaPendingExecuteState {
  const keys = input.keys?.length ? input.keys : [input.ticketKey];
  const oldest = keys[0]!;
  return {
    slug: input.slug,
    oldest,
    keys,
    count: keys.length,
    issuedAt: new Date().toISOString(),
    consumed: false,
    source: input.source ?? "handoff",
    executePrompt: formatQaWakeExecutePrompt({
      slug: input.slug,
      oldest,
      keys,
    }),
  };
}

export function formatQaWakeExecutePrompt(input: {
  slug: string;
  oldest: string;
  keys: string[];
}): string {
  return (
    `${QA_WAKE_EXECUTE_SENTINEL}: Drain validate-testing for ${input.slug} NOW. ` +
    `Oldest ${input.oldest}` +
    (input.keys.length > 1 ? ` (${input.keys.length} keys)` : "") +
    `. cd qa-agent → eval "$(bash scripts/qa_scope.sh ${input.slug} --log --shell)" → ` +
    `handoff+OpenSpec+TC+STG evidence → qa-verdict-review → close or QA RETURN → ` +
    `drain until backlog_drained. Forbidden: notify-only / status-only.`
  );
}

export function formatQaWakeExecuteLine(state: QaPendingExecuteState): string {
  return `${QA_WAKE_EXECUTE_SENTINEL} ${JSON.stringify({
    executeNow: true,
    slug: state.slug,
    oldest: state.oldest,
    keys: state.keys,
    count: state.count,
    source: state.source,
    prompt: state.executePrompt,
  })}`;
}

export function consumeQaPendingExecuteState(
  state: QaPendingExecuteState,
): QaPendingExecuteState {
  return { ...state, consumed: true };
}

export function shouldForceQaDrainFollowup(input: {
  pending: QaPendingExecuteState | null;
  loopCount: number;
  maxFollowups?: number;
}): { force: true; message: string } | { force: false } {
  const max = input.maxFollowups ?? 5;
  if (!input.pending || input.pending.consumed || input.pending.count <= 0) {
    return { force: false };
  }
  if (input.loopCount >= max) return { force: false };
  return {
    force: true,
    message:
      `${input.pending.executePrompt} ` +
      `You ended the turn without draining ${input.pending.oldest}. ` +
      `Begin Argus qa-loop immediately — no status summary.`,
  };
}
