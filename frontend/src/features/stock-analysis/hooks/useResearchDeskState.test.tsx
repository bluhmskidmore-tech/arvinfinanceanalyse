import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useResearchDeskState } from "./useResearchDeskState";

describe("useResearchDeskState", () => {
  it("starts on the queue pool with the summary dossier and empty notes", () => {
    const { result } = renderHook(() =>
      useResearchDeskState({ onRequestCandidateHistory: vi.fn() }),
    );

    expect(result.current.poolTab).toBe("queue");
    expect(result.current.dossierTab).toBe("summary");
    expect(result.current.watchlistCodes).toEqual([]);
    expect(result.current.noteDraft).toBe("");
    expect(result.current.savedNote).toBe("");
  });

  it("toggles a stock in and out of the watchlist", () => {
    const { result } = renderHook(() =>
      useResearchDeskState({ onRequestCandidateHistory: vi.fn() }),
    );

    act(() => {
      result.current.toggleWatchlist("600519.SH");
    });
    expect(result.current.watchlistCodes).toEqual(["600519.SH"]);

    act(() => {
      result.current.toggleWatchlist("000001.SZ");
    });
    expect(result.current.watchlistCodes).toEqual(["600519.SH", "000001.SZ"]);

    act(() => {
      result.current.toggleWatchlist("600519.SH");
    });
    expect(result.current.watchlistCodes).toEqual(["000001.SZ"]);
  });

  it("opens history by switching both tabs and requesting the candidate-history endpoint", () => {
    const onRequestCandidateHistory = vi.fn();
    const { result } = renderHook(() => useResearchDeskState({ onRequestCandidateHistory }));

    act(() => {
      result.current.openHistory();
    });

    expect(result.current.poolTab).toBe("history");
    expect(result.current.dossierTab).toBe("appendix");
    expect(onRequestCandidateHistory).toHaveBeenCalledTimes(1);
  });

  it("saves a trimmed note prefixed with the selected candidate and ignores blank drafts", () => {
    const { result } = renderHook(() =>
      useResearchDeskState({ onRequestCandidateHistory: vi.fn() }),
    );

    act(() => {
      result.current.setNoteDraft("   ");
      result.current.saveNote({ stockName: "贵州茅台", stockCode: "600519.SH" });
    });
    expect(result.current.savedNote).toBe("");

    act(() => {
      result.current.setNoteDraft("  突破前高，待量能确认  ");
    });
    act(() => {
      result.current.saveNote({ stockName: "贵州茅台", stockCode: "600519.SH" });
    });
    expect(result.current.savedNote).toBe("贵州茅台 600519.SH：突破前高，待量能确认");

    act(() => {
      result.current.setNoteDraft("无选中标的时不加前缀");
    });
    act(() => {
      result.current.saveNote(null);
    });
    expect(result.current.savedNote).toBe("无选中标的时不加前缀");
  });
});
