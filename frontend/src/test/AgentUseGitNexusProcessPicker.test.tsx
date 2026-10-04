import { act, renderHook, waitFor } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useGitNexusProcessPicker } from "../features/agent/hooks/useGitNexusProcessPicker";

function StrictWrapper({ children }: { children: ReactNode }) {
  return <StrictMode>{children}</StrictMode>;
}

describe("useGitNexusProcessPicker", () => {
  it("keeps the latest process load sequence responsible for clearing loading", () => {
    const { result } = renderHook(
      () =>
        useGitNexusProcessPicker({
          recentRepoPaths: ["F:\\MOSS-V3"],
          pinnedRepoPaths: [],
        }),
      { wrapper: StrictWrapper },
    );

    const firstSequence = result.current.beginProcessLoadSequence();
    const secondSequence = result.current.beginProcessLoadSequence();

    expect(result.current.isLatestProcessLoad(firstSequence)).toBe(false);
    expect(result.current.isLatestProcessLoad(secondSequence)).toBe(true);
  });

  it("rejects stale process state after repo path changes", () => {
    const { result } = renderHook(() =>
      useGitNexusProcessPicker({
        recentRepoPaths: ["F:\\MOSS-V3"],
        pinnedRepoPaths: [],
      }),
    );

    const requestVersion = result.current.beginProcessStateRequest();
    expect(result.current.canCommitProcessState(requestVersion, "F:\\MOSS-V3")).toBe(true);

    act(() => {
      result.current.setRepoPath("F:\\OTHER");
    });

    expect(result.current.canCommitProcessState(requestVersion, "F:\\MOSS-V3")).toBe(false);
  });

  it("derives filtered selection and pinned state", async () => {
    const { result } = renderHook(() =>
      useGitNexusProcessPicker({
        recentRepoPaths: ["F:\\MOSS-V3", "F:\\OLD"],
        pinnedRepoPaths: ["F:\\MOSS-V3"],
      }),
    );

    act(() => {
      result.current.setAvailableProcesses(["DailyUpdate", "AuditFlow"]);
      result.current.setProcessSearch("audit");
    });

    await waitFor(() => expect(result.current.filteredProcesses).toEqual(["AuditFlow"]));
    expect(result.current.selectedProcess).toBe("AuditFlow");
    expect(result.current.recentUnpinnedRepoPaths).toEqual(["F:\\OLD"]);
    expect(result.current.isCurrentRepoPinned).toBe(true);
  });
});
