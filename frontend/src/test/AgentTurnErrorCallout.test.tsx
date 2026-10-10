import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AgentRunStopReason } from "../api/contracts";
import { AgentTurnErrorCallout } from "../features/agent/components/AgentTurnErrorCallout";
import type { AgentConversationTurn } from "../features/agent/lib/agentWorkbenchModel";

function buildFailedTurn(stopReason: AgentRunStopReason): AgentConversationTurn {
  return {
    id: "turn-stop-reason",
    question: "请解释组合久期",
    agentRun: {
      run_id: "agent_run:stop_reason",
      status: "failed",
      provider: "hermes",
      model: "default",
      transport: "bridge",
      toolsets: "default",
      stop_reason: stopReason,
    },
    result: null,
    error: {
      kind: "request",
      message: "Hermes 托管任务失败，请稍后重试。",
    },
    activeSuggestedActionPayload: null,
  };
}

describe("AgentTurnErrorCallout stop_reason", () => {
  it("shows provider failure copy when stop_reason is provider_error", () => {
    render(
      <AgentTurnErrorCallout
        turn={buildFailedTurn("provider_error")}
        loading={false}
        canRetry={false}
        onEditQuestion={() => undefined}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("provider 执行失败")).toBeInTheDocument();
    expect(screen.getByText("Hermes 托管任务失败，请稍后重试。")).toBeInTheDocument();
  });

  it("shows unconfirmed cancel copy when stop_reason is cancel_requested_provider_stop_unconfirmed", () => {
    render(
      <AgentTurnErrorCallout
        turn={buildFailedTurn("cancel_requested_provider_stop_unconfirmed")}
        loading={false}
        canRetry={false}
        onEditQuestion={() => undefined}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("已请求取消，provider 停止未确认")).toBeInTheDocument();
  });

  it("does not show stop-reason copy when stop_reason is completed", () => {
    render(
      <AgentTurnErrorCallout
        turn={buildFailedTurn("completed")}
        loading={false}
        canRetry={false}
        onEditQuestion={() => undefined}
        onRetry={() => undefined}
      />,
    );

    expect(screen.queryByText("provider 执行失败")).not.toBeInTheDocument();
    expect(screen.queryByText("已请求取消，provider 停止未确认")).not.toBeInTheDocument();
  });
});
