import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { AlertList } from "../components/AlertList";
import { DataModeRibbon } from "../components/DataModeRibbon";
import { StatusPill } from "../components/StatusPill";
import { SummaryBlock } from "../components/SummaryBlock";
import { designTokens } from "../theme/designSystem";

describe("shared display components style governance", () => {
  it("renders alert severity dots with design tokens", () => {
    const { container } = render(
      <AlertList items={[{ level: "danger", title: "Risk limit breached" }]} />,
    );

    const dot = container.querySelector("[aria-hidden='true']");
    expect(dot).toHaveStyle({ background: designTokens.color.danger[500] });
  });

  it("renders summary copy with extracted token-backed classes", () => {
    render(<SummaryBlock title="Conclusion" content="Use governed display tokens." />);

    expect(screen.getByText("Use governed display tokens.")).toHaveClass("summary-block__content");
  });

  it("renders status pills with extracted status classes", () => {
    render(<StatusPill status="warning" label="Fallback" />);

    const pill = screen.getByText("Fallback");
    expect(pill).toHaveClass("status-pill");
    expect(pill).toHaveAttribute("data-status", "warning");
    expect(pill).not.toHaveAttribute("style");
  });

  it("marks the mock data ribbon with the global governance class", () => {
    render(
      <ApiClientProvider client={createApiClient({ mode: "mock" })}>
        <DataModeRibbon />
      </ApiClientProvider>,
    );

    expect(document.querySelector("#data-mode-ribbon")).toHaveClass("moss-data-mode-ribbon");
    expect(document.querySelector("#data-mode-ribbon")).toHaveAttribute("data-variant", "default");
  });

  it("marks the cockpit mock ribbon with a compact governance variant", () => {
    render(
      <ApiClientProvider client={createApiClient({ mode: "mock" })}>
        <DataModeRibbon variant="cockpit" />
      </ApiClientProvider>,
    );

    expect(document.querySelector("#data-mode-ribbon")).toHaveClass("moss-data-mode-ribbon");
    expect(document.querySelector("#data-mode-ribbon")).toHaveClass("moss-data-mode-ribbon--cockpit");
    expect(document.querySelector("#data-mode-ribbon")).toHaveAttribute("data-variant", "cockpit");
  });

  it("hides the data mode ribbon when the client is in real mode", () => {
    render(
      <ApiClientProvider client={createApiClient({ mode: "real", baseUrl: "/api" })}>
        <DataModeRibbon />
      </ApiClientProvider>,
    );

    expect(document.querySelector("#data-mode-ribbon")).not.toBeInTheDocument();
  });
});
