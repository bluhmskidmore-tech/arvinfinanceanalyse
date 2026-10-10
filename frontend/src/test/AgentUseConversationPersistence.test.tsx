import { act, renderHook } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { useConversationPersistence } from "../features/agent/hooks/useConversationPersistence";
import {
  AGENT_COMPOSER_DRAFT_KEY,
  AGENT_QUEUED_QUERIES_KEY,
  getScopedAgentWorkbenchStorageKey,
} from "../features/agent/lib/agentWorkbenchStorage";

function StrictWrapper({ children }: { children: ReactNode }) {
  return <StrictMode>{children}</StrictMode>;
}

describe("useConversationPersistence", () => {
  it("restores scoped queued queries and composer draft under StrictMode", () => {
    window.localStorage.setItem(
      getScopedAgentWorkbenchStorageKey(AGENT_COMPOSER_DRAFT_KEY),
      "draft question",
    );
    window.localStorage.setItem(
      getScopedAgentWorkbenchStorageKey(AGENT_QUEUED_QUERIES_KEY),
      JSON.stringify(["queued question"]),
    );

    const { result } = renderHook(
      () =>
        useConversationPersistence({
          shouldPersistConversation: true,
          defaultQuestion: "",
          variant: "workbench",
        }),
      { wrapper: StrictWrapper },
    );

    expect(result.current.query).toBe("draft question");
    expect(result.current.queuedQueries).toEqual(["queued question"]);
  });

  it("flushes the latest composer draft on unmount and clears the timer", () => {
    vi.useFakeTimers();
    const clearTimeoutSpy = vi.spyOn(window, "clearTimeout");
    const { result, unmount } = renderHook(() =>
      useConversationPersistence({
        shouldPersistConversation: true,
        defaultQuestion: "",
        variant: "workbench",
      }),
    );

    act(() => {
      result.current.writeComposerDraft("draft before unmount");
    });
    unmount();

    expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(AGENT_COMPOSER_DRAFT_KEY))).toBe(
      "draft before unmount",
    );
    expect(clearTimeoutSpy).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("does not throw when turn persistence hits localStorage quota", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota exceeded", "QuotaExceededError");
    });
    const { result } = renderHook(() =>
      useConversationPersistence({
        shouldPersistConversation: true,
        defaultQuestion: "",
        variant: "workbench",
      }),
    );

    expect(() => {
      act(() => {
        result.current.persistConversationTurnsNow([]);
      });
    }).not.toThrow();
    expect(warnSpy).toHaveBeenCalled();
  });

  it("keeps embedded copilots out of persisted workbench storage", () => {
    const { result } = renderHook(() =>
      useConversationPersistence({
        shouldPersistConversation: false,
        defaultQuestion: "",
        variant: "embedded",
      }),
    );

    act(() => {
      result.current.writeComposerDraft("embedded draft");
      result.current.setQueuedQueries(["embedded queued"]);
    });

    expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(AGENT_COMPOSER_DRAFT_KEY))).toBeNull();
    expect(window.localStorage.getItem(getScopedAgentWorkbenchStorageKey(AGENT_QUEUED_QUERIES_KEY))).toBeNull();
  });
});
