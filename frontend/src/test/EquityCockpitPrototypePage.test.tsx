import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient } from "../api/client";
import EquityCockpitPrototypePage from "../features/prototype/EquityCockpitPrototypePage";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="prototype-echarts-stub" />,
}));

describe("EquityCockpitPrototypePage", () => {
  it("shows a clear prototype and mock warning ribbon", () => {
    render(
      <AppProviders client={createApiClient({ mode: "mock" })}>
        <EquityCockpitPrototypePage />
      </AppProviders>,
    );

    expect(screen.getByTestId("equity-prototype-ribbon")).toHaveTextContent(
      /prototype \/ mock only/i,
    );
    expect(screen.getByTestId("equity-prototype-ribbon")).toHaveTextContent(
      /not for business decisions/i,
    );
  });
});
