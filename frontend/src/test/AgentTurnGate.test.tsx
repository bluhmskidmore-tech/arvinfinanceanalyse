import { renderHook } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useAgentTurnGate } from "../features/agent/hooks/agentTurnGate";

function StrictWrapper({ children }: { children: ReactNode }) {
  return <StrictMode>{children}</StrictMode>;
}

describe("useAgentTurnGate", () => {
  it("keeps only the newest turn current under StrictMode", () => {
    const { result } = renderHook(() => useAgentTurnGate(), { wrapper: StrictWrapper });

    const firstGate = result.current.beginAgentTurn();
    const secondGate = result.current.beginAgentTurn();

    expect(firstGate.isCurrent()).toBe(false);
    expect(secondGate.isCurrent()).toBe(true);
    expect(firstGate.signal.aborted).toBe(false);
  });

  it("invalidates and aborts the active turn", () => {
    const { result } = renderHook(() => useAgentTurnGate());

    const gate = result.current.beginAgentTurn();
    result.current.invalidateActiveAgentTurn();

    expect(gate.signal.aborted).toBe(true);
    expect(gate.isCurrent()).toBe(false);
  });

  it("aborts active waiting without making an old gate current again", () => {
    const { result } = renderHook(() => useAgentTurnGate());

    const firstGate = result.current.beginAgentTurn();
    const secondGate = result.current.beginAgentTurn();
    result.current.abortActiveAgentTurn();

    expect(firstGate.isCurrent()).toBe(false);
    expect(secondGate.signal.aborted).toBe(true);
    expect(secondGate.isCurrent()).toBe(false);
  });
});
