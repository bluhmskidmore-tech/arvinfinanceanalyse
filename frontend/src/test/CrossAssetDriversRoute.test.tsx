import { act, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
import {
  createWorkbenchMemoryRouter,
  renderWorkbenchApp,
} from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="cross-asset-echarts-stub" />,
}));

describe("CrossAssetDriversRoute", () => {
  beforeAll(async () => {
    // 预热路由懒加载链（含真正重的 CrossAssetDriversPage 与 ThemedRouteBoundary），
    // 避免用例内 5s findBy 超时为首个模块转换买单。
    await import("../features/cross-asset/pages/CrossAssetPage");
    await import("../features/cross-asset/pages/CrossAssetDriversPage");
    await import("../app/ThemedRouteBoundary");
  }, 30_000);

  it("renders the cross-asset-drivers compatibility route", async () => {
    renderWorkbenchApp(["/cross-asset-drivers"], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-first-screen")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-hero-panel")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-zone-linkage")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-zone-transmission")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    // NCD 代理在分阶段挂载的附录末组，需等待阶段跃迁 effect 完成后再断言。
    expect(await screen.findByTestId("cross-asset-ncd-proxy")).toBeInTheDocument();
  });

  it("renders the canonical cross-asset route as the real page after lazy loading", async () => {
    renderWorkbenchApp(["/cross-asset"], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-hero-panel")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    expect(screen.queryByText("页面加载中")).not.toBeInTheDocument();
  });
  it("deduplicates the initial choice macro latest request with the shell ticker", async () => {
    const client = createApiClient({ mode: "mock" });
    const getChoiceMacroLatest = vi.spyOn(client, "getChoiceMacroLatest");

    renderWorkbenchApp(["/cross-asset"], { client });

    expect(
      await screen.findByTestId("cross-asset-drivers-page"),
    ).toBeInTheDocument();
    expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
  });

  it("refreshes a warmed shell snapshot when entering the decision page", async () => {
    const client = createApiClient({ mode: "mock" });
    const getChoiceMacroLatest = vi.spyOn(client, "getChoiceMacroLatest");
    const router = createWorkbenchMemoryRouter(["/news-events"]);

    render(
      <AppProviders client={client}>
        <RouterProvider router={router} future={routerFuture} />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("workbench-market-ticker")).toHaveTextContent(
        "1.71%",
      );
    });

    await act(async () => {
      await router.navigate("/cross-asset");
    });

    expect(
      await screen.findByTestId("cross-asset-drivers-page"),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(2);
    });
  });
});
