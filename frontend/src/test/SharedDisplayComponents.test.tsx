import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiClientProvider, createApiClient } from "../api/client";
import { AlertList } from "../components/AlertList";
import { DataModeRibbon } from "../components/DataModeRibbon";
import { SummaryBlock } from "../components/SummaryBlock";
import { designTokens } from "../theme/designSystem";
import { shellTokens } from "../theme/tokens";

describe("shared display components style governance", () => {
  it("renders alert severity dots with design tokens", () => {
    const { container } = render(
      <AlertList items={[{ level: "danger", title: "Risk limit breached" }]} />,
    );

    const dot = container.querySelector("[aria-hidden='true']");
    expect(dot).toHaveStyle({ background: designTokens.color.danger[500] });
  });

  it("renders summary copy with shell text tokens", () => {
    render(<SummaryBlock title="Conclusion" content="Use governed display tokens." />);

    expect(screen.getByText("Use governed display tokens.")).toHaveStyle({
      color: shellTokens.colorTextSecondary,
    });
  });

  it("marks the mock data ribbon with the global governance class", () => {
    render(
      <ApiClientProvider client={createApiClient({ mode: "mock" })}>
        <DataModeRibbon />
      </ApiClientProvider>,
    );

    expect(document.querySelector("#data-mode-ribbon")).toHaveClass("moss-data-mode-ribbon");
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
