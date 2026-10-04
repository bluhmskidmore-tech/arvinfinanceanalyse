import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StrictMode, type ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import MarketHomeLayout from "./MarketHomeLayout";
import type { ModuleHomeSourceQueries, ModuleHomeView } from "./moduleHomeModel";
import type { ModuleWorkbenchHomeConfig } from "./moduleHomeConfig";

vi.mock("./marketChartPalette", () => ({ useMarketChartPalette: () => undefined }));
vi.mock("./MarketBackendDataWorkbench", () => ({ MarketBackendDataWorkbench: () => null }));
vi.mock("./MarketFinancialChartsWorkbench", () => ({ MarketFinancialChartsWorkbench: () => null }));
vi.mock("./MarketOverviewDenseFirstScreen", () => ({
  MarketOverviewDenseFirstScreen: ({ chapterNav }: { chapterNav: ReactNode }) => <>
    <section id="market-overview-judgment">观察</section>{chapterNav}
    <button id="market-home-macro-trigger">宏观详情</button>
    <a href="/macro-observation?origin=market-overview&return_section=macro" onClick={(event) => event.preventDefault()}>进入宏观观察</a>
  </>,
}));

afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks(); });

function page() {
  return <StrictMode><MemoryRouter><MarketHomeLayout view={{ stateLabel: "可用" } as ModuleHomeView} config={{ title: "市场" } as ModuleWorkbenchHomeConfig}
    tapeDateRange="2026-09-04" formalTradeDate="2026-09-04" isRefreshing={false} refreshStatus="" refreshError=""
    queries={{ marketSnapshot: { data: {} } } as ModuleHomeSourceQueries} onBackendActiveKeyChange={vi.fn()} onChartsVisible={vi.fn()} onChartSectionsChange={vi.fn()} onRefreshData={vi.fn()} /></MemoryRouter></StrictMode>;
}

it("restores page-local search, disclosures and focus after returning from source context", async () => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
  const first = render(page());
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "国债" } });
  fireEvent.click(screen.getByText("全部行情", { selector: "strong" }));
  fireEvent.click(screen.getByRole("link", { name: "进入宏观观察" }));
  first.unmount();
  render(page());
  await waitFor(() => expect(screen.getByRole("button", { name: "宏观详情" })).toHaveFocus());
  expect(screen.getByRole("textbox")).toHaveValue("国债");
  expect(document.getElementById("market-backend-data-all")).toHaveAttribute("open");
  expect(sessionStorage.getItem("moss:market-home:return-state")).toBeNull();
});
