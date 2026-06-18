import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="cross-asset-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { LivermoreOutputKey } from "../api/contracts";
import { MarketCandidateActions } from "../features/cross-asset/components/MarketCandidateActions";
import type { CrossAssetCandidateAction } from "../features/cross-asset/lib/crossAssetDriversPageModel";
import CrossAssetPage from "../features/cross-asset/pages/CrossAssetPage";

const CROSS_ASSET_DRIVERS_CSS_PATH = resolve(
  process.cwd(),
  "src/features/cross-asset/pages/CrossAssetDriversPage.css",
);

function renderPage(client: ApiClient = createApiClient({ mode: "mock" })) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(
    <Wrapper>
      <CrossAssetPage />
    </Wrapper>,
  );
}

describe("CrossAssetPage", () => {
  it("keeps page-local decorative colors on the IB light institutional token family", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).not.toMatch(/moss-color-warm-/);
    expect(css).not.toMatch(/rgba\((255, 253, 248|246, 241, 232|255, 250, 242|121, 96, 74|112, 140, 116|52, 43, 39)/);
    expect(css).not.toMatch(/#(fffdf8|f0e6d8|e4d8c8|b8a38f|342b27|6f6258|8f7e70|b85c38|708c74|7c3e46|667a96)/i);
    expect(css).toContain("var(--ib-accent)");
    expect(css).toContain("var(--ib-up)");
    expect(css).toContain("var(--ib-down)");
    expect(css).toContain("var(--ib-warn)");
    expect(css).toContain("var(--ib-ink-muted)");
    expect(css).toContain("--ca-paper: var(--ib-paper)");
  });

  it("keeps shared shell compression out of page-local styles", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).toContain(".cross-asset-first-screen-grid");
    expect(css).not.toContain(".workbench-shell-grid--cross-asset");
    expect(css).not.toContain(".workbench-shell-grid--institutional-console.workbench-shell-grid--cross-asset");
    expect(css).not.toContain('[data-testid="workbench-section-subnav"]');
    expect(css).not.toContain('[data-testid="workbench-governance-banner"]');
    expect(css).not.toContain(".workbench-market-ticker-item:nth-of-type(n + 7)");
    expect(css).not.toContain('.workbench-shell-grid--desktop-aligned [data-testid="workbench-section-subnav"]');
    expect(css).not.toContain('.workbench-shell-grid--desktop-aligned [data-testid="workbench-governance-banner"]');
    expect(css).not.toContain('.workbench-main-column [data-testid="workbench-section-subnav"]');
    expect(css).not.toContain(':has([data-testid="cross-asset-drivers-page"])');
  });

  it("renders the reference dashboard structure from the supplied Product Design screenshot", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const page = await screen.findByTestId("cross-asset-drivers-page");
    const toolbar = within(page).getByTestId("cross-asset-reference-toolbar");
    const summary = within(page).getByTestId("cross-asset-reference-summary");
    const evidenceMatrix = within(page).getByTestId("cross-asset-reference-evidence-matrix");
    const sourceAudit = within(page).getByTestId("cross-asset-reference-source-audit");
    const lowerGrid = within(page).getByTestId("cross-asset-reference-lower-grid");
    const trendStrip = within(page).getByTestId("cross-asset-reference-trend-strip");

    expect(toolbar).toHaveTextContent("跨资产驱动");
    expect(toolbar).toHaveTextContent("报告日");
    expect(toolbar).toHaveTextContent("导出报告");
    expect(summary).toHaveTextContent("核心结论");
    expect(summary).toHaveTextContent("当前格局");
    expect(summary).toHaveTextContent("宏观质量");
    expect(summary).toHaveTextContent("联动质量");
    expect(evidenceMatrix).toHaveTextContent("证据矩阵");
    expect(evidenceMatrix).toHaveTextContent("资产类别");
    expect(evidenceMatrix).toHaveTextContent("关键指标");
    expect(sourceAudit).toHaveTextContent("来源与审计");
    expect(sourceAudit).toHaveTextContent("数据源");
    expect(sourceAudit).toHaveTextContent("下一步核对");
    expect(lowerGrid).toHaveTextContent("相关性热力");
    expect(lowerGrid).toHaveTextContent("传导主线");
    expect(lowerGrid).toHaveTextContent("投资研究判断");
    expect(trendStrip).toHaveTextContent("走势与观察");
    expect(trendStrip.querySelectorAll(".cross-asset-reference-trend-card")).toHaveLength(6);
    expect(screen.queryByTestId("market-workbench-topbar")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-workbench-nav")).not.toBeInTheDocument();
  });

  it("keeps the first-screen command center dense enough for desktop decision scanning", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const toolbarBlock = css.match(/\.cross-asset-reference-toolbar \{[\s\S]*?\n\}/)?.[0] ?? "";
    const summaryBlock = css.match(/\.cross-asset-reference-summary \{[\s\S]*?\n\}/)?.[0] ?? "";
    const fusionLayoutBlock = css.match(/\.cross-asset-reference-fusion-layout\.cross-asset-fusion-layout \{[\s\S]*?\n\}/)?.[0] ?? "";
    const lowerGridBlock = css.match(/\.cross-asset-reference-lower-grid \{[\s\S]*?\n\}/)?.[0] ?? "";
    const correlationMatrixBlock = css.match(/\.cross-asset-reference-correlation__matrix \{[\s\S]*?\n\}/)?.[0] ?? "";
    const correlationCellBlock =
      css.match(
        /\.cross-asset-reference-correlation__matrix > span,[\s\S]*?\.cross-asset-reference-correlation__row > span \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const railBlock = css.match(/\.cross-asset-action-rail \{[\s\S]*?\n\}/)?.[0] ?? "";
    const railSummaryBlock =
      css.match(/\.cross-asset-action-rail__summary[\s\S]*?\.cross-asset-action-rail__action \{[\s\S]*?\}/)?.[0] ??
      "";

    expect(css).toContain(".cross-asset-first-screen {");
    expect(toolbarBlock).toContain("justify-content: space-between;");
    expect(summaryBlock).toContain("grid-template-columns:");
    expect(fusionLayoutBlock).toContain("grid-template-columns: minmax(0, 1.62fr) minmax(360px, 0.9fr);");
    expect(fusionLayoutBlock).toContain('grid-template-areas: "evidence rail";');
    expect(lowerGridBlock).toContain("grid-template-columns: minmax(540px, 1.35fr) minmax(320px, 0.82fr) minmax(380px, 0.98fr);");
    expect(correlationMatrixBlock).toContain("grid-template-columns: 76px repeat(5, minmax(0, 1fr));");
    expect(correlationCellBlock).toContain("font-size: 12px;");
    expect(css).toContain(".cross-asset-status-region--compact");
    expect(railBlock).toContain("border-left: 3px solid");
    expect(railBlock).toContain("background: var(--ca-card);");
    expect(railBlock).toContain("box-shadow: none;");
    expect(css).not.toContain("AI 决策舱");
    expect(css).not.toContain("CA.DRIVERS");
    expect(css).not.toContain("ACTION LEDGER");
    expect(css).not.toContain("Transmission path");
    expect(css).not.toContain("Evidence tape");
    expect(css).not.toContain(".cross-asset-trading-desk");
    expect(css).not.toContain(".cross-asset-market-radar");
    expect(railBlock).not.toContain("linear-gradient(180deg, #10356a, #0b2b58)");
    expect(railBlock).not.toContain("background: linear-gradient(180deg, #174783, #10356a);");
    expect(railBlock).toContain("isolation: isolate;");
    expect(railSummaryBlock).toContain("border-bottom: 1px solid var(--ca-border-muted);");
    expect(css).toContain(".cross-asset-action-rail__metrics {");
    expect(css).toContain("grid-template-columns: minmax(72px, auto) minmax(0, 1fr);");
    expect(css).toContain(".cross-asset-transmission-canvas .cross-asset-research-views__evidence");
    expect(css).toContain("line-clamp: 1;");
  });

  it("renders a decision header, market state strip, transmission canvas, and action rail on the first screen", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const firstScreen = await screen.findByTestId("cross-asset-first-screen");
    const toolbar = await screen.findByTestId("cross-asset-reference-toolbar");
    const summary = await screen.findByTestId("cross-asset-reference-summary");
    const lowerGrid = await screen.findByTestId("cross-asset-reference-lower-grid");
    const decisionHeader = await screen.findByTestId("cross-asset-decision-header");
    const marketStateStrip = await screen.findByTestId("cross-asset-market-state-strip");
    const marketTape = await screen.findByTestId("cross-asset-market-tape");
    const commandCenter = await screen.findByTestId("cross-asset-first-screen-grid");
    const fusionLayout = await screen.findByTestId("cross-asset-fusion-layout");
    const evidenceMatrix = await screen.findByTestId("cross-asset-first-screen-evidence-matrix");
    const transmissionCanvas = await screen.findByTestId("cross-asset-transmission-canvas");
    const sidePanel = await screen.findByTestId("cross-asset-fusion-side-panel");
    const actionRail = await screen.findByTestId("cross-asset-action-rail");
    const reviewQueue = await screen.findByTestId("cross-asset-review-queue");

    expect(firstScreen).toContainElement(toolbar);
    expect(firstScreen).toContainElement(summary);
    expect(firstScreen).toContainElement(decisionHeader);
    expect(firstScreen).toContainElement(marketStateStrip);
    expect(firstScreen).toContainElement(commandCenter);
    expect(toolbar).toHaveTextContent("跨资产驱动");
    expect(toolbar).toHaveTextContent("报告日");
    expect(decisionHeader).toHaveTextContent("核心结论");
    expect(decisionHeader).toHaveTextContent("数据日期");
    expect(decisionHeader).not.toHaveTextContent("CA.DRIVERS");
    expect(marketStateStrip).toHaveTextContent("当前格局");
    expect(marketTape).toHaveAttribute("role", "list");
    expect(marketTape).toHaveAttribute("aria-label", "跨资产市场快讯");
    expect(marketTape.querySelectorAll('[role="listitem"]')).toHaveLength(6);
    expect(marketTape).toHaveTextContent("10Y国债");
    expect(marketTape).toHaveTextContent("DR007");
    expect(marketTape).toHaveTextContent("沪深300");
    expect(marketTape).toHaveTextContent("布油");
    expect(marketTape).toHaveTextContent("USD/CNY");
    expect(marketTape).toHaveTextContent("中美10Y利差");
    expect(commandCenter).toHaveClass("cross-asset-command-center");
    expect(commandCenter).toContainElement(fusionLayout);
    expect(fusionLayout).toContainElement(evidenceMatrix);
    expect(lowerGrid).toContainElement(transmissionCanvas);
    expect(fusionLayout).toContainElement(reviewQueue);
    expect(sidePanel).toContainElement(actionRail);
    expect(sidePanel).toContainElement(reviewQueue);
    expect(Array.from(commandCenter.children)).toEqual([fusionLayout]);
    expect(Array.from(fusionLayout.children)).toEqual([screen.getByTestId("cross-asset-reference-evidence-matrix"), sidePanel]);
    expect(Boolean(decisionHeader.compareDocumentPosition(marketStateStrip) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(marketStateStrip.compareDocumentPosition(commandCenter) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("renders the 2+3 fusion layout with evidence matrix and review queue in the first screen", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const firstScreen = await screen.findByTestId("cross-asset-first-screen");
    const fusionLayout = within(firstScreen).getByTestId("cross-asset-fusion-layout");
    const evidenceMatrix = within(fusionLayout).getByTestId("cross-asset-first-screen-evidence-matrix");
    const actionRail = within(fusionLayout).getByTestId("cross-asset-action-rail");
    const reviewQueue = within(fusionLayout).getByTestId("cross-asset-review-queue");

    expect(evidenceMatrix).toHaveTextContent("证据矩阵");
    expect(evidenceMatrix).toHaveTextContent("利率与流动性");
    expect(evidenceMatrix).toHaveTextContent("权益风险偏好");
    expect(actionRail).toHaveTextContent("动作约束");
    expect(actionRail).toHaveTextContent("仅分析，不替代指令");
    expect(reviewQueue).toHaveTextContent("待复核队列");
    expect(reviewQueue).toHaveTextContent("宏观质量");
    expect(reviewQueue).toHaveTextContent("联动质量");
  });

  it("keeps the desktop first screen styled as a quiet institutional command center", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const decisionHeaderBlock = css.match(/\.cross-asset-decision-header \{[\s\S]*?\n\}/)?.[0] ?? "";
    const marketStateBlock = css.match(/\.cross-asset-market-state-strip \{[\s\S]*?\n\}/)?.[0] ?? "";
    const commandCenterBlock = css.match(/^\.cross-asset-command-center \{[\s\S]*?\n\}/m)?.[0] ?? "";
    const fusionLayoutBlock = css.match(/\.cross-asset-reference-fusion-layout\.cross-asset-fusion-layout \{[\s\S]*?\n\}/)?.[0] ?? "";
    const referenceEvidenceBlock =
      css.match(/\.cross-asset-reference-evidence-grid\.cross-asset-command-center \{[\s\S]*?\n\}/)?.[0] ?? "";
    const reviewQueueBlock = css.match(/^\.cross-asset-review-queue \{[\s\S]*?\n\}/m)?.[0] ?? "";
    const transmissionCanvasBlock = css.match(/\.cross-asset-transmission-canvas \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(decisionHeaderBlock).toContain("grid-template-columns: 30px minmax(0, 1fr);");
    expect(decisionHeaderBlock).not.toContain("box-shadow: var(--ca-shadow-hero);");
    expect(decisionHeaderBlock).toContain("background: var(--ca-card);");
    expect(marketStateBlock).toContain("grid-template-columns:");
    expect(commandCenterBlock).toContain("display: block;");
    expect(fusionLayoutBlock).toContain('"evidence rail"');
    expect(referenceEvidenceBlock).toContain("background: transparent;");
    expect(reviewQueueBlock).toContain("border-left: 3px solid");
    expect(transmissionCanvasBlock).toContain("display: grid;");
    expect(css).toContain(".cross-asset-action-rail {");
    expect(css).toContain("@media (max-width: 1320px)");
    expect(css).toContain("grid-template-columns: minmax(0, 1fr) minmax(246px, 0.32fr);");
    expect(css).toContain(".cross-asset-transmission-map__step strong");
    expect(css).toContain("white-space: normal;");
    expect(css).not.toContain(".cross-asset-terminal-command-strip");
    expect(css).not.toContain(".cross-asset-desktop-transmission-workbench");
  });

  it("renders factor matrix, transmission path, and action list instead of equal card stacks", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const evidenceTape = await screen.findByTestId("cross-asset-evidence-tape");
    const evidenceDigest = screen.queryByTestId("cross-asset-evidence-digest");
    const transmissionMap = await screen.findByTestId("cross-asset-transmission-map");
    const actionLedger = await screen.findByTestId("cross-asset-action-ledger");

    expect(evidenceDigest).not.toBeInTheDocument();
    expect(evidenceTape).toHaveAttribute("aria-label", "关键因子矩阵");
    expect(evidenceTape).toHaveTextContent("因子");
    expect(evidenceTape).toHaveTextContent("当前");
    expect(evidenceTape).toHaveTextContent("变化");
    expect(evidenceTape).toHaveTextContent("方向");
    expect(evidenceTape).toHaveTextContent("来源");
    expect(transmissionMap).toHaveTextContent("利率");
    expect(transmissionMap).toHaveTextContent("信用/NCD");
    expect(transmissionMap).toHaveTextContent("权益");
    expect(transmissionMap).toHaveTextContent("商品");
    expect(transmissionMap).toHaveTextContent("汇率");
    expect(transmissionMap).toHaveTextContent("债券组合动作");
    expect(actionLedger).toHaveTextContent("动作清单");
    expect(actionLedger).toHaveTextContent("组合动作");
    expect(actionLedger).toHaveTextContent("证据约束");
    expect(transmissionMap).not.toHaveTextContent("Transmission path");
    expect(actionLedger).not.toHaveTextContent("ACTION LEDGER");
    expect(screen.queryByText("Execution")).not.toBeInTheDocument();
  });

  it("lets desktop status flags read as a compact evidence list", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const trustPanelBlock = css.match(/\.cross-asset-trust-panel \{[\s\S]*?\n\}/)?.[0] ?? "";
    const trustSummaryBlock = css.match(/\.cross-asset-trust-panel__summary \{[\s\S]*?\n\}/)?.[0] ?? "";
    const trustGridBlock = css.match(/\.cross-asset-trust-panel__grid \{[\s\S]*?\n\}/)?.[0] ?? "";
    const desktopTrustPanelBlock =
      css.match(/@media \(min-width: 901px\) \{[\s\S]*?\.cross-asset-trust-panel \{[\s\S]*?\n  \}/)?.[0] ??
      "";
    const desktopTrustSummaryBlock =
      css.match(/@media \(min-width: 901px\) \{[\s\S]*?\.cross-asset-trust-panel__summary \{[\s\S]*?\n  \}/)?.[0] ??
      "";
    const desktopTrustGridBlock =
      css.match(/@media \(min-width: 901px\) \{[\s\S]*?\.cross-asset-trust-panel__grid \{[\s\S]*?\n  \}/)?.[0] ??
      "";
    const desktopTrustMetaBlock =
      css.match(
        /@media \(min-width: 901px\) \{[\s\S]*?\.cross-asset-status-region--compact \.cross-asset-data-status-strip__meta\.cross-asset-page-meta \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const compactKvBlock =
      css.match(/\.cross-asset-status-region--compact \.cross-asset-data-status-strip__kv \{[\s\S]*?\n\}/)?.[0] ??
      "";
    const compactFlagBlock =
      css.match(/\.cross-asset-status-region--compact \.cross-asset-data-status-strip__flag \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const compactFlagDetailBlock =
      css.match(
        /\.cross-asset-status-region--compact \.cross-asset-data-status-strip__flag > span:last-child \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const marketStateTagRowBlock =
      css.match(/\.cross-asset-market-state-strip__tag-row \{[\s\S]*?\n\}/)?.[0] ?? "";
    const transmissionStepsBlock = css.match(/\.cross-asset-transmission-map__steps \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(trustPanelBlock).toContain("display: grid;");
    expect(trustPanelBlock).toContain("min-height: 100%;");
    expect(trustSummaryBlock).toContain("grid-template-columns: minmax(0, 1fr) auto;");
    expect(trustGridBlock).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(trustGridBlock).toContain("border: 0;");
    expect(trustGridBlock).toContain("background: transparent;");
    expect(desktopTrustPanelBlock).toContain("grid-template-columns: minmax(116px, 0.28fr) minmax(0, 1fr);");
    expect(desktopTrustPanelBlock).toContain("gap: 3px 8px;");
    expect(desktopTrustSummaryBlock).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(desktopTrustSummaryBlock).toContain("border-right: 1px solid var(--ca-border-muted);");
    expect(desktopTrustGridBlock).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(desktopTrustGridBlock).toContain("grid-column: 2;");
    expect(desktopTrustMetaBlock).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(compactKvBlock).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(compactFlagBlock).toContain("grid-template-columns: auto minmax(0, 1fr);");
    expect(compactFlagDetailBlock).toContain("display: -webkit-box;");
    expect(compactFlagDetailBlock).toContain("-webkit-line-clamp: 1;");
    expect(compactFlagDetailBlock).toContain("white-space: normal;");
    expect(marketStateTagRowBlock).toContain("grid-template-columns: 42px minmax(0, 1fr);");
    expect(transmissionStepsBlock).toContain("grid-auto-rows: 1fr;");
    expect(transmissionStepsBlock).toContain("align-items: stretch;");
  });

  it("keeps the deep evidence board visually secondary to the first-screen decision block", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const decisionBoardBlock = css.match(/\.cross-asset-decision-board \{[\s\S]*?\n\}/)?.[0] ?? "";
    const decisionZoneTitleBlock = css.match(/^\.cross-asset-decision-zone__title \{[\s\S]*?\n\}/m)?.[0] ?? "";
    const evidenceDigestBlock = css.match(/\.cross-asset-evidence-digest \{[\s\S]*?\n\}/)?.[0] ?? "";
    const evidenceDetailsBlock = css.match(/\.cross-asset-evidence-details \{[\s\S]*?\n\}/)?.[0] ?? "";
    const evidenceLedgerLayoutBlock =
      css.match(/\.cross-asset-reference-depth \.cross-asset-evidence-ledger__matrix-grid \{[\s\S]*?\n\}/)?.[0] ?? "";
    const evidenceLedgerTableBlock = css.match(/\.cross-asset-evidence-factor__table \{[\s\S]*?\n\}/)?.[0] ?? "";
    const linkageHeatmapBlock =
      css.match(/\.cross-asset-reference-depth \.cross-asset-linkage-heatmap-ledger \{[\s\S]*?\n\}/)?.[0] ?? "";
    const evidenceGroupBlock = css.match(/^\.cross-asset-evidence-group \{[\s\S]*?\n\}/m)?.[0] ?? "";

    expect(decisionBoardBlock).toContain("background: transparent;");
    expect(decisionBoardBlock).toContain("box-shadow: none;");
    expect(decisionZoneTitleBlock).toContain("font-size: 0.74rem;");
    expect(decisionZoneTitleBlock).toContain("text-transform: none;");
    expect(evidenceDigestBlock).toContain("grid-template-columns: repeat(4, minmax(0, 1fr));");
    expect(evidenceDetailsBlock).toContain("background: transparent;");
    expect(evidenceLedgerLayoutBlock).toContain("grid-template-columns: repeat(4, minmax(0, 1fr));");
    expect(evidenceLedgerTableBlock).toContain("table-layout: fixed;");
    expect(linkageHeatmapBlock).toContain("border: 1px solid var(--ca-border-soft);");
    expect(evidenceGroupBlock).toContain("min-height: 0;");
    expect(evidenceGroupBlock).toContain("box-shadow: none;");
  });

  it("keeps the desktop digest terse and decision oriented", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const heroBlock = css.match(/\.cross-asset-decision-hero\.moss-page-v2-decision-hero \{[\s\S]*?\n\}/)?.[0] ?? "";
    const digestBodyBlock = css.match(/\.cross-asset-evidence-digest__body \{[\s\S]*?\n\}/)?.[0] ?? "";
    const digestMetricBlock = css.match(/\.cross-asset-evidence-digest__metric \{[\s\S]*?\n\}/)?.[0] ?? "";
    const evidenceSummaryFocusBlock =
      css.match(/\.cross-asset-evidence-details > summary:focus-visible \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(heroBlock).not.toContain("radial-gradient");
    expect(digestBodyBlock).toContain("-webkit-line-clamp: 1;");
    expect(digestMetricBlock).toContain("grid-template-columns: minmax(0, 1fr) auto;");
    expect(evidenceSummaryFocusBlock).toContain("outline:");
    expect(evidenceSummaryFocusBlock).toContain("outline-offset:");
  });

  it("gives the desktop action rail and first evidence card a clear final-call hierarchy", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const desktopCss = css.slice(css.lastIndexOf("@media (min-width: 901px)"));
    const railDesktopBlock =
      desktopCss.match(/\.cross-asset-action-rail \{[\s\S]*?\n  \}/)?.[0] ?? "";
    const actionDesktopBlock =
      desktopCss.match(/\.cross-asset-action-rail__action \{[\s\S]*?\n  \}/)?.[0] ?? "";
    const actionStrongDesktopBlock =
      desktopCss.match(/\.cross-asset-action-rail__action strong \{[\s\S]*?\n  \}/)?.[0] ?? "";
    const firstEvidenceDesktopBlock =
      desktopCss.match(/\.cross-asset-evidence-digest__item:first-child \{[\s\S]*?\n  \}/)?.[0] ?? "";
    const nonFirstEvidenceDesktopBlock =
      desktopCss.match(/\.cross-asset-evidence-digest__item:not\(:first-child\) \{[\s\S]*?\n  \}/)?.[0] ?? "";

    expect(railDesktopBlock).toContain("grid-template-rows: auto auto auto minmax(0, 1fr);");
    expect(railDesktopBlock).toContain("border-left-width: 3px;");
    expect(actionDesktopBlock).toContain("align-self: start;");
    expect(actionDesktopBlock).toContain("border-color: var(--ca-border-muted);");
    expect(actionDesktopBlock).toContain("background: transparent;");
    expect(actionStrongDesktopBlock).toContain("font-size: 0.9rem;");
    expect(actionStrongDesktopBlock).toContain("color: var(--ca-slate);");
    expect(firstEvidenceDesktopBlock).toContain("border-left-width: 4px;");
    expect(firstEvidenceDesktopBlock).toContain("background: var(--ca-card);");
    expect(firstEvidenceDesktopBlock).toContain("box-shadow: none;");
    expect(nonFirstEvidenceDesktopBlock).toContain("border-left-color: color-mix(in srgb, var(--ca-accent) 48%, #ffffff);");
    expect(nonFirstEvidenceDesktopBlock).toContain("background: rgba(255, 255, 255, 0.72);");
  });

  it("makes the desktop primary research judgment read as the active transmission lane", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const desktopCss = css.slice(css.lastIndexOf("@media (min-width: 901px)"));
    const primaryResearchCardBlock =
      desktopCss.match(/\.cross-asset-transmission-canvas \.cross-asset-research-views__card:first-child \{[\s\S]*?\n  \}/)?.[0] ??
      "";
    const primaryLabelBlock =
      desktopCss.match(
        /\.cross-asset-transmission-canvas \.cross-asset-research-views__card:first-child \.cross-asset-research-views__label \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const primarySummaryBlock =
      desktopCss.match(
        /\.cross-asset-transmission-canvas \.cross-asset-research-views__card:first-child \.cross-asset-research-views__summary \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";
    const secondaryResearchCardBlock =
      desktopCss.match(
        /\.cross-asset-transmission-canvas \.cross-asset-research-views__card:not\(:first-child\) \{[\s\S]*?\n  \}/,
      )?.[0] ?? "";

    expect(primaryResearchCardBlock).toContain("border-left: 0;");
    expect(primaryResearchCardBlock).toContain("background: var(--ca-card);");
    expect(primaryResearchCardBlock).toContain("box-shadow: none;");
    expect(primaryLabelBlock).toContain("color: var(--ca-slate);");
    expect(primaryLabelBlock).toContain("font-size: 0.92rem;");
    expect(primarySummaryBlock).toContain("-webkit-line-clamp: 1;");
    expect(secondaryResearchCardBlock).toContain("border-left: 0;");
    expect(secondaryResearchCardBlock).toContain("background: var(--ca-card);");
  });

  it("keeps the 520px mobile fallback scoped out of the desktop workbench redesign", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const mobileCss = css.slice(css.indexOf("@media (max-width: 520px)"));

    expect(mobileCss).toContain(".cross-asset-decision-hero .moss-page-v2-decision-hero__title {");
    expect(mobileCss).toContain(".cross-asset-decision-hero .moss-page-v2-decision-hero__question {");
    expect(mobileCss).toContain("font-size: 1.65rem;");
    expect(mobileCss).not.toContain("font-size: 1.2rem;");
    expect(mobileCss).not.toContain(".cross-asset-page-meta {");
    expect(mobileCss).not.toContain(".cross-asset-action-rail__summary {");
    expect(mobileCss).not.toContain("grid-template-columns: minmax(0, 0.82fr) minmax(0, 1.18fr);");
    expect(mobileCss).not.toContain(".cross-asset-action-rail__metrics {");
    expect(mobileCss).not.toContain(".cross-asset-action-rail__action strong {");
  });

  it("does not mix mobile research compaction into the desktop workbench pass", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const mobileCss = css.slice(css.indexOf("@media (max-width: 520px)"));

    expect(mobileCss).toContain(".cross-asset-data-status-strip__flag {");
    expect(mobileCss).toContain(".cross-asset-data-status-strip__meta {");
    expect(mobileCss).not.toContain(".cross-asset-data-status-strip__flags {");
    expect(mobileCss).not.toContain(".cross-asset-transmission-canvas .cross-asset-research-views__grid {");
    expect(mobileCss).not.toContain(".cross-asset-transmission-canvas .cross-asset-research-views__card {");
    expect(mobileCss).not.toContain(".cross-asset-transmission-canvas .cross-asset-research-views__summary {");
    expect(mobileCss).not.toContain(".cross-asset-transmission-canvas .cross-asset-research-views__meta,");
  });

  it("keeps cross-asset evidence groups readable on narrow screens", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).toContain("@media (max-width: 900px)");
    expect(css).toContain(".cross-asset-first-screen-grid,");
    expect(css).toContain(".cross-asset-evidence-groups__grid,");
    expect(css).toContain(".cross-asset-evidence-ledger__matrix-grid,");
    expect(css).toContain(".cross-asset-reference-depth .cross-asset-evidence-ledger__matrix-grid,");
    expect(css).toContain(".cross-asset-evidence-factor__table {");
    expect(css).not.toContain("  .cross-asset-evidence-digest,\n  .cross-asset-metric-strip");
    expect(css).toContain("grid-template-columns: 1fr;");
  });

  it("keeps first-screen selectors and status evidence visible", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).toContain(".cross-asset-data-status-strip__kv-row");
    expect(css).toContain(".cross-asset-data-status-strip__kv-label");
    expect(css).toContain(".cross-asset-data-status-strip__flag > span:last-child");
    expect(css).not.toContain(".cross-asset-data-status-strip__flag > span:last-child {\n  display: none;");

    renderPage(createApiClient({ mode: "mock" }));

    const firstScreenGrid = await screen.findByTestId("cross-asset-first-screen-grid");
    await waitFor(() => {
      const statusFlags = screen.getByTestId("cross-asset-status-flags");
      expect(statusFlags).toHaveTextContent("Choice");
      expect(statusFlags).toHaveTextContent("Choice+公共");
      expect(statusFlags).not.toHaveTextContent("Tushare/公共补充行都已进入治理后的跨资产链路");
      expect(
        statusFlags.querySelector('[title="Choice 行与 Tushare/公共补充行都已进入治理后的跨资产链路。"]'),
      ).toBeInTheDocument();
    });
    expect(firstScreenGrid).toHaveClass("cross-asset-first-screen-grid");
  });

  it("renders below-fold indicator detail as a ledger instead of sparse mini KPI cards", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).toContain(".cross-asset-evidence-ledger__matrix-grid");
    expect(css).toContain(".cross-asset-evidence-factor__table");
    expect(css).toContain(".cross-asset-evidence-factor__percentile");
    expect(css).toContain("grid-template-columns: repeat(4, minmax(0, 1fr));");
    expect(css).not.toContain(".cross-asset-reference-depth .cross-asset-metric-strip .cross-asset-drivers-page__mini-kpi:nth-last-child(2):nth-child(odd)");
  });

  it("renders dual-source stock evidence from the default mock latest-series contract", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("cross-asset-status-flags")).toHaveTextContent("双源就绪");
    });

    const evidence = await screen.findByTestId("cross-asset-equity-evidence");
    expect(evidence).toHaveTextContent("Tushare");
    expect(evidence).toHaveTextContent("CA.CSI300");
    expect(evidence).toHaveTextContent("CA.CSI300_PE");
    expect(evidence).toHaveTextContent("CA.MEGA_CAP_WEIGHT");
    expect(evidence).toHaveTextContent("CA.MEGA_CAP_TOP5_WEIGHT");

    const broadIndex = screen.getByTestId("cross-asset-equity-evidence-broad_index");
    expect(broadIndex).toHaveTextContent("指数");
    expect(broadIndex).not.toHaveTextContent("index");
    expect(broadIndex).toHaveTextContent("Tushare");
  });

  it("uses the displayed cross-asset data date for linkage analysis", async () => {
    const client = createApiClient({ mode: "mock" });
    const latestPayload = await client.getChoiceMacroLatest();
    const baseCsi300 = latestPayload.result.series.find((point) => point.series_id === "CA.CSI300")!;
    const getMacroBondLinkageAnalysis = vi.spyOn(client, "getMacroBondLinkageAnalysis");

    vi.spyOn(client, "getChoiceMacroLatest").mockResolvedValue({
      ...latestPayload,
      result: {
        ...latestPayload.result,
        series: [
          ...latestPayload.result.series.map((point) =>
            ["E1000180", "E1003238", "EM1", "CA.DR007", "CA.CSI300"].includes(point.series_id)
              ? { ...point, trade_date: "2026-05-29" }
              : point,
          ),
          {
            ...baseCsi300,
            series_id: "NON_HEADLINE_MACRO",
            series_name: "非首屏宏观序列",
            trade_date: "2026-05-30",
          },
        ],
      },
    });

    renderPage(client);

    const hero = await screen.findByTestId("cross-asset-decision-hero");
    await waitFor(() => {
      expect(hero).toHaveTextContent("数据日期 2026-05-29");
      expect(getMacroBondLinkageAnalysis).toHaveBeenCalledWith({ reportDate: "2026-05-29" });
    });
    expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalledWith({ reportDate: "2026-05-30" });
  });

  it("renders the command center before the deep evidence stack", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const firstScreenFrame = await screen.findByTestId("cross-asset-first-screen");
    const toolbar = await screen.findByTestId("cross-asset-reference-toolbar");
    const summary = await screen.findByTestId("cross-asset-reference-summary");
    const sourceAudit = await screen.findByTestId("cross-asset-reference-source-audit");
    const lowerGrid = await screen.findByTestId("cross-asset-reference-lower-grid");
    const trendStrip = await screen.findByTestId("cross-asset-reference-trend-strip");
    const hero = await screen.findByTestId("cross-asset-decision-hero");
    const decisionHeader = await screen.findByTestId("cross-asset-decision-header");
    const marketStateStrip = await screen.findByTestId("cross-asset-market-state-strip");
    const statusStrip = await screen.findByTestId("cross-asset-data-status-strip");
    const trustPanel = await screen.findByTestId("cross-asset-trust-panel");
    const firstScreenGrid = await screen.findByTestId("cross-asset-first-screen-grid");
    const evidenceMatrix = await screen.findByTestId("cross-asset-reference-evidence-matrix");
    const actionRail = await screen.findByTestId("cross-asset-action-rail");
    const transmissionCanvas = await screen.findByTestId("cross-asset-transmission-canvas");
    const researchViews = await screen.findByTestId("cross-asset-research-views");
    const fullKpiBand = await screen.findByTestId("cross-asset-kpi-band");
    const kpiLedgerTable = await screen.findByTestId("cross-asset-kpi-ledger-table");
    const livermoreStatus = await screen.findByTestId("cross-asset-livermore-status");
    const observationSupport = await screen.findByTestId("cross-asset-observation-support-grid");
    const waterfallEvidence = await screen.findByTestId("cross-asset-driver-waterfall-evidence");
    const momentumScoreboard = await screen.findByTestId("cross-asset-momentum-scoreboard");
    const correlationHeatmap = await screen.findByTestId("cross-asset-correlation-heatmap");
    const momentumTable = await screen.findByTestId("cross-asset-momentum-table-wrap");
    const correlationMatrix = await screen.findByTestId("cross-asset-correlation-matrix-wrap");
    const heroTitle = hero.querySelector(".moss-page-v2-decision-hero__title");

    expect(heroTitle).toHaveTextContent("宏观环境偏松");
    expect(toolbar).toHaveTextContent("跨资产驱动");
    expect(hero).toHaveTextContent("核心结论");
    expect(hero).toHaveTextContent("今日传导结论");
    expect(statusStrip).toHaveTextContent("宏观");
    expect(statusStrip).toHaveTextContent("联动");
    expect(firstScreenFrame).toContainElement(toolbar);
    expect(firstScreenFrame).toContainElement(summary);
    expect(firstScreenFrame).toContainElement(decisionHeader);
    expect(firstScreenFrame).toContainElement(hero);
    expect(firstScreenFrame).toContainElement(trustPanel);
    expect(firstScreenFrame).toContainElement(marketStateStrip);
    expect(firstScreenFrame).toContainElement(sourceAudit);
    expect(firstScreenFrame).toContainElement(lowerGrid);
    expect(firstScreenFrame).toContainElement(trendStrip);
    expect(trustPanel).toContainElement(statusStrip);
    expect(trustPanel).toHaveTextContent("可信状态");
    expect(trustPanel).toHaveTextContent("报告日");
    expect(trustPanel).toHaveTextContent("宏观质量");
    expect(trustPanel).toHaveTextContent("联动质量");
    expect(trustPanel).toHaveTextContent("下一步");
    expect(trustPanel).toHaveTextContent("核对状态");
    expect(trustPanel).not.toHaveTextContent("先核对状态提示");
    expect(trustPanel).toHaveTextContent("降级快照");
    expect(trustPanel.querySelector(".cross-asset-trust-panel__summary em")).toHaveTextContent("含降级");
    expect(statusStrip).toHaveTextContent("分析链路");
    expect(statusStrip).toHaveTextContent("置信下调");
    expect(statusStrip).toHaveTextContent("Choice+公共");
    expect(statusStrip).not.toHaveTextContent("Choice + 公共源");
    expect(statusStrip).not.toHaveTextContent("本页读取分析链路，不替代正式执行输出。");
    expect(statusStrip).not.toHaveTextContent("当前包含降级快照，结论置信度需要下调。");
    expect(statusStrip.querySelector('[title="本页读取分析链路，不替代正式执行输出。"]')).toBeInTheDocument();
    expect(statusStrip.querySelector('[title="当前包含降级快照，结论置信度需要下调。"]')).toBeInTheDocument();
    const statusMetaItems = Array.from(
      statusStrip.querySelectorAll(".cross-asset-data-status-strip__meta dd.cross-asset-data-status-strip__kv-value[title]"),
    );
    expect(statusMetaItems).toHaveLength(2);
    statusMetaItems.forEach((item) => {
      expect(item.textContent).toMatch(/\d{2}:\d{2}/);
      expect(item.textContent).not.toMatch(/\d{4}-\d{2}-\d{2}T/);
      expect(item).toHaveAttribute("title", expect.stringMatching(/\d{4}-\d{2}-\d{2}T/));
    });
    expect(firstScreenFrame).toContainElement(statusStrip);
    expect(firstScreenFrame).toContainElement(firstScreenGrid);
    expect(Boolean(toolbar.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(summary.compareDocumentPosition(firstScreenGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(firstScreenGrid.compareDocumentPosition(lowerGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(lowerGrid.compareDocumentPosition(trendStrip) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(summary).toContainElement(decisionHeader);
    expect(decisionHeader).toContainElement(hero);
    expect(firstScreenGrid).toContainElement(evidenceMatrix);
    expect(firstScreenGrid).toContainElement(sourceAudit);
    expect(Boolean(marketStateStrip.compareDocumentPosition(firstScreenGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(lowerGrid).toContainElement(transmissionCanvas);
    expect(firstScreenGrid).toContainElement(actionRail);
    expect(lowerGrid).toContainElement(researchViews);
    expect(actionRail).toHaveTextContent("组合动作");
    expect(actionRail).toHaveTextContent("下一步");
    expect(screen.queryByText("AI 决策舱")).not.toBeInTheDocument();
    expect(screen.queryByTestId("cross-asset-headline-kpis")).not.toBeInTheDocument();
    expect(observationSupport).toContainElement(momentumScoreboard);
    expect(observationSupport).toContainElement(correlationHeatmap);
    expect(momentumTable).toBeInTheDocument();
    expect(correlationMatrix).toBeInTheDocument();
    expect(waterfallEvidence).toHaveTextContent("综合");
    expect(fullKpiBand).toContainElement(kpiLedgerTable);
    expect(kpiLedgerTable.querySelectorAll("tbody tr").length).toBeGreaterThanOrEqual(10);
    expect(Boolean(researchViews.compareDocumentPosition(fullKpiBand) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(fullKpiBand.compareDocumentPosition(livermoreStatus) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("does not call the trust panel normal or degraded before source metadata returns", async () => {
    const client = createApiClient({ mode: "mock" });
    const latestPayload = await client.getChoiceMacroLatest();
    const linkagePayload = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-04-10" });
    const runtimeLatestWithoutMeta = {
      result: {
        ...latestPayload.result,
        series: [
          {
            series_id: "XTEST_NEUTRAL",
            series_name: "neutral test driver",
            trade_date: "2026-04-10",
            value_numeric: 1,
            unit: "index",
            source_version: "sv_test",
            vendor_version: "vv_test",
            refresh_tier: "stable" as const,
          },
        ],
      },
    } as unknown as Awaited<ReturnType<ApiClient["getChoiceMacroLatest"]>>;
    const runtimeLinkageWithoutMeta = {
      result: {
        ...linkagePayload.result,
        report_date: "2026-04-10",
      },
    } as unknown as Awaited<ReturnType<ApiClient["getMacroBondLinkageAnalysis"]>>;

    vi.spyOn(client, "getChoiceMacroLatest").mockResolvedValue(runtimeLatestWithoutMeta);
    vi.spyOn(client, "getMacroBondLinkageAnalysis").mockResolvedValue(runtimeLinkageWithoutMeta);

    renderPage(client);

    const trustPanel = await screen.findByTestId("cross-asset-trust-panel");

    await waitFor(() => {
      expect(trustPanel).toHaveTextContent("等待证据");
      expect(trustPanel).toHaveTextContent("待返回");
      expect(trustPanel).toHaveTextContent("等待数据返回");
    });
    expect(trustPanel).not.toHaveTextContent("状态正常");
    expect(trustPanel).not.toHaveTextContent("含降级");
    expect(trustPanel).not.toHaveTextContent("可读");
  });

  it("keeps the attribution and risk diagnostics in a controlled desktop rhythm", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const analyticsBlock = css.match(/\.cross-asset-zone-analytics-grid \{[\s\S]*?\n\}/)?.[0] ?? "";
    const riskBlock = css.match(/^\.cross-asset-risk-snapshot-grid \{[\s\S]*?\n\}/m)?.[0] ?? "";
    const volBarsBlock = css.match(/\.ca-vol-alert__bars \{[\s\S]*?\n\}/)?.[0] ?? "";
    const observationDesktopBlock =
      css.match(/@media \(min-width: 1000px\) \{[\s\S]*?\.cross-asset-observation-support-grid \{[\s\S]*?\n  \}/)?.[0] ??
      "";

    expect(analyticsBlock).toContain("grid-template-columns: minmax(0, 1fr) minmax(300px, 340px);");
    expect(riskBlock).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(volBarsBlock).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(css).toContain(".ca-waterfall__decision");
    expect(css).toContain(".ca-waterfall__evidence-strip");
    expect(observationDesktopBlock).toContain(
      "grid-template-columns: minmax(320px, 0.78fr) minmax(0, 1.22fr);",
    );

    renderPage(createApiClient({ mode: "mock" }));

    const analyticsGrid = await screen.findByTestId("cross-asset-zone-analytics-grid");
    const riskRail = await screen.findByTestId("cross-asset-risk-snapshot-grid");
    const waterfallDecision = await screen.findByTestId("cross-asset-driver-waterfall-decision");
    const waterfallGapStrip = await screen.findByTestId("cross-asset-driver-waterfall-gap-strip");
    const foldedVolAssets = await screen.findByTestId("cross-asset-vol-folded-assets");

    expect(analyticsGrid).toContainElement(riskRail);
    expect(analyticsGrid).toContainElement(waterfallDecision);
    expect(analyticsGrid).toContainElement(waterfallGapStrip);
    expect(riskRail).toContainElement(foldedVolAssets);
    expect(foldedVolAssets).toHaveTextContent(/其余 \d+ 项/);
    expect(foldedVolAssets).toHaveTextContent("常规波动");
    expect(foldedVolAssets).toHaveAttribute("title", expect.stringContaining("USD/CNY"));
  });

  it("renders two waterfall gap chips as a compact balanced evidence row", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const compactStripBlock = css.match(/\.ca-waterfall__evidence-strip--compact \{[\s\S]*?\n\}/)?.[0] ?? "";
    const client = createApiClient({ mode: "mock" });
    const linkagePayload = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-04-10" });

    vi.spyOn(client, "getMacroBondLinkageAnalysis").mockResolvedValue({
      ...linkagePayload,
      result: {
        ...linkagePayload.result,
        environment_score: {
          ...linkagePayload.result.environment_score,
          liquidity_score: 0.52,
          rate_direction_score: -0.24,
          growth_score: 0,
          inflation_score: 0,
          composite_score: 0.28,
          contributing_factors: [
            { category: "liquidity", series_name: "Liquidity proxy", latest_value: 1.2 },
            { category: "rate", series_name: "Rate proxy", latest_value: 1.6 },
          ],
        },
      },
    });

    expect(compactStripBlock).toContain("display: flex;");

    renderPage(client);

    const gapStrip = await screen.findByTestId("cross-asset-driver-waterfall-gap-strip");

    await waitFor(() => {
      expect(gapStrip).toHaveClass("ca-waterfall__evidence-strip--compact");
      expect(gapStrip.querySelectorAll(".ca-waterfall__evidence-chip")).toHaveLength(2);
    });
    expect(screen.queryByTestId("cross-asset-driver-waterfall-gap-summary")).not.toBeInTheDocument();
    const waterfallEvidence = screen.getByTestId("cross-asset-driver-waterfall-evidence");
    expect(waterfallEvidence).toHaveTextContent("流动性代理");
    expect(waterfallEvidence).not.toHaveTextContent("Liquidity proxy");
  });

  it("keeps candidate actions visually attached to the transmission diagnostics", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const actionShellBlock = css.match(/\.cross-asset-candidate-actions \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(actionShellBlock).toContain("margin-top: -4px;");
    expect(actionShellBlock).toContain("border: 1px solid var(--ca-border-soft);");
    expect(actionShellBlock).toContain("box-shadow: none;");

    renderPage(createApiClient({ mode: "mock" }));

    const transmissionZone = await screen.findByTestId("cross-asset-zone-transmission");
    const analyticsGrid = await screen.findByTestId("cross-asset-zone-analytics-grid");
    const candidateActions = await screen.findByTestId("cross-asset-candidate-actions");

    expect(candidateActions).toHaveClass("cross-asset-candidate-actions");
    expect(transmissionZone).toContainElement(analyticsGrid);
    expect(transmissionZone).toContainElement(candidateActions);
    expect(Boolean(analyticsGrid.compareDocumentPosition(candidateActions) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("shows tail observations and supplemental review as quiet lower ledgers", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const depthBlock = css.match(/\.cross-asset-reference-depth \{[\s\S]*?\n\}/)?.[0] ?? "";
    const depthSummaryBlock = css.match(/\.cross-asset-reference-depth-summary \{[\s\S]*?\n\}/)?.[0] ?? "";
    const depthDisclosureBlock =
      css.match(
        /\.cross-asset-reference-depth \.cross-asset-observation-secondary,\n\.cross-asset-reference-depth \.cross-asset-decision-appendix \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const secondaryBlock = css.match(/^\.cross-asset-observation-secondary \{[\s\S]*?\n\}/m)?.[0] ?? "";
    const secondarySummaryBlock = css.match(/\.cross-asset-observation-secondary > summary \{[\s\S]*?\n\}/)?.[0] ?? "";
    const appendixBlock = css.match(/^\.cross-asset-decision-appendix \{[\s\S]*?\n\}/m)?.[0] ?? "";
    const appendixSummaryBlock = css.match(/\.cross-asset-decision-appendix > summary \{[\s\S]*?\n\}/)?.[0] ?? "";
    const appendixBodyBlock = css.match(/\.cross-asset-decision-appendix__body \{[\s\S]*?\n\}/)?.[0] ?? "";
    const closedSecondaryBlock =
      css.match(/\.cross-asset-observation-secondary:not\(\[open\]\) > \.cross-asset-observation-secondary-grid \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const closedAppendixBlock =
      css.match(/\.cross-asset-decision-appendix:not\(\[open\]\) > \.cross-asset-decision-appendix__body \{[\s\S]*?\n\}/)
        ?.[0] ?? "";

    expect(depthBlock).toContain("gap: 8px;");
    expect(depthSummaryBlock).toContain("grid-template-columns: minmax(0, 170px) minmax(0, 1fr);");
    expect(depthDisclosureBlock).toContain("border: 1px solid var(--ca-border-soft);");
    expect(secondaryBlock).toContain("border-top: 1px dashed var(--ca-border-muted);");
    expect(secondarySummaryBlock).toContain("display: flex;");
    expect(appendixBlock).toContain("border-top: 1px dashed var(--ca-border-muted);");
    expect(appendixSummaryBlock).toContain("display: flex;");
    expect(appendixBodyBlock).toContain("gap: 10px;");
    expect(appendixBodyBlock).toContain("padding-top: 8px;");
    expect(closedSecondaryBlock).toContain("display: none;");
    expect(closedAppendixBlock).toContain("display: none;");

    renderPage(createApiClient({ mode: "mock" }));

    const depthSummary = await screen.findByTestId("cross-asset-reference-depth-summary");
    const depthBoard = await screen.findByTestId("cross-asset-decision-display");
    const observationZone = await screen.findByTestId("cross-asset-zone-observation");
    const secondaryDisclosure = await screen.findByTestId("cross-asset-observation-secondary");
    const secondaryGrid = await screen.findByTestId("cross-asset-observation-secondary-grid");
    const appendix = await screen.findByTestId("cross-asset-decision-appendix");
    const livermoreStatus = await screen.findByTestId("cross-asset-livermore-status");
    const structuredOutput = await screen.findByTestId("cross-asset-page-output");

    expect(depthSummary).toBeInTheDocument();
    expect(depthBoard).toHaveClass("cross-asset-reference-depth");
    expect(observationZone).toContainElement(secondaryDisclosure);
    expect(secondaryDisclosure).toHaveAttribute("open");
    expect(secondaryDisclosure).toContainElement(secondaryGrid);
    expect(appendix).toHaveAttribute("open");
    expect(appendix).toContainElement(livermoreStatus);
    expect(appendix).toContainElement(structuredOutput);
    expect(Boolean(secondaryDisclosure.compareDocumentPosition(appendix) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("renders candidate actions as a homepage-aligned compact execution queue", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const shellBlock = css.match(/\.cross-asset-candidate-actions \{[\s\S]*?\n\}/)?.[0] ?? "";
    const headerBlock = css.match(/\.cross-asset-candidate-actions__header \{[\s\S]*?\n\}/)?.[0] ?? "";
    const queueBlock = css.match(/\.cross-asset-candidate-actions__queue \{[\s\S]*?\n\}/)?.[0] ?? "";
    const itemBlock = css.match(/^\.cross-asset-candidate-actions__item \{[\s\S]*?\n\}/m)?.[0] ?? "";
    const itemRowBlock =
      css.match(/\.cross-asset-candidate-actions__item \{\n  min-height:[\s\S]*?\n\}/)?.[0] ?? "";
    const lastOddBlock = css.match(/\.cross-asset-candidate-actions__item--last-odd \{[\s\S]*?\n\}/)?.[0] ?? "";
    const rankBlock = css.match(/\.cross-asset-candidate-actions__rank \{[\s\S]*?\n\}/)?.[0] ?? "";
    const actionBlock = css.match(/\.cross-asset-candidate-actions__action \{[\s\S]*?\n\}/)?.[0] ?? "";
    const reasonBlock = css.match(/\.cross-asset-candidate-actions__reason \{[\s\S]*?\n\}/)?.[0] ?? "";
    const evidenceBlock = css.match(/\.cross-asset-candidate-actions__evidence \{[\s\S]*?\n\}/)?.[0] ?? "";
    const targetBlock = css.match(/\.cross-asset-candidate-actions__tone \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(shellBlock).toContain("grid-template-rows: auto 1fr;");
    expect(shellBlock).toContain("gap: 0;");
    expect(shellBlock).toContain("background: var(--ca-border-soft);");
    expect(headerBlock).toContain("display: flex;");
    expect(headerBlock).toContain("border-bottom: 1px solid var(--ca-border-soft);");
    expect(queueBlock).toContain("display: grid;");
    expect(queueBlock).toContain("grid-template-rows: auto 1fr;");
    expect(queueBlock).toContain("background: var(--ca-border-soft);");
    expect(itemBlock).toContain("grid-template-columns: 52px minmax(176px, 0.9fr) minmax(0, 1.05fr) minmax(0, 1.1fr) 64px;");
    expect(itemRowBlock).toContain("min-height: 48px;");
    expect(itemBlock).toContain("position: relative;");
    expect(itemRowBlock).not.toContain("border-left:");
    expect(itemRowBlock).not.toContain("border-top: 2px");
    expect(css).toContain(".cross-asset-candidate-actions__item::before");
    expect(lastOddBlock).toContain("grid-column: auto;");
    expect(rankBlock).toContain("display: inline-grid;");
    expect(css).toContain(".cross-asset-candidate-actions__columns");
    expect(actionBlock).toContain("font-weight: 800;");
    expect(reasonBlock).toContain("text-overflow: ellipsis;");
    expect(evidenceBlock).toContain("text-overflow: ellipsis;");
    expect(targetBlock).toContain("border-radius: var(--ib-radius, 2px);");

    renderPage(createApiClient({ mode: "mock" }));

    const candidateActions = await screen.findByTestId("cross-asset-candidate-actions");
    const header = within(candidateActions).getByText("执行台账");
    const queue = within(candidateActions).getByRole("list", { name: "市场候选动作队列" });
    const actionItems = within(queue).getAllByRole("listitem");

    expect(candidateActions.querySelector("table")).not.toBeInTheDocument();
    expect(header).toBeInTheDocument();
    expect(actionItems.length).toBeGreaterThanOrEqual(3);
    expect(actionItems[0].querySelector(".cross-asset-candidate-actions__rank")).toHaveTextContent("P1");
    expect(actionItems[0].querySelector(".cross-asset-candidate-actions__action")).toBeInTheDocument();
    expect(actionItems[0].querySelector(".cross-asset-candidate-actions__reason")).toBeInTheDocument();
    expect(actionItems[0].querySelector(".cross-asset-candidate-actions__evidence")).toBeInTheDocument();
    expect(actionItems[0].querySelector(".cross-asset-candidate-actions__tone")).toBeInTheDocument();
  });

  it("spans an odd final candidate action across the desktop queue", () => {
    const rows: CrossAssetCandidateAction[] = [
      { action: "动作一", reason: "理由一", evidence: "证据一", tone: "warning" },
      { action: "动作二", reason: "理由二", evidence: "证据二", tone: "bull" },
      { action: "动作三", reason: "理由三", evidence: "证据三", tone: "warning" },
    ];

    render(<MarketCandidateActions rows={rows} />);

    const candidateActions = screen.getByTestId("cross-asset-candidate-actions");
    const queue = within(candidateActions).getByRole("list", { name: "市场候选动作队列" });
    const actionItems = within(queue).getAllByRole("listitem");

    expect(actionItems).toHaveLength(3);
    expect(actionItems[2]).toHaveClass("cross-asset-candidate-actions__item--last-odd");
  });

  it("separates the desktop observation chapter and consolidates trend chart controls", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const observationZoneBlock = css.match(/\.cross-asset-zone-observation \{[\s\S]*?\n\}/)?.[0] ?? "";
    const observationTitleBlock = css.match(/\.cross-asset-zone-observation \.cross-asset-decision-zone__title \{[\s\S]*?\n\}/)?.[0] ?? "";
    const toolbarBlock = css.match(/\.cross-asset-trend-panel__toolbar \{[\s\S]*?\n\}/)?.[0] ?? "";
    const methodBlock = css.match(/\.cross-asset-trend-panel__method \{[\s\S]*?\n\}/)?.[0] ?? "";
    const chartBlock = css.match(/\.cross-asset-trend-chart \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(observationZoneBlock).toContain("margin-top: 12px;");
    expect(observationZoneBlock).toContain("padding-top: 14px;");
    expect(observationZoneBlock).toContain("border-top: 1px solid var(--ca-border-soft);");
    expect(observationTitleBlock).toContain("margin-bottom: 6px;");
    expect(toolbarBlock).toContain("display: flex;");
    expect(toolbarBlock).toContain("justify-content: space-between;");
    expect(methodBlock).toContain("margin: 0;");
    expect(methodBlock).toContain("flex: 0 0 auto;");
    expect(chartBlock).toContain("overflow: hidden;");

    renderPage(createApiClient({ mode: "mock" }));

    const observationZone = await screen.findByTestId("cross-asset-zone-observation");
    const trendPanel = await screen.findByTestId("cross-asset-trend-panel");
    const toolbar = trendPanel.querySelector(".cross-asset-trend-panel__toolbar");
    const groups = await screen.findByTestId("cross-asset-trend-groups");
    const method = trendPanel.querySelector(".cross-asset-trend-panel__method");
    await waitFor(() => {
      expect(trendPanel.querySelector(".cross-asset-trend-chart")).toBeInTheDocument();
    });

    expect(observationZone).toHaveClass("cross-asset-zone-observation");
    expect(toolbar).toBeInTheDocument();
    expect(toolbar).toContainElement(groups);
    expect(toolbar).toContainElement(method as HTMLElement);
  });

  it("keeps NCD proxy evidence visible as a funding evidence footer under the action queue", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const proxyBlock = css.match(/\.cross-asset-ncd-proxy \{[\s\S]*?\n\}/)?.[0] ?? "";
    const summaryBlock = css.match(/\.cross-asset-ncd-proxy > summary \{[\s\S]*?\n\}/)?.[0] ?? "";
    const closedBlock =
      css.match(/\.cross-asset-ncd-proxy:not\(\[open\]\) > \.cross-asset-ncd-proxy__body \{[\s\S]*?\n\}/)?.[0] ??
      "";
    const bodyBlock = css.match(/\.cross-asset-ncd-proxy__body \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(proxyBlock).toContain("margin-top: -2px;");
    expect(proxyBlock).toContain("box-shadow: none;");
    expect(summaryBlock).toContain("display: flex;");
    expect(summaryBlock).toContain("min-height: 40px;");
    expect(closedBlock).toContain("display: none;");
    expect(bodyBlock).toContain("border-top: 1px dashed var(--ca-border-muted);");

    renderPage(createApiClient({ mode: "mock" }));

    const candidateActions = await screen.findByTestId("cross-asset-candidate-actions");
    const ncdProxy = await screen.findByTestId("cross-asset-ncd-proxy");
    const warning = screen.getByTestId("cross-asset-ncd-proxy-warning");
    const rows = screen.getByTestId("cross-asset-ncd-proxy-rows");

    expect(ncdProxy.tagName.toLowerCase()).toBe("details");
    expect(ncdProxy).toHaveAttribute("open");
    expect(ncdProxy).toContainElement(warning);
    expect(ncdProxy).toContainElement(rows);
    expect(Boolean(candidateActions.compareDocumentPosition(ncdProxy) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("breaks the desktop transmission rail out of five equal compressed columns", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const flatTransmissionGridBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes__grid \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatTransmissionCardBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes__card \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const scopedTransmissionGridBlock =
      css.match(
        /\.cross-asset-reference-depth \.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes__grid \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const scopedTransmissionCardBlock =
      css.match(
        /\.cross-asset-reference-depth \.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes__card \{[\s\S]*?\n\}/,
      )?.[0] ?? "";

    expect(flatTransmissionGridBlock).toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
    expect(flatTransmissionGridBlock).not.toContain("repeat(5, minmax(0, 1fr));");
    expect(flatTransmissionCardBlock).toContain("min-height: 132px;");
    expect(flatTransmissionCardBlock).toContain("padding: 11px 12px;");
    expect(scopedTransmissionGridBlock).toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
    expect(scopedTransmissionGridBlock).not.toContain("grid-template-columns: 1fr;");
    expect(scopedTransmissionCardBlock).toContain("min-height: 132px;");
    expect(scopedTransmissionCardBlock).toContain("border-left: 3px solid var(--ca-accent);");
  });

  it("keeps the desktop transmission cards summary-first instead of report-like", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const flatTransmissionBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatTransmissionCardBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes__card \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const summaryBlock =
      css.match(
        /\.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes__summary \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const metaBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-transmission-axes__meta \{[\s\S]*?\n\}/)
        ?.[0] ?? "";

    expect(flatTransmissionBlock).toContain("gap: 8px;");
    expect(flatTransmissionCardBlock).toContain("gap: 7px;");
    expect(summaryBlock).toContain("display: -webkit-box;");
    expect(summaryBlock).toContain("-webkit-line-clamp: 2;");
    expect(metaBlock).toContain("display: -webkit-box;");
    expect(metaBlock).toContain("overflow: hidden;");
    expect(metaBlock).toContain("overflow-wrap: anywhere;");
    expect(metaBlock).toContain("white-space: normal;");
    expect(metaBlock).toContain("-webkit-line-clamp: 1;");
  });

  it("keeps the secondary driver factors as a quiet compact strip", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const driversGridBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-drivers-page__drivers-grid--flat \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const driverCellBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-drivers-page__driver-cell \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const driverListBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-drivers-page__driver-list \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const driverItemBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-drivers-page__driver-list li \{[\s\S]*?\n\}/)
        ?.[0] ?? "";

    expect(driversGridBlock).toContain("grid-template-columns: repeat(4, minmax(0, 1fr));");
    expect(driverCellBlock).toContain("padding: 9px 10px;");
    expect(driverCellBlock).toContain("background: transparent;");
    expect(driverCellBlock).toContain("border-left:");
    expect(driverListBlock).toContain("gap: 3px;");
    expect(driverItemBlock).toContain("display: -webkit-box;");
    expect(driverItemBlock).toContain("-webkit-line-clamp: 1;");
  });

  it("keeps desktop asset analysis judgment-first instead of one oversized evidence card", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const detailsBlock =
      css.match(/\.cross-asset-class-analysis__details \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const detailsSummaryBlock =
      css.match(/\.cross-asset-class-analysis__details > summary \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const detailsClosedBlock =
      css.match(/\.cross-asset-class-analysis__details:not\(\[open\]\) > \.cross-asset-class-analysis__details-body \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const detailsBodyBlock =
      css.match(/\.cross-asset-class-analysis__details-body \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatCardsBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__cards \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatFirstCardBlock =
      css.match(
        /\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__cards > \.cross-asset-class-analysis__card:first-child \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const flatCardBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__card \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatLineBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__line \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatLineExplanationBlock =
      css.match(
        /\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__line-explanation \{[\s\S]*?\n\}/,
      )?.[0] ?? "";

    expect(detailsBlock).toContain("border-top: 1px dashed var(--ca-border-muted);");
    expect(detailsSummaryBlock).toContain("display: flex;");
    expect(detailsClosedBlock).toContain("display: none;");
    expect(detailsBodyBlock).toContain("grid-template-columns: minmax(0, 1fr) minmax(280px, 320px);");
    expect(flatCardsBlock).toContain("grid-template-rows: auto;");
    expect(flatFirstCardBlock).toContain("grid-row: auto;");
    expect(flatCardBlock).toContain("gap: 8px;");
    expect(flatCardBlock).toContain("padding: 12px;");
    expect(flatLineBlock).toContain("padding: 7px 0 0;");
    expect(flatLineExplanationBlock).toContain("display: -webkit-box;");
    expect(flatLineExplanationBlock).toContain("-webkit-line-clamp: 1;");

    renderPage(createApiClient({ mode: "mock" }));

    const analysis = screen.getByTestId("cross-asset-asset-class-analysis");
    const judgment = screen.getByTestId("cross-asset-asset-class-judgment");
    const details = screen.getByTestId("cross-asset-asset-class-details");
    const stockCard = screen.getByTestId("cross-asset-asset-analysis-stock");

    expect(analysis).toContainElement(judgment);
    expect(analysis).toContainElement(details);
    expect(details).toHaveAttribute("open");
    expect(details).toContainElement(stockCard);
    expect(Boolean(judgment.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("keeps desktop equity evidence as a compact supporting digest", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const flatEvidenceBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__evidence \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatEvidenceItemBlock =
      css.match(
        /\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__evidence-item \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const flatEvidenceSmallBlock =
      css.match(
        /\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__evidence-item small \{[\s\S]*?\n\}/,
      )?.[0] ?? "";

    expect(flatEvidenceBlock).toContain("grid-template-columns: repeat(2, minmax(0, 1fr));");
    expect(flatEvidenceBlock).toContain("gap: 6px 10px;");
    expect(flatEvidenceItemBlock).toContain("grid-template-columns: minmax(0, 1fr) auto;");
    expect(flatEvidenceItemBlock).toContain("min-width: 0;");
    expect(flatEvidenceSmallBlock).toContain("overflow: hidden;");
    expect(flatEvidenceSmallBlock).toContain("text-overflow: ellipsis;");
    expect(flatEvidenceSmallBlock).toContain("white-space: nowrap;");
  });

  it("promotes the bond transmission judgment above asset evidence on desktop", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const flatJudgmentBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__judgment \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const flatJudgmentItemsBlock =
      css.match(
        /\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__judgment-items \{[\s\S]*?\n\}/,
      )?.[0] ?? "";
    const flatJudgmentItemDetailBlock =
      css.match(
        /\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__judgment-item p \{[\s\S]*?\n\}/,
      )?.[0] ?? "";

    expect(flatJudgmentBlock).toContain("grid-column: 1 / -1;");
    expect(flatJudgmentBlock).toContain("order: -1;");
    expect(flatJudgmentBlock).toContain("padding: 12px;");
    expect(flatJudgmentItemsBlock).toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
    expect(flatJudgmentItemDetailBlock).toContain("display: -webkit-box;");
    expect(flatJudgmentItemDetailBlock).toContain("-webkit-line-clamp: 2;");
  });

  it("keeps transmission impact cues visually subordinate to status and action evidence", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const impactBlock = css.match(/\.cross-asset-transmission-axes__impact \{[\s\S]*?\n\}/)?.[0] ?? "";
    const pendingCardBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__pending-card \{[\s\S]*?\n\}/)
        ?.[0] ?? "";
    const pendingLineBlock =
      css.match(/\.cross-asset-decision-zone__body--flat \.cross-asset-class-analysis__pending-line \{[\s\S]*?\n\}/)
        ?.[0] ?? "";

    expect(impactBlock).toContain("border-left:");
    expect(impactBlock).toContain("background:");
    expect(pendingCardBlock).toContain("padding: 12px;");
    expect(pendingCardBlock).toContain("gap: 8px;");
    expect(pendingLineBlock).toContain("padding: 6px 0;");

    renderPage(createApiClient({ mode: "mock" }));

    const globalRatesAxis = await screen.findByTestId("cross-asset-transmission-axis-global_rates");
    expect(globalRatesAxis.querySelector(".cross-asset-transmission-axes__impact")).toBeInTheDocument();
  });

  it("compresses missing-heavy waterfall evidence instead of repeating gap labels on every bar", async () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");

    expect(css).toContain(".ca-waterfall__gap-summary");
    expect(css).toContain(".ca-waterfall__chart--compact-gaps");

    renderPage(createApiClient({ mode: "mock" }));

    const waterfall = await screen.findByTestId("cross-asset-driver-waterfall");
    const chart = waterfall.querySelector(".ca-waterfall__chart--compact-gaps");
    const zeroLine = chart?.querySelector(".ca-waterfall__zero-line") as HTMLElement | null;
    const gapSummary = await screen.findByTestId("cross-asset-driver-waterfall-gap-summary");
    const gapStrip = await screen.findByTestId("cross-asset-driver-waterfall-gap-strip");
    const compactChartBlock = css.match(/\.ca-waterfall__chart--compact-gaps \{[\s\S]*?\n\}/)?.[0] ?? "";
    const compactZeroLineBlock =
      css.match(/\.ca-waterfall__chart--compact-gaps \.ca-waterfall__zero-line \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(gapSummary).toHaveTextContent("证据缺口");
    expect(gapSummary).toHaveTextContent("4 项待补");
    expect(gapSummary).toHaveTextContent("当前按 0 参与汇总");
    expect(chart).toBeInTheDocument();
    expect(compactChartBlock).toContain("height: 96px;");
    expect(compactChartBlock).toContain("padding-bottom: 28px;");
    expect(compactZeroLineBlock).toContain("bottom: 64px;");
    expect(zeroLine).not.toHaveAttribute("style");
    expect(within(chart as HTMLElement).queryAllByText("缺数据")).toHaveLength(0);
    expect(within(chart as HTMLElement).queryAllByText("样本不足")).toHaveLength(0);
    expect(gapStrip).toHaveTextContent("流动性");
    expect(gapStrip).toHaveTextContent("通胀扰动");
  });

  it("keeps waterfall value labels separated from bar status chips on desktop", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const chartBlock = css.match(/\.ca-waterfall__chart \{[\s\S]*?\n\}/)?.[0] ?? "";
    const barGroupBlock = css.match(/\.ca-waterfall__bar-group \{[\s\S]*?\n\}/)?.[0] ?? "";
    const valueBlock = css.match(/\.ca-waterfall__bar-value \{[\s\S]*?\n\}/)?.[0] ?? "";
    const belowValueBlock = css.match(/\.ca-waterfall__bar-value--below \{[\s\S]*?\n\}/)?.[0] ?? "";
    const labelBlock = css.match(/\.ca-waterfall__bar-label \{[\s\S]*?\n\}/)?.[0] ?? "";
    const statusBlock = css.match(/\.ca-waterfall__bar-status \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(chartBlock).toContain("padding-bottom: 68px;");
    expect(barGroupBlock).toContain("padding-top: 22px;");
    expect(valueBlock).toContain("line-height: 1;");
    expect(valueBlock).toContain("z-index: 2;");
    expect(belowValueBlock).toContain("top: calc(100% + 9px);");
    expect(labelBlock).toContain("bottom: -28px;");
    expect(statusBlock).toContain("bottom: -66px;");
    expect(statusBlock).toContain("z-index: 1;");
  });

  it("gives negative waterfall bars their own deeper label and status lanes", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const negativeLabelBlock =
      css.match(/\.ca-waterfall__bar--negative \.ca-waterfall__bar-label \{[\s\S]*?\n\}/)?.[0] ?? "";
    const negativeStatusBlock =
      css.match(/\.ca-waterfall__bar--negative \.ca-waterfall__bar-status \{[\s\S]*?\n\}/)?.[0] ?? "";

    expect(negativeLabelBlock).toContain("bottom: -44px;");
    expect(negativeStatusBlock).toContain("bottom: -82px;");
  });

  it("contains the desktop correlation matrix without page-level horizontal spill", () => {
    const css = readFileSync(CROSS_ASSET_DRIVERS_CSS_PATH, "utf8");
    const panelBlock = css.match(/\.ca-correlation \{[\s\S]*?\n\}/)?.[0] ?? "";
    const summaryBlock = css.match(/\.ca-correlation__summary \{[\s\S]*?\n\}/)?.[0] ?? "";
    const summaryCardBlock = css.match(/\.ca-correlation__summary-card \{[\s\S]*?\n\}/)?.[0] ?? "";
    const detailsBlock = css.match(/\.ca-correlation__details \{[\s\S]*?\n\}/)?.[0] ?? "";
    const wrapBlock = css.match(/\.ca-correlation__matrix-wrap \{[\s\S]*?\n\}/)?.[0] ?? "";
    const wrapFadeBlock = css.match(/\.ca-correlation__matrix-wrap::after \{[\s\S]*?\n\}/)?.[0] ?? "";
    const gridBlock = css.match(/\.ca-correlation__grid \{[\s\S]*?\n\}/)?.[0] ?? "";
    const compactGridBlock = css.match(/\.ca-correlation__grid--compact \{[\s\S]*?\n\}/)?.[0] ?? "";
    const cellBlock = css.match(/\.ca-correlation__cell \{[\s\S]*?\n\}/)?.[0] ?? "";
    const headerBlock = css.match(/\.ca-correlation__cell--header \{[\s\S]*?\n\}/)?.[0] ?? "";
    const observationDesktopBlock =
      css.match(/@media \(min-width: 1000px\) \{[\s\S]*?\.cross-asset-observation-support-grid \{[\s\S]*?\n  \}/)?.[0] ??
      "";

    expect(panelBlock).toContain("overflow: hidden;");
    expect(panelBlock).toContain("position: relative;");
    expect(summaryBlock).toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
    expect(summaryCardBlock).toContain("border-left: 3px solid");
    expect(detailsBlock).toContain("border-top: 1px dashed var(--ca-border-muted);");
    expect(css).toContain(".ca-correlation__matrix-wrap::after");
    expect(wrapBlock).toContain("max-width: 100%;");
    expect(wrapBlock).toContain("overflow-x: hidden;");
    expect(wrapBlock).toContain("scrollbar-width: thin;");
    expect(wrapFadeBlock).toContain("position: absolute;");
    expect(wrapFadeBlock).toContain("top: 0;");
    expect(wrapFadeBlock).toContain("bottom: 4px;");
    expect(wrapFadeBlock).not.toContain("position: sticky;");
    expect(wrapFadeBlock).not.toContain("margin-top:");
    expect(compactGridBlock).toContain("width: 100%;");
    expect(compactGridBlock).toContain("min-width: 0;");
    expect(gridBlock).toContain("min-width: max-content;");
    expect(cellBlock).toContain("min-width: 0;");
    expect(headerBlock).toContain("min-width: 0;");
    expect(observationDesktopBlock).toContain(
      "grid-template-columns: minmax(320px, 0.78fr) minmax(0, 1.22fr);",
    );
  });

  it("shows the most important correlation pairs before the full matrix", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const heatmap = await screen.findByTestId("cross-asset-correlation-heatmap");
    const summary = await screen.findByTestId("cross-asset-correlation-summary");
    const details = await screen.findByTestId("cross-asset-correlation-details");
    const matrixWrap = await screen.findByTestId("cross-asset-correlation-matrix-wrap");

    expect(heatmap).toContainElement(summary);
    expect(heatmap).toContainElement(details);
    expect(details.tagName.toLowerCase()).toBe("details");
    expect(details).toHaveAttribute("open");
    expect(details).toContainElement(matrixWrap);
    expect(summary.querySelectorAll(".ca-correlation__summary-card")).toHaveLength(3);
    expect(summary).toHaveTextContent("最强共振");
    expect(summary).toHaveTextContent("最强背离");
    expect(summary).toHaveTextContent("关注组合");
    expect(Boolean(summary.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it("uses compact correlation matrix columns so desktop can inspect it without page spill", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const matrixGrid = await waitFor(() => {
      const grid = screen.getByTestId("cross-asset-correlation-matrix-wrap").querySelector(".ca-correlation__grid");
      expect(grid).toBeInTheDocument();
      return grid as HTMLElement;
    });

    expect(matrixGrid).toHaveClass("ca-correlation__grid--compact");
    expect(matrixGrid.getAttribute("style")).toContain("grid-template-columns: 48px repeat(");
    expect(matrixGrid.getAttribute("style")).toContain("minmax(30px, 1fr)");
  });

  it("groups cross-asset evidence into a compact factor ledger with heatmap follow-up", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const evidenceZone = await screen.findByTestId("cross-asset-zone-evidence");
    const evidenceTape = await screen.findByTestId("cross-asset-evidence-tape");
    const evidenceDetails = await screen.findByTestId("cross-asset-evidence-details");
    const evidenceGroups = await screen.findByTestId("cross-asset-evidence-groups");
    const fullKpiBand = await screen.findByTestId("cross-asset-kpi-band");
    const kpiLedgerTable = await screen.findByTestId("cross-asset-kpi-ledger-table");
    const linkageHeatmapLedger = await screen.findByTestId("cross-asset-linkage-heatmap-ledger");
    const heatmap = evidenceZone.querySelector(".cross-asset-drivers-page__heatmap");

    expect(evidenceZone).toContainElement(evidenceTape);
    expect(evidenceZone).toContainElement(evidenceDetails);
    expect(evidenceDetails).toHaveAttribute("open");
    expect(evidenceZone).toContainElement(evidenceGroups);
    expect(evidenceGroups).toContainElement(fullKpiBand);
    expect(evidenceTape).toHaveTextContent("债券锚");
    expect(evidenceTape).toHaveTextContent("风险偏好");
    expect(evidenceTape).toHaveTextContent("通胀脉冲");
    expect(evidenceTape).toHaveTextContent("外部约束");
    expect(evidenceTape).toHaveTextContent("因子");
    expect(evidenceTape).toHaveTextContent("当前");
    expect(evidenceTape).toHaveTextContent("变化");
    expect(evidenceTape).toHaveTextContent("方向");
    expect(evidenceTape).toHaveTextContent("来源");
    expect(evidenceTape).toHaveAttribute("aria-label", "关键因子矩阵");
    expect(evidenceTape.querySelectorAll("tbody tr")).toHaveLength(4);
    expect(evidenceDetails).toHaveAttribute("aria-label", "指标明细与相关性热力");
    expect(evidenceGroups).toHaveTextContent("指标矩阵加工台");
    expect(evidenceGroups).toHaveTextContent("四列因子、分位、来源一次扫完");
    expect(fullKpiBand).toContainElement(kpiLedgerTable);
    expect(fullKpiBand.querySelector(".cross-asset-drivers-page__mini-kpi")).not.toBeInTheDocument();
    expect(kpiLedgerTable.querySelectorAll(".cross-asset-evidence-factor")).toHaveLength(4);
    expect(kpiLedgerTable.querySelector(".cross-asset-evidence-factor--rates_liquidity")).toBeInTheDocument();
    expect(kpiLedgerTable.querySelector(".cross-asset-evidence-factor--equity_risk")).toBeInTheDocument();
    expect(kpiLedgerTable.querySelector(".cross-asset-evidence-factor__source")).toBeInTheDocument();
    expect(kpiLedgerTable).toHaveTextContent("分位");
    expect(kpiLedgerTable).toHaveTextContent("源");
    expect(kpiLedgerTable).toHaveTextContent("10Y国债");
    expect(kpiLedgerTable.querySelectorAll("tbody tr").length).toBeGreaterThanOrEqual(10);
    expect(linkageHeatmapLedger).toHaveTextContent("相关性热力");
    expect(linkageHeatmapLedger).toContainElement(heatmap as HTMLElement);
    expect(linkageHeatmapLedger.querySelector(".cross-asset-linkage-heatmap-ledger__legend")).toBeInTheDocument();
    expect(linkageHeatmapLedger.querySelectorAll(".cross-asset-linkage-heatmap-ledger__legend-item")).toHaveLength(3);
    expect(linkageHeatmapLedger.querySelector(".cross-asset-linkage-heatmap-ledger__pair strong")).toBeInTheDocument();
    expect(linkageHeatmapLedger.querySelector(".cross-asset-linkage-heatmap-ledger__cell")).toBeInTheDocument();
    expect(evidenceGroups.querySelectorAll(".cross-asset-evidence-group")).toHaveLength(4);
    expect(screen.getByTestId("cross-asset-evidence-group-rates_liquidity")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-evidence-group-equity_risk")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-evidence-group-commodity_inflation")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-evidence-group-fx_spread")).toBeInTheDocument();
    expect(Boolean(evidenceGroups.compareDocumentPosition(heatmap!) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    await waitFor(() => {
      const firstLinkagePair = heatmap?.querySelector("tbody tr td:first-child");
      expect(firstLinkagePair?.textContent ?? "").toContain("→");
      expect(firstLinkagePair?.textContent ?? "").not.toContain("->");
      expect(firstLinkagePair?.textContent ?? "").not.toContain("暂无治理后的联动排序");
    });
  });

  it("exposes the first-screen action rail as a labelled complementary region", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const actionRail = await screen.findByTestId("cross-asset-action-rail");
    const title = actionRail.querySelector("#cross-asset-action-rail-title");

    expect(actionRail).toHaveAttribute("aria-labelledby", "cross-asset-action-rail-title");
    expect(title).toHaveTextContent("组合动作");
  });

  it("uses a styled signal mark instead of emoji for the market regime indicator", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const regime = await screen.findByTestId("cross-asset-regime-indicator");
    const mark = regime.querySelector(".ca-regime__signal");

    expect(mark).toBeInTheDocument();
    expect(regime).not.toHaveTextContent(/[🟢🔴🟠🔵🟣⚪]/u);
  });

  it("renders first-screen investment research judgments from backend additive fields", async () => {
    const client = createApiClient({ mode: "mock" });
    const latestPayload = await client.getChoiceMacroLatest();
    const baseCsi300 = latestPayload.result.series.find((point) => point.series_id === "CA.CSI300")!;
    vi.spyOn(client, "getChoiceMacroLatest").mockResolvedValue({
      ...latestPayload,
      result_meta: {
        ...latestPayload.result_meta,
        vendor_status: "vendor_unavailable",
      },
      result: {
        ...latestPayload.result,
        series: [
          ...latestPayload.result.series.map((point) =>
            point.series_id === "CA.CSI300"
              ? {
                  ...point,
                  trade_date: "2026-02-28",
                }
              : point,
          ),
          {
            ...baseCsi300,
            series_id: "CA.CSI300_PE",
            series_name: "沪深300市盈率",
            value_numeric: 14.58,
            unit: "x",
            refresh_tier: "fallback",
            latest_change: 0.16,
          },
          {
            ...baseCsi300,
            series_id: "CA.MEGA_CAP_WEIGHT",
            series_name: "沪深300前十大权重",
            trade_date: "2026-04-01",
            value_numeric: 23.5367,
            unit: "%",
            latest_change: 0.2,
          },
          {
            ...baseCsi300,
            series_id: "CA.MEGA_CAP_TOP5_WEIGHT",
            series_name: "沪深300前五大权重",
            trade_date: "2026-04-01",
            value_numeric: 15.532,
            unit: "%",
            latest_change: 0.1,
          },
        ],
      },
    });
    const linkagePayload = await client.getMacroBondLinkageAnalysis({ reportDate: "2026-04-10" });

    vi.spyOn(client, "getMacroBondLinkageAnalysis").mockResolvedValue({
      ...linkagePayload,
      result: {
        ...linkagePayload.result,
        research_views: [
          {
            key: "duration",
            status: "ready",
            stance: "bullish",
            confidence: "high",
            summary: "Duration view favors adding exposure.",
            affected_targets: ["rates", "ncd", "high_grade_credit"],
            evidence: ["Liquidity remains supportive."],
          },
          {
            key: "curve",
            status: "ready",
            stance: "barbell",
            confidence: "medium",
            summary: "Curve view prefers front-end carry with selective extension.",
            affected_targets: ["rates", "ncd"],
            evidence: ["Funding stays loose."],
          },
          {
            key: "credit",
            status: "ready",
            stance: "selective",
            confidence: "medium",
            summary: "Credit view stays focused on high grade.",
            affected_targets: ["high_grade_credit"],
            evidence: ["Spread beta remains controlled."],
          },
          {
            key: "instrument",
            status: "ready",
            stance: "barbell",
            confidence: "medium",
            summary: "Instrument view prefers rates plus high-grade credit.",
            affected_targets: ["rates", "ncd", "high_grade_credit"],
            evidence: ["Cross-asset evidence is mixed but constructive."],
          },
        ],
        transmission_axes: [
          {
            axis_key: "global_rates",
            status: "ready",
            stance: "restrictive",
            summary: "Global rates cap aggressive long-end chasing.",
            impacted_views: ["duration", "curve"],
            required_series_ids: ["UST10Y"],
            warnings: [],
          },
          {
            axis_key: "equity_bond_spread",
            status: "ready",
            stance: "conflicted",
            summary: "CSI300 equity-bond spread is 5.10ppt with CSI300 move -0.35%.",
            impacted_views: ["duration", "credit"],
            required_series_ids: ["tushare.index.000300.SH.daily", "tushare.index.000300.SH.dailybasic"],
            warnings: [],
          },
          {
            axis_key: "mega_cap_equities",
            status: "ready",
            stance: "neutral",
            summary: "CSI300 top10 weight concentration is 23.54% (top5 15.53%).",
            impacted_views: ["credit", "instrument"],
            required_series_ids: ["tushare.index.000300.SH.weight"],
            warnings: [],
          },
        ],
      },
    });

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(await screen.findByTestId("cross-asset-ncd-proxy")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-ncd-proxy-warning")).toBeInTheDocument();
    await waitFor(() => {
      const warning = screen.getByTestId("cross-asset-ncd-proxy-warning");
      expect(warning).toHaveTextContent(/不是真实 NCD 发行矩阵/);
      expect(warning).toHaveTextContent(/Tushare Shibor/);
    });
    expect(await screen.findByText("久期判断偏积极，可讨论增加敞口。")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-transmission-axes")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-card-duration")).toHaveTextContent(
      "久期判断偏积极，可讨论增加敞口。",
    );
    expect(screen.getByTestId("cross-asset-research-card-instrument")).toHaveTextContent(
      "品种判断偏好利率与高等级信用。",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent(
      "全球利率制约激进拉长久期。",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent("已就绪");
    expect(screen.getByTestId("cross-asset-transmission-axis-global_rates")).toHaveTextContent("偏紧");
    expect(screen.getByTestId("cross-asset-transmission-axis-equity_bond_spread")).toHaveTextContent(
      "沪深300股债利差",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-equity_bond_spread")).not.toHaveTextContent(
      "CSI300 equity-bond spread",
    );
    expect(screen.getByTestId("cross-asset-transmission-axis-mega_cap_equities")).toHaveTextContent("23.54%");
    const judgment = screen.getByTestId("cross-asset-asset-class-judgment");
    expect(judgment).not.toHaveTextContent("CSI300 equity-bond spread is 5.10ppt");
    expect(judgment).toHaveTextContent("股票通道");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-stock")).toHaveTextContent("股票分析");
    expect(screen.getByTestId("cross-asset-asset-analysis-commodities")).toHaveTextContent("大宗商品");
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).toHaveTextContent("期权");
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).toHaveTextContent("\u5f85\u63a5\u5165");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("\u8de8\u8d44\u4ea7\u7ed3\u8bba");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("\u5f85\u63a5\u5165\u6e05\u5355");
    expect(screen.getByTestId("cross-asset-asset-class-judgment")).toHaveTextContent("\u503a\u5238\u4f20\u5bfc\u5224\u65ad");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("Choice");
    expect(screen.getByTestId("cross-asset-asset-class-analysis")).toHaveTextContent("Tushare");
    expect(screen.getByTestId("cross-asset-status-flags")).toHaveTextContent("来源受限");
    const stockBroadIndex = screen.getByTestId("cross-asset-asset-analysis-stock-broad_index");
    expect(stockBroadIndex).toBeInTheDocument();
    expect(stockBroadIndex).toHaveTextContent("来源受限");
    expect(stockBroadIndex).not.toHaveTextContent("EMM01843735");
    expect(stockBroadIndex.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "EMM01843735",
    );
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-valuation_spread")).toHaveTextContent("14.58");
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toHaveTextContent("23.54%");
    expect(screen.getByTestId("cross-asset-asset-analysis-stock-mega_cap_weight")).toHaveTextContent("15.53%");
    const equityEvidence = screen.getByTestId("cross-asset-equity-evidence");
    expect(equityEvidence).toHaveTextContent("EMM01843735");
    expect(equityEvidence).toHaveTextContent("CA.CSI300_PE");
    expect(equityEvidence).toHaveTextContent("CA.MEGA_CAP_WEIGHT");
    expect(equityEvidence).toHaveTextContent("CA.MEGA_CAP_TOP5_WEIGHT");
    expect(equityEvidence).toHaveTextContent("指数");
    expect(equityEvidence).not.toHaveTextContent("index");
    expect(equityEvidence).toHaveTextContent("倍");
    expect(equityEvidence).not.toHaveTextContent(" x ");
    expect(equityEvidence).toHaveTextContent("%");
    expect(screen.getByTestId("cross-asset-equity-evidence-broad_index")).toHaveTextContent("来源受限");
    expect(screen.getByTestId("cross-asset-equity-evidence-csi300_pe")).toHaveTextContent("降级");
    const commoditiesEnergy = screen.getByTestId("cross-asset-asset-analysis-commodities-energy");
    expect(commoditiesEnergy).toBeInTheDocument();
    expect(commoditiesEnergy).not.toHaveTextContent("CA.BRENT");
    expect(commoditiesEnergy.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "CA.BRENT",
    );
    const commoditiesFerrous = screen.getByTestId("cross-asset-asset-analysis-commodities-ferrous");
    expect(commoditiesFerrous).toBeInTheDocument();
    expect(commoditiesFerrous).not.toHaveTextContent("CA.STEEL");
    expect(commoditiesFerrous.querySelector(".cross-asset-class-analysis__line-source")?.getAttribute("title")).toContain(
      "CA.STEEL",
    );
    expect(screen.getByTestId("cross-asset-asset-analysis-commodities-nonferrous")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-equity_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-equity_options")).toHaveTextContent("Choice");
    expect(screen.getByTestId("cross-asset-asset-analysis-options-commodity_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options-rates_bond_options")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-asset-analysis-options")).not.toHaveTextContent("Evidence:");
  });

  it("surfaces incomplete A-share Livermore strategy status on the cross-asset page", async () => {
    const client = createApiClient({ mode: "mock" });
    const livermorePayload = await client.getLivermoreStrategy({ asOfDate: "2026-04-30" });
    const resultWithoutRiskExit = {
      ...livermorePayload.result,
      rule_readiness: livermorePayload.result.rule_readiness.map((rule) =>
        rule.key === "risk_exit"
          ? {
              ...rule,
              status: "blocked" as const,
              summary: "Risk and exit output is blocked because the position snapshot has no ACTIVE rows.",
              missing_inputs: ["positions", "entry_cost", "bars_since_entry", "close_history"],
            }
          : rule,
      ),
      supported_outputs: ["market_gate", "sector_rank", "stock_candidates"] as LivermoreOutputKey[],
      unsupported_outputs: [
        {
          key: "risk_exit" as const,
          reason: "livermore_position_snapshot has no ACTIVE A-share rows for as_of_date 2026-04-30.",
        },
      ],
    };
    delete resultWithoutRiskExit.risk_exit;
    vi.spyOn(client, "getLivermoreStrategy").mockResolvedValue({
      ...livermorePayload,
      result: resultWithoutRiskExit,
    });

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-status");
    await waitFor(() => {
      expect(client.getLivermoreStrategy).toHaveBeenCalled();
      expect(panel).toHaveTextContent("市场门控");
    });
    expect(panel).toHaveTextContent("A股策略状态");
    expect(panel).toHaveTextContent("个股候选");
    expect(panel).toHaveTextContent("风险退出");
    expect(panel).toHaveTextContent("缺持仓快照");
    expect(panel).toHaveTextContent("持仓快照输入未闭合");
    expect(panel).toHaveTextContent("持仓快照缺失，暂无可执行风险退出样本。");
    expect(panel).not.toHaveTextContent("position snapshot");
    expect(panel).not.toHaveTextContent("livermore_position_snapshot");
    expect(screen.getByTestId("cross-asset-livermore-risk-exit")).toHaveTextContent("未闭环");
  });

  it("localizes Livermore readiness summaries on the strategy status panel", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const panel = await screen.findByTestId("cross-asset-livermore-status");
    await waitFor(() => {
      expect(panel).toHaveTextContent("市场门控");
    });
    expect(panel).toHaveTextContent("趋势门控可用；市场宽度与涨停质量仍缺数。");
    expect(panel).toHaveTextContent("个股候选筛选已可由 Choice 个股输入支撑。");
    expect(panel).not.toHaveTextContent("Trend-only market gate");
    expect(panel).not.toHaveTextContent("Stock pivot candidate");
  });

  it("submits manually entered Livermore positions from the cross-asset page", async () => {
    const client = createApiClient({ mode: "mock" });
    const livermorePayload = await client.getLivermoreStrategy({ asOfDate: "2026-04-30" });
    const blockedResult = {
      ...livermorePayload.result,
      as_of_date: "2026-04-30",
      rule_readiness: livermorePayload.result.rule_readiness.map((rule) =>
        rule.key === "risk_exit"
          ? {
              ...rule,
              status: "blocked" as const,
              summary: "Position snapshot is missing.",
              missing_inputs: ["positions"],
            }
          : rule,
      ),
      supported_outputs: ["market_gate", "sector_rank", "stock_candidates"] as LivermoreOutputKey[],
      unsupported_outputs: [{ key: "risk_exit" as const, reason: "position snapshot is missing." }],
    };
    delete blockedResult.risk_exit;
    vi.spyOn(client, "getLivermoreStrategy").mockResolvedValue({
      ...livermorePayload,
      result: blockedResult,
    });
    const confluenceSpy = vi.spyOn(client, "getLivermoreSignalConfluence");
    const manualSpy = vi.spyOn(client, "materializeLivermoreManualPositionSnapshot").mockResolvedValue({
      status: "completed",
      fact_source: "livermore_position_snapshot",
      input_mode: "manual",
      as_of_date: "2026-04-30",
      row_count: 1,
      run_id: "livermore_position_snapshot:2026-04-30:test",
      source_file_hash: "sha256:test",
      source_systems: ["livermore_position_snapshot_manual"],
      source_version: "sv_livermore_position_test",
      vendor_version: "vv_livermore_position_manual_test",
      csv_path: null,
      risk_exit_input_status: "ready",
      risk_exit_input_block_reason: "",
    });

    renderPage(client);
    await screen.findByTestId("cross-asset-livermore-status");
    await waitFor(() => {
      expect(confluenceSpy).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByTestId("cross-asset-livermore-confluence")).toHaveTextContent("Alpha");
    });
    fireEvent.change(await screen.findByLabelText("股票代码"), { target: { value: "000001.SZ" } });
    fireEvent.change(screen.getByLabelText("股票名称"), { target: { value: "Alpha" } });
    fireEvent.change(screen.getByLabelText("入场成本"), { target: { value: "10.5" } });
    fireEvent.change(screen.getByLabelText("持有天数"), { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText("持仓数量"), { target: { value: "10000" } });
    fireEvent.click(screen.getByRole("button", { name: "保存持仓" }));

    await waitFor(() => {
      expect(manualSpy).toHaveBeenCalledWith({
        asOfDate: "2026-04-30",
        positions: [
          {
            stockCode: "000001.SZ",
            stockName: "Alpha",
            entryCost: 10.5,
            barsSinceEntry: 6,
            positionQuantity: 10000,
          },
        ],
      });
    });
    expect(await screen.findByText("已写入 1 条持仓快照。")).toBeInTheDocument();
    await waitFor(() => {
      expect(confluenceSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    expect(confluenceSpy.mock.calls[0]?.[0]).toEqual({ asOfDate: "2026-04-30" });
    expect(confluenceSpy.mock.calls.at(-1)?.[0]).toEqual({ asOfDate: "2026-04-30" });
  });

  it("renders observation-only Livermore confluence rows with the same strategy date", async () => {
    type SignalConfluenceClient = ApiClient & {
      getLivermoreSignalConfluence: (options?: { asOfDate?: string }) => Promise<{
        result: {
          as_of_date: string;
          macro_context: {
            status: string;
            composite_score: number | null;
            description?: string;
          };
          strategy_context: {
            market_gate_state: string;
            position_size_hint: number | null;
            new_entry_observation_allowed: boolean;
          };
          entry_observations: Array<{
            action: string;
            stock_code: string;
            stock_name: string;
            current_price: number;
            buy_trigger_price: number | null;
            invalidation_reference_price: number | null;
            position_size_hint: number | null;
            evidence: string[];
          }>;
          exit_observations: Array<{
            action: string;
            stock_code: string;
            stock_name: string;
            current_price: number;
            exit_watch_price: number | null;
            triggered: boolean;
            evidence: string[];
          }>;
          diagnostics: Array<{
            severity: string;
            code: string;
            message: string;
          }>;
        };
      }>;
    };

    const client = createApiClient({ mode: "mock" }) as SignalConfluenceClient;
    const livermoreSpy = vi.spyOn(client, "getLivermoreStrategy");
    const confluenceSpy = vi.fn().mockResolvedValue({
      result: {
        as_of_date: "2026-04-30",
        macro_context: {
          status: "supportive",
          composite_score: -0.35,
          description: "宏观环境偏支持，但该面板仅供观察。",
        },
        strategy_context: {
          market_gate_state: "HOT",
          position_size_hint: 0.75,
          new_entry_observation_allowed: true,
        },
        entry_observations: [
          {
            action: "observe_entry_setup",
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            current_price: 21.9,
            buy_trigger_price: 21.8,
            invalidation_reference_price: 20.6,
            position_size_hint: 0.5,
            evidence: ["突破位贴近买点", "量价配合待确认"],
          },
        ],
        exit_observations: [
          {
            action: "observe_exit_watch",
            stock_code: "000777.SZ",
            stock_name: "Watch Alpha",
            current_price: 19.8,
            exit_watch_price: 20.1,
            triggered: false,
            evidence: ["EMA10 失守前先观察"],
          },
        ],
        diagnostics: [
          "No risk exit watch items or triggered exit items available.",
          "Observation-only output. This service does not generate trading instructions.",
          {
            severity: "info",
            code: "observation_only",
            message: "仅供观察，不构成交易指令。",
          },
        ],
      },
    });
    client.getLivermoreSignalConfluence = confluenceSpy;

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-confluence");
    await waitFor(() => {
      expect(livermoreSpy).toHaveBeenCalled();
      expect(confluenceSpy).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(panel).toHaveTextContent("Alpha");
    });
    expect(confluenceSpy.mock.calls[0]?.[0]).toEqual(livermoreSpy.mock.calls[0]?.[0]);
    expect(panel).toHaveTextContent("宏观 × 策略观察点位");
    expect(panel).toHaveTextContent("仅供观察，不构成交易指令。");
    expect(panel).not.toHaveTextContent("message-0");
    expect(panel).not.toHaveTextContent("Observation-only output. This service does not generate trading instructions.");
    expect(panel).not.toHaveTextContent("No risk exit watch items or triggered exit items available.");
    expect(panel).toHaveTextContent("当前没有可展示的退出观察点位。");
    expect(panel).toHaveTextContent("候选触发价");
    expect(panel).toHaveTextContent("21.80");
    expect(panel).toHaveTextContent("退出观察价");
    expect(panel).toHaveTextContent("20.10");
    expect(panel).toHaveTextContent("突破位贴近买点");
    expect(panel).toHaveTextContent("EMA10 失守前先观察");
  });

  it("renders Livermore confluence diagnostics and empty observations when no rows are available", async () => {
    type SignalConfluenceClient = ApiClient & {
      getLivermoreSignalConfluence: (options?: { asOfDate?: string }) => Promise<{
        result: {
          as_of_date: string;
          macro_context: {
            status: string;
            composite_score: number | null;
          };
          strategy_context: {
            market_gate_state: string;
            position_size_hint: number | null;
            new_entry_observation_allowed: boolean;
          };
          entry_observations: unknown[];
          exit_observations: unknown[];
          diagnostics: Array<{
            severity: string;
            code: string;
            message: string;
          }>;
        };
      }>;
    };

    const client = createApiClient({ mode: "mock" }) as SignalConfluenceClient;
    client.getLivermoreSignalConfluence = vi.fn().mockResolvedValue({
      result: {
        as_of_date: "2026-04-30",
        macro_context: {
          status: "unknown",
          composite_score: null,
        },
        strategy_context: {
          market_gate_state: "UNKNOWN",
          position_size_hint: 0,
          new_entry_observation_allowed: false,
        },
        entry_observations: [],
        exit_observations: [],
        diagnostics: [
          {
            severity: "warning",
            code: "missing_macro_score",
            message: "缺少宏观综合分，当前只能保留观察口径。",
          },
          {
            severity: "info",
            code: "no_observations",
            message: "当前没有可展示的入场或退出观察点位。",
          },
        ],
      },
    });

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-confluence");
    await waitFor(() => {
      expect(client.getLivermoreSignalConfluence).toHaveBeenCalled();
      expect(panel).toHaveTextContent("暂无可观察点位");
    });
    expect(panel).toHaveTextContent("暂无可观察点位");
    expect(panel).toHaveTextContent("缺少宏观综合分，当前只能保留观察口径。");
    expect(panel).toHaveTextContent("当前没有可展示的入场或退出观察点位。");
    expect(panel).not.toHaveTextContent("message-");
    expect(panel).toHaveTextContent("宏观缺数");
    expect(panel).toHaveTextContent("暂无点位");
  });

  it("keeps restrictive Livermore confluence entries in observe-only mode and marks triggered exits", async () => {
    const client = createApiClient({ mode: "mock" });
    client.getLivermoreSignalConfluence = vi.fn().mockResolvedValue({
      result: {
        as_of_date: "2026-04-30",
        macro_context: {
          status: "restrictive",
          composite_score: 0.42,
          multiplier: 0,
        },
        strategy_context: {
          market_gate_state: "OVERHEAT",
          market_gate_exposure: 1,
          allows_new_entry_observations: false,
        },
        position_size_hint: 0,
        entry_observations: [
          {
            action: "observe_only",
            stock_code: "000002.SZ",
            stock_name: "Beta",
            current_price: 12.1,
            trigger_price: 12.4,
            invalidation_reference_price: null,
            evidence: ["候选触发价来自 Livermore breakout_level。"],
          },
        ],
        exit_observations: [
          {
            action: "exit_triggered",
            stock_code: "000003.SZ",
            stock_name: "Gamma",
            current_price: 9.1,
            exit_watch_price: 9.8,
            triggered: true,
            evidence: ["退出观察价来自 Livermore EMA10。"],
          },
        ],
        diagnostics: ["Observation-only output. This service does not generate trading instructions."],
        disclaimer: "Observation-only output. This service does not generate trading instructions.",
      },
    });

    renderPage(client);

    const panel = await screen.findByTestId("cross-asset-livermore-confluence");
    await waitFor(() => {
      expect(panel).toHaveTextContent("偏收敛");
      expect(panel).toHaveTextContent("仅保留观察，不追加新动作");
      expect(panel).toHaveTextContent("仅观察");
      expect(panel).toHaveTextContent("退出观察已触发");
      expect(panel).toHaveTextContent("0%");
    });
  });

  it("surfaces the data-driven cockpit sections and provenance flags", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getResearchCalendarEvents: vi.fn(async () => [
        {
          id: "rc_supply_001",
          date: "2026-04-10",
          title: "国债供给窗口",
          kind: "supply" as const,
          severity: "medium" as const,
          amount_label: "净融资 180 亿元",
          note: "供给节奏",
        },
      ]),
    };

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-candidate-actions")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-event-calendar")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-watch-list")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-page-output")).toBeInTheDocument();
    expect(await screen.findByText("国债供给窗口")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-event-calendar")).not.toHaveTextContent("仅分析口径");
    expect((await screen.findAllByText("仅分析口径")).length).toBeGreaterThan(0);
  });

  it("shows a regime-based first-screen conclusion when linkage analysis is unavailable", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getMacroBondLinkageAnalysis: vi.fn(async () => {
        throw new Error("macro_bond_linkage.analysis failed");
      }),
    };

    renderPage(client);

    const hero = await screen.findByTestId("cross-asset-decision-hero");
    await waitFor(() => {
      expect(hero).toHaveTextContent("联动分析暂不可用");
      expect(hero).toHaveTextContent("首屏参考市场体制");
    });
    expect(screen.getByTestId("cross-asset-research-card-duration")).toHaveTextContent(
      "联动分析暂不可用，四维判断待恢复。",
    );
  });

  it("surfaces permission-denied linkage and ncd modules on the first screen", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getMacroBondLinkageAnalysis: vi.fn(async () => {
        throw new Error("User is not allowed to read macro_bond_linkage.");
      }),
      getNcdFundingProxy: vi.fn(async () => {
        throw new Error("User is not allowed to read market_data_ncd_proxy.");
      }),
    };

    renderPage(client);

    const hero = await screen.findByTestId("cross-asset-decision-hero");
    const statusFlags = await screen.findByTestId("cross-asset-status-flags");
    const trustPanel = await screen.findByTestId("cross-asset-trust-panel");

    await waitFor(() => {
      expect(hero).toHaveTextContent("联动分析权限受限");
      expect(statusFlags).toHaveTextContent("权限受限");
      expect(statusFlags).toHaveTextContent("macro_bond_linkage.analysis");
      expect(statusFlags).toHaveTextContent("market_data_ncd_proxy");
    });
    expect(screen.getByTestId("cross-asset-research-card-duration")).toHaveTextContent(
      "联动分析权限受限，四维判断待开通。",
    );
    expect(trustPanel).toHaveTextContent("申请读取权限");
    expect(await screen.findByTestId("cross-asset-ncd-proxy-warning")).toHaveTextContent(
      "无 NCD/资金代理读取权限",
    );
  });

  it("surfaces a first-screen loading failure when the latest macro chain fails", async () => {
    const client = {
      ...createApiClient({ mode: "mock" }),
      getChoiceMacroLatest: vi.fn(async () => {
        throw new Error("choice latest failed");
      }),
    };

    renderPage(client);

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    const firstScreenFlags = await screen.findByTestId("cross-asset-status-flags");
    await waitFor(() => {
      expect(firstScreenFlags).toHaveTextContent("加载失败");
    });
    expect(firstScreenFlags).toHaveTextContent("choice_macro.latest");
  });
});
