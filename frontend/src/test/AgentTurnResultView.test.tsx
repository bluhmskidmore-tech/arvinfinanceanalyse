import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentTurnResultView } from "../features/agent/components/AgentTurnResultView";
import type { AgentConversationTurn } from "../features/agent/lib/agentWorkbenchModel";


describe("AgentTurnResultView", () => {
  it("falls back to result_meta evidence strength for stored results", () => {
    const turn: AgentConversationTurn = {
      id: "turn-provider-runtime",
      question: "ping",
      agentRun: null,
      result: {
        answer: "pong",
        cards: [],
        evidence: {
          tables_used: ["dexter_sidecar"],
          filters_applied: {},
          sql_executed: [],
          evidence_rows: 0,
          quality_flag: "warning",
        },
        result_meta: {
          result_kind: "agent.dexter",
          formal_use_allowed: false,
          evidence_strength: "provider_runtime",
        },
        next_drill: [],
        suggested_actions: [],
      },
      error: null,
      activeSuggestedActionPayload: null,
    };

    render(
      <AgentTurnResultView
        turn={turn}
        isLatestResultTurn
        isEmbedded={false}
        readOnly={false}
        loading={false}
        latestConversationTurnId={turn.id}
        copyFeedback={null}
        pendingSuggestedActionConfirmation={null}
        canRegenerate={false}
        onRegenerate={() => undefined}
        onCopyAnswer={() => undefined}
        onApplyNextDrill={() => undefined}
        onSuggestedAction={() => undefined}
        onFocusComposerFromFollowUp={() => undefined}
        onApplyFollowUpChip={() => undefined}
        onFocusComposerFromEmptyResult={() => undefined}
        onSideDrawerOpen={() => undefined}
      />,
    );

    expect(screen.getByText("外部模型运行证据")).toBeInTheDocument();
  });
});
