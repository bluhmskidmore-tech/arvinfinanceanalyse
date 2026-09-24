import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentTurnResultView } from "../features/agent/components/AgentTurnResultView";
import type { AgentConversationTurn } from "../features/agent/lib/agentWorkbenchModel";

describe("AgentTurnResultView render isolation", () => {
  it("does not re-read unchanged static result data after an unrelated parent update", () => {
    let cardTitleReads = 0;
    let filterValueReads = 0;
    let traceIdReads = 0;
    const copyHandlerCalls: number[] = [];

    const card = {
      get title() {
        cardTitleReads += 1;
        return "Static result card";
      },
      type: "table",
      data: [{ metric: "duration", value: 4.2 }],
    };
    const filtersApplied = Object.defineProperty({}, "desk", {
      enumerable: true,
      get() {
        filterValueReads += 1;
        return "fixed-income";
      },
    }) as Record<string, unknown>;
    const resultMeta = {
      result_kind: "agent.test",
      formal_use_allowed: true,
      get trace_id() {
        traceIdReads += 1;
        return "trace-static";
      },
    };
    const turn: AgentConversationTurn = {
      id: "turn-static-result",
      question: "Show a static result",
      agentRun: null,
      result: {
        answer: "Static answer",
        cards: [card],
        evidence: {
          tables_used: ["fact_positions"],
          filters_applied: filtersApplied,
          sql_executed: [],
          evidence_rows: 1,
          quality_flag: "ok",
        },
        result_meta: resultMeta,
        next_drill: [],
        suggested_actions: [],
      },
      error: null,
      activeSuggestedActionPayload: null,
    };

    function Harness() {
      const [unrelatedCount, setUnrelatedCount] = useState(0);

      return (
        <>
          <button type="button" onClick={() => setUnrelatedCount((count) => count + 1)}>
            Unrelated update {unrelatedCount}
          </button>
          <AgentTurnResultView
            turn={turn}
            isLatestResultTurn
            isEmbedded={false}
            readOnly={false}
            loading={false}
            latestConversationTurnId={turn.id}
            copyFeedback={null}
            pendingSuggestedActionConfirmation={null}
            canRegenerate
            onRegenerate={() => undefined}
            onCopyAnswer={() => copyHandlerCalls.push(unrelatedCount)}
            onApplyNextDrill={() => undefined}
            onSuggestedAction={() => undefined}
            onFocusComposerFromFollowUp={() => undefined}
            onApplyFollowUpChip={() => undefined}
            onFocusComposerFromEmptyResult={() => undefined}
            onSideDrawerOpen={() => undefined}
          />
        </>
      );
    }

    render(<Harness />);

    const readsAfterInitialRender = {
      cardTitleReads,
      filterValueReads,
      traceIdReads,
    };
    expect(readsAfterInitialRender.cardTitleReads).toBeGreaterThan(0);
    expect(readsAfterInitialRender.filterValueReads).toBeGreaterThan(0);
    expect(readsAfterInitialRender.traceIdReads).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Unrelated update 0" }));

    expect({ cardTitleReads, filterValueReads, traceIdReads }).toEqual(readsAfterInitialRender);

    fireEvent.click(screen.getByRole("button", { name: "复制回答：Show a static result" }));
    expect(copyHandlerCalls).toEqual([1]);
  });
});
