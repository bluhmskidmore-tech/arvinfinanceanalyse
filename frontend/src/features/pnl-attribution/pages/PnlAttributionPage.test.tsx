import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PnlAttributionPage from "./PnlAttributionPage";

vi.mock("../components/PnlAttributionView", () => ({
  PnlAttributionView: ({ reportDate }: { reportDate?: string }) => (
    <div data-testid="pnl-attribution-view">{reportDate ?? "no report date"}</div>
  ),
}));

describe("PnlAttributionPage", () => {
  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("honors report_date from the URL", () => {
    window.history.pushState({}, "", "/pnl-attribution?report_date=2026-04-30");

    render(<PnlAttributionPage />);

    expect(screen.getByTestId("pnl-attribution-view")).toHaveTextContent("2026-04-30");
  });
});
