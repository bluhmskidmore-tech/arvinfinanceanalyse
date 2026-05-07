import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  AnalysisGrid,
  DataStatusStrip,
  EvidencePanel,
  KpiBand,
  KpiBandMetric,
  PageDecisionHero,
  PageHeader,
  PageStateSurface,
  PageV2Shell,
  PageV2SurfacePanel,
} from "../components/page/PagePrimitives";
import { PAGE_V2_CONTRACT } from "../components/page/PagePrimitiveStyles";

describe("PagePrimitives v2 opt-in contract", () => {
  it("keeps the legacy primitives classless while exposing opt-in v2 surfaces", () => {
    render(
      <>
        <PageHeader title="旧标题" description="旧页面仍走 v1 默认输出" />
        <PageV2Shell testId="v2-shell">
          <PageV2SurfacePanel testId="v2-panel">v2 content</PageV2SurfacePanel>
        </PageV2Shell>
      </>,
    );

    expect(screen.getByText("旧标题").closest("section")).not.toHaveClass("moss-page-v2-shell");
    expect(screen.getByText("旧标题").closest("section")).not.toHaveClass("moss-page-v2-decision-hero");
    expect(screen.getByTestId("v2-shell")).toHaveClass("moss-page-v2-shell");
    expect(screen.getByTestId("v2-panel")).toHaveClass("moss-page-v2-surface");
  });

  it("renders PageDecisionHero slots and contract hero CSS root", () => {
    render(
      <PageDecisionHero
        testId="hero"
        title="组合总览"
        businessQuestion="今日组合暴露在哪些主要风险维度下仍可控？"
        reportDateSlot={<span data-testid="rd">截止 2026-05-01</span>}
        conclusion={<span data-testid="conc">利差走阔，_credit_ 低配维持</span>}
        actions={<button type="button">导出</button>}
        titleTestId="hero-title"
        questionTestId="hero-q"
      />,
    );

    expect(screen.getByTestId("hero")).toHaveClass(PAGE_V2_CONTRACT.decisionHeroRoot);
    expect(screen.getByTestId("hero-title")).toHaveTextContent("组合总览");
    expect(screen.getByTestId("hero-q")).toHaveTextContent("风险维度");
    expect(screen.getByTestId("rd")).toHaveTextContent("截止");
    expect(screen.getByTestId("conc")).toBeTruthy();
    expect(screen.getByRole("button", { name: "导出" })).toBeTruthy();
  });

  it("renders DataStatusStrip, KpiBand, KpiBandMetric, AnalysisGrid, EvidencePanel, PageStateSurface", () => {
    render(
      <>
        <DataStatusStrip testId="strip">
          <span data-testid="pill">Stale</span>
        </DataStatusStrip>
        <KpiBand testId="kpis">
          <KpiBandMetric label="久期" value="4.26" footer="年" testId="kpi-1" />
        </KpiBand>
        <AnalysisGrid columns={3} testId="grid">
          <div>a</div>
          <div>b</div>
          <div>c</div>
        </AnalysisGrid>
        <EvidencePanel heading="血缘与定义" testId="evidence">
          <p>证据正文</p>
        </EvidencePanel>
        <PageStateSurface variant="fallback-date" title="使用中" description="兜底报告日生效" testId="st" />
      </>,
    );

    expect(screen.getByTestId("strip")).toHaveClass(PAGE_V2_CONTRACT.dataStatusRoot);
    expect(screen.getByTestId("pill")).toBeTruthy();

    expect(screen.getByTestId("kpis")).toHaveClass(PAGE_V2_CONTRACT.kpiBandRoot);
    expect(screen.getByTestId("kpi-1")).toHaveClass(PAGE_V2_CONTRACT.kpiMetricItem);
    expect(screen.getByTestId("kpi-1")).toHaveTextContent("4.26");

    expect(screen.getByTestId("grid")).toHaveClass("moss-page-v2-analysis-grid--cols-3");

    expect(screen.getByTestId("evidence")).toHaveClass(PAGE_V2_CONTRACT.evidencePanelRoot);
    expect(screen.getByText("血缘与定义")).toBeTruthy();

    const surf = screen.getByTestId("st");
    expect(surf).toHaveAttribute("data-state-variant", "fallback-date");
    expect(surf).toHaveClass(PAGE_V2_CONTRACT.stateSurfaceRoot);
    expect(screen.getByText("兜底报告日生效")).toBeTruthy();
  });
});
