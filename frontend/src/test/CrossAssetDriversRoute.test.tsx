import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="cross-asset-echarts-stub" />,
}));

describe("CrossAssetDriversRoute", () => {
  beforeAll(async () => {
    await import("../features/cross-asset/pages/CrossAssetPage");
  }, 20_000);

  it("renders the cross-asset-drivers compatibility route", async () => {
    renderWorkbenchApp(["/cross-asset-drivers"], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-transmission-axes")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-ncd-proxy")).toBeInTheDocument();
  });

  it("renders the canonical cross-asset route as the real page after lazy loading", async () => {
    renderWorkbenchApp(["/cross-asset"], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    expect(screen.queryByText("页面加载中")).not.toBeInTheDocument();
  });
});
