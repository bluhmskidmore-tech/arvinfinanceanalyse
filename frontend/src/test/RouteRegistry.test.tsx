import { screen, within } from "@testing-library/react";

import { primaryWorkbenchNavigation } from "../mocks/navigation";
import { workbenchSections } from "../router/routes";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("RouteRegistry", () => {
  it("exposes the current visible primary workbench entries", () => {
    expect(workbenchSections).toHaveLength(primaryWorkbenchNavigation.length);
  });

  it("renders the dashboard route inside the workbench shell", async () => {
    renderWorkbenchApp(["/"]);

    expect(await screen.findByText("MOSS")).toBeInTheDocument();
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", { name: /驾驶舱/ }),
    ).toBeInTheDocument();
  });

  it("renders the operations-analysis route as the consolidated read-only entry", async () => {
    renderWorkbenchApp(["/operations-analysis"]);

    expect(
      await screen.findByRole("heading", { name: "经营分析入口" }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("operations-entry-source-count")).toBeInTheDocument();
  });

  it("renders the source-preview route as the canonical source workbench page", async () => {
    renderWorkbenchApp(["/source-preview"]);

    expect(
      await screen.findByRole("heading", { name: "数据源规则预览" }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("source-family")).toBeInTheDocument();
  });

  it("renders the news-events route with the read-only news workbench", async () => {
    renderWorkbenchApp(["/news-events"]);

    expect(await screen.findByRole("heading", { name: "新闻事件" })).toBeInTheDocument();
    expect(await screen.findByTestId("news-events-table")).toBeInTheDocument();
    expect(await screen.findByLabelText("news-events-topic-code")).toBeInTheDocument();
  });

  it("renders the product-category pnl route with page content", async () => {
    renderWorkbenchApp(["/product-category-pnl"]);

    expect(
      await screen.findByRole("heading", { name: "产品类别损益分析" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("产品类别损益分析表（单位：亿元）"),
    ).toBeInTheDocument();
    expect(await screen.findByText("债券投资")).toBeInTheDocument();
  });

  it("renders the bond-analysis route with the overview-first shell", async () => {
    renderWorkbenchApp(["/bond-analysis"]);

    expect(
      await screen.findByTestId("bond-analysis-overview", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("bond-analysis-module-grid", {}, { timeout: 10000 }),
    ).toBeInTheDocument();
  });

  it("renders the product-category adjustment audit route", async () => {
    renderWorkbenchApp(["/product-category-pnl/audit"]);

    expect(
      await screen.findByRole("heading", { name: "产品损益调整审计" }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText("审计-报表月份")).toBeInTheDocument();
  });

  it("renders the market-data route with backend-backed content", async () => {
    renderWorkbenchApp(["/market-data"]);

    expect(
      await screen.findByRole("heading", { name: "市场数据工作台" }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-catalog-count")).toBeInTheDocument();
  });

  it("renders the hidden balance-analysis route as the first governed balance consumer", async () => {
    renderWorkbenchApp(["/balance-analysis"]);

    expect(
      await screen.findByRole("heading", { name: "资产负债分析" }),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation")).getByRole("link", {
        name: /资产负债分析/,
      }),
    ).toHaveAttribute("href", "/balance-analysis");
    expect(await screen.findByTestId("balance-analysis-table")).toBeInTheDocument();
  });

  it("renders the pnl-bridge route with the governed bridge shell", async () => {
    renderWorkbenchApp(["/pnl-bridge"]);

    expect(
      await screen.findByRole("heading", { name: "损益桥接" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("汇总")).toBeInTheDocument();
    expect(await screen.findByLabelText("pnl-bridge-report-date")).toBeInTheDocument();
  });
});
