import { describe, expect, it } from "vitest";
import {
  buildQaPendingExecuteState,
  formatQaWakeExecuteLine,
  shouldForceQaDrainFollowup,
  QA_WAKE_EXECUTE_SENTINEL,
} from "../lib/qaPendingExecute.ts";

describe("qaPendingExecute", () => {
  it("builds unconsumed handoff pending", () => {
    const s = buildQaPendingExecuteState({
      slug: "pantheon",
      ticketKey: "pantheon#66",
    });
    expect(s.oldest).toBe("pantheon#66");
    expect(s.consumed).toBe(false);
    expect(s.source).toBe("handoff");
    expect(formatQaWakeExecuteLine(s)).toContain(QA_WAKE_EXECUTE_SENTINEL);
  });

  it("forces stop-hook followup while pending", () => {
    const pending = buildQaPendingExecuteState({
      slug: "pantheon",
      ticketKey: "pantheon#66",
    });
    const d = shouldForceQaDrainFollowup({ pending, loopCount: 0 });
    expect(d.force).toBe(true);
    expect(
      shouldForceQaDrainFollowup({
        pending: { ...pending, consumed: true },
        loopCount: 0,
      }).force,
    ).toBe(false);
  });
});
