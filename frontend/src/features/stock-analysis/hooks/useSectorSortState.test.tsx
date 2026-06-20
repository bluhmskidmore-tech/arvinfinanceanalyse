import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSectorSortState } from "./useSectorSortState";

describe("useSectorSortState", () => {
  it("starts on rank ascending and renders a suffix only for the active key", () => {
    const { result } = renderHook(() => useSectorSortState());

    expect(result.current.sectorSort).toEqual({ key: "rank", order: "ascend" });
    expect(result.current.renderSortSuffix("rank")).toBe(" ▲");
    expect(result.current.renderSortSuffix("score")).toBe("");
  });

  it("toggles the active sort order and starts new keys ascending", () => {
    const { result } = renderHook(() => useSectorSortState());

    act(() => {
      result.current.toggleSort("rank");
    });
    expect(result.current.sectorSort).toEqual({ key: "rank", order: "descend" });
    expect(result.current.renderSortSuffix("rank")).toBe(" ▼");

    act(() => {
      result.current.toggleSort("score");
    });
    expect(result.current.sectorSort).toEqual({ key: "score", order: "ascend" });
    expect(result.current.renderSortSuffix("rank")).toBe("");
    expect(result.current.renderSortSuffix("score")).toBe(" ▲");
  });
});
