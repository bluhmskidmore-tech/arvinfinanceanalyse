import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../components/grid/MossAgGrid", () => ({
  MossAgGrid: ({ "data-testid": testId }: { "data-testid"?: string }) => (
    <div data-testid={testId}>grid</div>
  ),
}));

import { DeferredBalanceAnalysisGrid } from "./DeferredBalanceAnalysisGrid";

function toggleDetails(details: HTMLDetailsElement, open: boolean) {
  details.open = open;
  fireEvent(details, new Event("toggle"));
}

describe("DeferredBalanceAnalysisGrid", () => {
  it("loads on first expansion and preserves the mounted grid across later toggles", async () => {
    render(
      <details data-testid="supplemental-panel">
        <summary>Supplemental data</summary>
        <DeferredBalanceAnalysisGrid
          columnDefs={[]}
          data-testid="supplemental-grid"
          rowData={[]}
        />
      </details>,
    );

    expect(screen.queryByTestId("supplemental-grid")).not.toBeInTheDocument();

    const details = screen.getByTestId("supplemental-panel") as HTMLDetailsElement;
    toggleDetails(details, true);
    const mountedGrid = await screen.findByTestId("supplemental-grid");

    toggleDetails(details, false);
    expect(screen.getByTestId("supplemental-grid")).toBe(mountedGrid);

    toggleDetails(details, true);
    expect(screen.getByTestId("supplemental-grid")).toBe(mountedGrid);
  });
});
