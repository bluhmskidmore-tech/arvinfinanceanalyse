import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, vi } from "vitest";

import { createApiClient } from "../api/client";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="balance-movement-echarts-stub" />,
}));

beforeAll(async () => {
  await preloadWorkbenchRouteModules("balance-movement-analysis");
}, 20_000);

describe("BalanceMovementAnalysisPage", () => {
  it("keeps source-level style debt bounded to dynamic visual values", () => {
    const source = readFileSync(
      resolve(process.cwd(), "src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx"),
      "utf8",
    );
    const styleCount = (source.match(/\bstyle\s*=\s*\{/g) ?? []).length;

    expect(source).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(source).not.toMatch(/rgba\(/);
    expect(source).not.toMatch(/\bboxShadow\s*:|box-shadow\s*:/);
    expect(styleCount).toBeLessThanOrEqual(3);
    expect(source).not.toContain("PageAsyncSection");
    expect(source).toContain("BusinessBalanceMatrixSection");
  });

  it("lets provenance content expand when the compact layout stacks", () => {
    const css = readFileSync(
      resolve(
        process.cwd(),
        "src/features/balance-movement-analysis/pages/BalanceMovementAnalysisFigma.css",
      ),
      "utf8",
    );

    expect(css).toMatch(
      /\.balance-movement-provenance\s*\{\s*height:\s*auto;\s*min-height:\s*0;\s*grid-template-rows:\s*auto;\s*overflow:\s*visible;/,
    );
  });

  it("renders AC OCI TPL balance movement from the governed read model", async () => {
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    const pageHeader = await screen.findByTestId("balance-movement-analysis-page-header");
    expect(within(pageHeader).getByTestId("balance-movement-analysis-title")).toHaveTextContent(
      "资产余额变动分析",
    );
    expect(pageHeader).toHaveTextContent("投资组合 / 资产结构");
    expect(within(pageHeader).getAllByRole("combobox")).toHaveLength(2);
    const kpiRibbon = await screen.findByTestId("balance-movement-analysis-summary");
    await waitFor(() => {
      expect(within(pageHeader).getByRole("button", { name: "刷新数据" })).toBeEnabled();
      expect(within(pageHeader).getByRole("button", { name: "导出 CSV" })).toBeEnabled();
    });

    const decisionHero = await screen.findByTestId("balance-movement-analysis-decision-hero");
    expect(decisionHero).toHaveTextContent("DECISION SIGNAL");
    expect(decisionHero).toHaveTextContent("主要由 TPL 驱动");
    expect(decisionHero).toHaveTextContent("对账完整");
    expect(decisionHero).toHaveTextContent("FVTPL 结构占比");
    expect(decisionHero).toHaveTextContent("TPL +51.63 亿");
    expect(decisionHero).toHaveTextContent("OCI +44.87 亿");
    expect(decisionHero).toHaveTextContent("AC +33.29 亿");

    const dataTrust = screen.getByTestId("balance-movement-analysis-freshness");
    expect(dataTrust).toHaveTextContent("DATA TRUST");
    expect(dataTrust).toHaveTextContent("Read model");
    expect(dataTrust).toHaveTextContent("Upstream control");
    expect(dataTrust).toHaveTextContent("3 / 3 matched");
    expect(dataTrust).toHaveTextContent("Currency basisCNX");

    expect(kpiRibbon.querySelectorAll(":scope > article")).toHaveLength(4);
    expect(kpiRibbon).toHaveTextContent("期末余额3,358.73 亿");
    expect(kpiRibbon).toHaveTextContent("本月净增+129.80 亿");
    expect(kpiRibbon).toHaveTextContent("最大驱动TPL · 39.78%");
    expect(kpiRibbon).toHaveTextContent("对账状态3 / 3 匹配");
    expect(within(kpiRibbon).getAllByTestId("balance-movement-kpi-signal")).toHaveLength(4);

    const driversAndStructure = screen.getByTestId("balance-movement-analysis-drivers-structure");
    expect(driversAndStructure).toHaveTextContent("本月变动驱动");
    expect(driversAndStructure).toHaveTextContent("会计分类结构");
    expect(driversAndStructure).toHaveTextContent("TPL");
    expect(driversAndStructure).toHaveTextContent("+51.63 亿");
    expect(driversAndStructure).toHaveTextContent("39.78%");
    expect(driversAndStructure).toHaveTextContent("AC");
    expect(driversAndStructure).toHaveTextContent("42.44%");
    expect(driversAndStructure).toHaveTextContent("-0.67pp");
    expect(
      within(driversAndStructure).getByTestId("balance-movement-driver-composition-band"),
    ).toHaveAccessibleName(/TPL 39.78%/);
    expect(
      within(driversAndStructure).getByTestId("balance-movement-structure-mix-band"),
    ).toHaveAccessibleName(/AC 42.44%/);

    const maturityAndConcentration = screen.getByTestId(
      "balance-movement-analysis-maturity-concentration",
    );
    expect(maturityAndConcentration).toHaveTextContent("期限结构");
    expect(maturityAndConcentration).toHaveTextContent("主体集中度");
    expect(maturityAndConcentration).toHaveTextContent("≤90天");
    expect(maturityAndConcentration).toHaveTextContent("HHI");
    expect(maturityAndConcentration).toHaveTextContent("Top 5 Share");
    expect(
      within(maturityAndConcentration).getByTestId("balance-movement-maturity-spectrum"),
    ).toHaveAccessibleName(/≤90天/);
    const overThreeYearsBucket = maturityAndConcentration.querySelector(
      '.balance-movement-maturity-compact__grid [data-maturity="over-3y"]',
    );
    expect(overThreeYearsBucket).toHaveTextContent(">3年");
    expect(overThreeYearsBucket).not.toHaveTextContent("未映射");
    expect(
      within(maturityAndConcentration).getByTestId("balance-movement-maturity-coverage-band"),
    ).toHaveAccessibleName(/KNOWN.*UNMAPPED/);
    expect(
      within(maturityAndConcentration).getByTestId("balance-movement-top5-gauge"),
    ).toHaveTextContent("Top 5 Share");
    expect(
      within(maturityAndConcentration).getByTestId(
        "balance-movement-concentration-unknown-strip",
      ),
    ).toHaveTextContent("Unknown");

    const evidenceStrip = await screen.findByTestId("balance-movement-analysis-evidence-strip");
    expect(evidenceStrip).toHaveTextContent("05 / EVIDENCE & PROVENANCE");
    expect(evidenceStrip).toHaveTextContent("FRESHNESS");
    expect(evidenceStrip).toHaveTextContent("LINEAGE");
    expect(evidenceStrip).toHaveTextContent("CONTROL SCOPE");
    expect(evidenceStrip).toHaveTextContent("mock_balance-analysis.movement.detail");
    expect(evidenceStrip).toHaveTextContent("rv_dashboard_mock_v2");

    const accountingBuckets = screen.getByTestId("balance-movement-analysis-accounting-buckets");
    expect(accountingBuckets).toHaveTextContent("06 / ACCOUNTING BUCKETS");
    expect(within(accountingBuckets).getByRole("row", { name: /AC/ })).toHaveTextContent("一致");
    expect(within(accountingBuckets).getByRole("row", { name: /OCI/ })).toHaveTextContent("一致");
    expect(within(accountingBuckets).getByRole("row", { name: /TPL/ })).toHaveTextContent("一致");

    const sixMonthStructure = screen.getByTestId(
      "balance-movement-analysis-six-month-structure",
    );
    const structureBridge = screen.getByTestId("balance-movement-analysis-structure-bridge");
    const liveDecomposition = screen.getByTestId(
      "balance-movement-analysis-live-decomposition",
    );
    expect(sixMonthStructure).toHaveTextContent("02 / SIX-MONTH ACCOUNTING STRUCTURE");
    expect(structureBridge).toHaveTextContent("03 / STRUCTURE MIGRATION");
    expect(liveDecomposition).toHaveTextContent("04 / DRIVER DECOMPOSITION");
    expect(
      accountingBuckets.compareDocumentPosition(sixMonthStructure) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      sixMonthStructure.compareDocumentPosition(structureBridge) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      structureBridge.compareDocumentPosition(liveDecomposition) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const anomalyDiagnostics = await screen.findByTestId(
      "balance-movement-analysis-anomaly-diagnostics",
    );
    expect(anomalyDiagnostics).toHaveTextContent("历史异常定位");
    expect(anomalyDiagnostics).toHaveTextContent("历史样本不足");
    expect(anomalyDiagnostics).toHaveTextContent("仅 2 期样本");
    const businessSummary = await screen.findByTestId(
      "balance-movement-analysis-business-summary",
    );
    expect(businessSummary).toHaveTextContent("07 / BUSINESS LINE MOVERS");
    expect(businessSummary).toHaveTextContent("TPL +51.63 亿 · 贡献 39.78%");
    expect(businessSummary).toHaveTextContent("本月总余额增加 129.80 亿");
    expect(businessSummary).toHaveTextContent("FVTPL 占比至");
    expect(screen.getByText("AC 稳定器").parentElement).toHaveTextContent("42.44%-0.67pp");
    expect(screen.getByText("OCI 压舱石").parentElement).toHaveTextContent("31.49%+0.12pp");
    expect(screen.getByTestId("balance-movement-analysis-driver-chart")).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-driver-ranking")).toHaveTextContent(
      "TPL+51.63 亿 · 39.78%占比 26.07% · +0.55pp",
    );
    expect(screen.getByTestId("balance-movement-analysis-driver-ranking")).toHaveTextContent(
      "OCI+44.87 亿 · 34.57%占比 31.49% · +0.12pp",
    );
    expect(screen.getByTestId("balance-movement-analysis-driver-ranking")).toHaveTextContent(
      "AC+33.29 亿 · 25.65%占比 42.44% · -0.67pp",
    );
    expect(screen.getByTestId("balance-movement-analysis-structure-driver-hint")).toHaveTextContent(
      "变动额",
    );
    expect(screen.getByTestId("balance-movement-analysis-business-top-moves")).toHaveTextContent(
      "本月变动 · 发散视图",
    );
    expect(screen.getByTestId("balance-movement-analysis-business-top-moves")).toHaveTextContent(
      "资产端-拆放同业",
    );
    const topMovesMom = screen.getByTestId("balance-movement-analysis-business-top-moves-mom");
    expect(topMovesMom).toBeInTheDocument();
    expect(within(topMovesMom).queryAllByRole("listitem").length).toBeGreaterThan(1);
    const interbankLendingTopMove = within(topMovesMom)
      .getByText("资产端-拆放同业")
      .closest('[role="listitem"]');
    expect(interbankLendingTopMove).toHaveTextContent("总账");
    expect(interbankLendingTopMove).toHaveTextContent("总账对账科目余额");
    expect(interbankLendingTopMove).toHaveTextContent("50.00 → 80.00");
    const topMovesSix = screen.getByTestId("balance-movement-analysis-business-top-moves-sixmonth");
    expect(topMovesSix).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-business-top-moves")).toHaveTextContent("近 2 月变动");
    const topMoveSources = screen.getAllByTestId("balance-movement-analysis-business-top-moves-source");
    expect(topMoveSources.length).toBeGreaterThan(0);
    expect(screen.getByTestId("balance-movement-analysis-slice-note")).toHaveTextContent(
      "总账 AC/OCI/TPL",
    );
    expect(screen.getByTestId("balance-movement-analysis-series-context")).toHaveTextContent(
      "两个月度",
    );
    expect(screen.getByTestId("balance-movement-analysis-governance")).toHaveTextContent(
      "规则版本",
    );
    expect(screen.getByTestId("balance-movement-analysis-governance")).toHaveTextContent(
      "rv_accounting_asset_movement_v2",
    );
    const zqtzCalibration = screen.getByTestId("balance-movement-analysis-zqtz-calibration");
    expect(zqtzCalibration).toHaveTextContent("ZQTZ228");
    expect(zqtzCalibration).toHaveTextContent("canonical grain");
    expect(zqtzCalibration).toHaveTextContent("652.28");
    expect(zqtzCalibration).toHaveTextContent("58.12");
    expect(zqtzCalibration).toHaveTextContent("2026-03");
    const zqtzDetail = screen.getByTestId("balance-movement-analysis-zqtz-detail");
    expect(zqtzDetail).toHaveTextContent("08 / FINANCIAL INVESTMENT MONTHLY DETAIL");
    expect(zqtzDetail).toHaveTextContent("金融投资资产明细变动");
    expect(zqtzDetail).toHaveTextContent("政策性金融债");
    expect(zqtzDetail).toHaveTextContent("地方政府债");
    expect(zqtzDetail).toHaveTextContent("外国债券");
    expect(zqtzDetail).toHaveTextContent("长期股权投资（亿元）");
    expect(zqtzDetail).toHaveTextContent("较上月");
    expect(zqtzDetail).toHaveTextContent("+8.00");
    expect(
      within(zqtzDetail).getByRole("row", {
        name: "汇总 120.75 163.00 +42.25 +42.25",
      }),
    ).toBeInTheDocument();
    const structureMigration = screen.getByTestId("balance-movement-analysis-structure-migration");
    expect(structureMigration).toHaveTextContent("结构迁移信号");
    expect(structureMigration).toHaveTextContent("占比正向抬升最明显的是 TPL");
    expect(structureMigration).toHaveTextContent("这是汇总会计分类桶的结构信号");
    expect(structureMigration).toHaveTextContent("损益波动暴露");

    const differenceWaterfall = screen.getByTestId("balance-movement-analysis-difference-waterfall");
    expect(differenceWaterfall).toHaveTextContent("差异归因瀑布");
    expect(differenceWaterfall).toHaveTextContent("ZQTZ 明细汇总");
    expect(differenceWaterfall).toHaveTextContent("AC/OCI/FVTPL 合计");
    expect(differenceWaterfall).toHaveTextContent("长期股权投资");
    expect(differenceWaterfall).toHaveTextContent("凭证式国债 / 1430101 成本");
    expect(differenceWaterfall).toHaveTextContent("未分类 / 残差");
    expect(differenceWaterfall).toHaveTextContent("闭合校验");
    const valuationGap = within(differenceWaterfall)
      .getByText("估值差")
      .closest(".balance-movement-waterfall__component");
    const fxGap = within(differenceWaterfall)
      .getByText("外币折算差")
      .closest(".balance-movement-waterfall__component");
    const unsupportedGaps = [valuationGap, fxGap].filter(
      (gap): gap is HTMLElement => gap instanceof HTMLElement,
    );
    expect(unsupportedGaps).toHaveLength(2);
    for (const gap of unsupportedGaps) {
      expect(gap).toHaveTextContent("待拆分");
      expect(gap).not.toHaveTextContent("+0.00 亿");
    }
    const residualClosure = screen.getByTestId("balance-movement-analysis-residual-closure");
    expect(residualClosure).toHaveTextContent("哪些差异还不能解释");
    expect(residualClosure).toHaveTextContent("未分类 / 残差");
    expect(residualClosure).toHaveTextContent("估值差");
    expect(residualClosure).toHaveTextContent("外币折算差");
    expect(residualClosure).toHaveTextContent("未支持，不反推");
    expect(residualClosure).not.toHaveTextContent("+0.00 亿");

    const basisDecomposition = screen.getByTestId("balance-movement-analysis-basis-decomposition");
    expect(basisDecomposition).toHaveTextContent("AC / OCI / TPL 驱动拆解");
    expect(basisDecomposition).toHaveTextContent("142 摊余成本债权投资");
    expect(basisDecomposition).toHaveTextContent("144020 股权 OCI");
    expect(basisDecomposition).toHaveTextContent("交易性金融资产");

    const maturityStructure = screen.getByTestId("balance-movement-analysis-zqtz-maturity");
    expect(maturityStructure).toHaveTextContent("期限 / 到期结构");
    expect(maturityStructure).toHaveTextContent("30天内");
    expect(maturityStructure).toHaveTextContent("1-3年");
    expect(maturityStructure).toHaveTextContent("未映射");

    const concentrationAnalysis = screen.getByTestId("balance-movement-analysis-zqtz-concentration");
    expect(concentrationAnalysis).toHaveTextContent("主体 / 评级 / 行业集中度");
    expect(concentrationAnalysis).toHaveTextContent("国家开发银行");
    expect(concentrationAnalysis).toHaveTextContent("AAA");
    expect(concentrationAnalysis).toHaveTextContent("金融业");
    expect(concentrationAnalysis).toHaveTextContent("Unknown");
    expect(concentrationAnalysis).toHaveTextContent("HHI 1,620.35");

    const matrixTitle = screen.getByText("业务口径余额矩阵与 AC / OCI / TPL 对账");
    const detailTitle = screen.getByText("明细 / 对账：AC / OCI / TPL 余额变动");
    expect(
      matrixTitle.compareDocumentPosition(detailTitle) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    const table = screen.getByTestId("balance-movement-analysis-table");
    expect(within(table).getByText("占比变动")).toBeInTheDocument();
    expect(within(table).getByText("-0.67pp")).toBeInTheDocument();
    expect(within(table).getByText("+0.12pp")).toBeInTheDocument();
    expect(within(table).getByText("+0.55pp")).toBeInTheDocument();
    expect(within(table).getByText("AC")).toBeInTheDocument();
    expect(within(table).getByText("42.44%")).toBeInTheDocument();
    expect(within(table).getByText("OCI")).toBeInTheDocument();
    expect(within(table).getByText("TPL")).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-controls")).toHaveTextContent(
      "1440101%",
    );
    expect(screen.getByTestId("balance-movement-analysis-controls")).toHaveTextContent(
      "144020%",
    );
    const trendTable = screen.getByTestId("balance-movement-analysis-trend-table");
    expect(matrixTitle).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-structure-chart")).toBeInTheDocument();
    expect(document.querySelectorAll(".balance-movement-six-month__bar").length).toBeGreaterThan(0);
    expect(screen.getByTestId("balance-movement-analysis-maturity-ladder")).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-structure-share-table-title")).toHaveTextContent(
      "结构占比明细",
    );
    const shareEvolutionTable = screen.getByTestId("balance-movement-analysis-structure-share-table");
    expect(within(shareEvolutionTable).getByText("26-01")).toBeInTheDocument();
    expect(within(shareEvolutionTable).getByText("26-02")).toBeInTheDocument();
    expect(within(shareEvolutionTable).getByText("环比·AC")).toBeInTheDocument();
    expect(within(shareEvolutionTable).getByText("同比·AC")).toBeInTheDocument();
    expect(within(shareEvolutionTable).getByText("较首月·AC")).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-structure-insight")).toHaveTextContent(
      "AC占比",
    );
    expect(within(trendTable).getByText("明细项目")).toBeInTheDocument();
    expect(within(trendTable).getAllByText("2026年2月").length).toBeGreaterThan(0);
    expect(within(trendTable).getAllByText("2026年1月").length).toBeGreaterThan(0);
    expect(within(trendTable).getAllByText("较上月").length).toBeGreaterThan(0);
    expect(within(trendTable).getAllByText("较年初").length).toBeGreaterThan(0);
    expect(within(trendTable).queryByText("央行票据")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("地方政府债")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("政策性金融债")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("外国债券")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("长期股权投资（亿元）")).not.toBeInTheDocument();
    expect(within(trendTable).getByText("负债端-同业存放")).toBeInTheDocument();
    expect(within(trendTable).getByText("负债端-同业拆入")).toBeInTheDocument();
    expect(within(trendTable).getByText("负债端-卖出回购")).toBeInTheDocument();
    expect(within(trendTable).getByText("负债端-同业存单")).toBeInTheDocument();
    expect(within(trendTable).getByText("资产端合计")).toBeInTheDocument();
    expect(within(trendTable).getByText("负债端合计")).toBeInTheDocument();
    expect(within(trendTable).getByText("资产负债净额")).toBeInTheDocument();
    /* 两期 mock（首月+当前月）下「较年初」= 当前期末 − 数据序列首月，与「较上月」同值，故动额两列各出现一次。 */
    expect(within(trendTable).getAllByText("+194.80").length).toBe(2);
    expect(within(trendTable).getAllByText("-85.00").length).toBe(2);
    expect(within(trendTable).getAllByText("+109.80").length).toBe(2);
    expect(screen.getByTestId("balance-movement-analysis-data-states")).toHaveTextContent(
      "10 / DATA STATES & GOVERNANCE",
    );
  });

  it("uses only backend share pct and keeps missing shares visible", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const nullShareClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        const patchRows = (rows: typeof envelope.result.rows) =>
          rows.map((row) => {
            if (row.basis_bucket === "AC") {
              return {
                ...row,
                previous_balance_pct: "0",
                current_balance_pct: "0",
              };
            }
            if (row.basis_bucket === "OCI") {
              return {
                ...row,
                current_balance_pct: null,
              };
            }
            if (row.basis_bucket === "TPL") {
              return {
                ...row,
                previous_balance_pct: null,
              };
            }
            return row;
          });
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: patchRows(envelope.result.rows),
            trend_months: envelope.result.trend_months.map((month) => ({
              ...month,
              rows: patchRows(month.rows),
            })),
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: nullShareClient,
    });

    await screen.findByTestId("balance-movement-analysis-business-summary");
    expect(screen.getByText("AC 稳定器").parentElement).toHaveTextContent("0.00%0.00pp");
    expect(screen.getByText("OCI 压舱石").parentElement).toHaveTextContent("——");
    const driverLabels = screen.getByTestId("balance-movement-analysis-driver-ranking");
    expect(driverLabels).toHaveTextContent("AC+33.29 亿 · 25.65%占比 0.00% · 0.00pp");
    expect(driverLabels).toHaveTextContent("OCI+44.87 亿 · 34.57%占比 — · —");
    expect(driverLabels).toHaveTextContent("TPL+51.63 亿 · 39.78%占比 26.07% · —");
    expect(driverLabels).not.toHaveTextContent("TPL+51.63 亿 · 39.78%占比 0.00%");

    const structureChart = screen.getByTestId("balance-movement-analysis-structure-chart");
    expect(within(structureChart).queryByTestId("balance-movement-echarts-stub")).not.toBeInTheDocument();
    expect(structureChart).toHaveTextContent("占比数据缺失，结构图暂不可比");
    const compactMixBand = screen.getByTestId("balance-movement-structure-mix-band");
    expect(compactMixBand).toHaveAttribute("data-state", "unavailable");
    expect(compactMixBand).toHaveAccessibleName("会计分类结构：数据不可用");

    const shareEvolutionTable = screen.getByTestId("balance-movement-analysis-structure-share-table");
    expect(within(shareEvolutionTable).getAllByText("0.00%").length).toBeGreaterThan(0);
    expect(within(shareEvolutionTable).queryByText("31.49%")).not.toBeInTheDocument();
    const currentShareRow = within(shareEvolutionTable).getByRole("row", { name: /26-02/ });
    expect(within(currentShareRow).getAllByRole("cell")[1]).toHaveTextContent("—");
    expect(shareEvolutionTable).not.toHaveTextContent("NaNpp");
  });

  it("hydrates report date and currency from query parameters", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getMovementSpy = vi.fn(baseClient.getBalanceMovementAnalysis);

    renderWorkbenchApp(["/balance-movement-analysis?report_date=2026-01-31&currency_basis=CNX"], {
      client: {
        ...baseClient,
        getBalanceMovementDates: vi.fn(async (currencyBasis = "CNX") =>
          buildMockApiEnvelope("balance-analysis.movement.dates", {
            report_dates: ["2026-02-28", "2026-01-31"],
            currency_basis: currencyBasis,
          }),
        ),
        getBalanceMovementAnalysis: getMovementSpy,
      },
    });

    await waitFor(() => {
      expect(getMovementSpy).toHaveBeenCalledWith({
        reportDate: "2026-01-31",
        currencyBasis: "CNX",
      });
    });
  });

  it("refreshes the selected report date through the formal materialize endpoint", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    await screen.findByTestId("balance-movement-analysis-table");
    await user.click(screen.getByTestId("balance-movement-analysis-refresh"));

    expect(await screen.findByTestId("balance-movement-analysis-refresh-message")).toHaveTextContent(
      "completed: 3 行",
    );
  });

  it("locks unsupported currency URLs to the governed CNX basis", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const datesSpy = vi.fn(baseClient.getBalanceMovementDates);
    const movementSpy = vi.fn(baseClient.getBalanceMovementAnalysis);

    renderWorkbenchApp(["/balance-movement-analysis?currency_basis=CNY"], {
      client: {
        ...baseClient,
        getBalanceMovementDates: datesSpy,
        getBalanceMovementAnalysis: movementSpy,
      },
    });

    await screen.findByTestId("balance-movement-analysis-table");

    expect(datesSpy).toHaveBeenCalledWith("CNX");
    expect(movementSpy).toHaveBeenCalledWith(
      expect.objectContaining({ currencyBasis: "CNX" }),
    );
    const currencySelector = screen.getAllByRole("combobox")[1] as HTMLSelectElement;
    expect(currencySelector).toBeDisabled();
    expect(currencySelector.value).toBe("CNX");
    expect(currencySelector.options).toHaveLength(1);
  });

  it("targets the latest upstream report date when the read model is lagging", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const refreshSpy = vi.fn(async ({
      reportDate,
      currencyBasis = "CNX",
    }: {
      reportDate: string;
      currencyBasis?: string;
    }) => ({
      status: "completed",
      cache_key: "accounting_asset_movement.monthly",
      report_date: reportDate,
      currency_basis: currencyBasis,
      rule_version: "rv_accounting_asset_movement_v2",
      movement_refreshed_dates: [reportDate],
    }));

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: {
        ...baseClient,
        getBalanceMovementDates: vi.fn(async (currencyBasis = "CNX") =>
          buildMockApiEnvelope("balance-analysis.movement.dates", {
            report_dates: ["2026-04-30"],
            currency_basis: currencyBasis,
            latest_read_model_report_date: "2026-04-30",
            latest_upstream_control_report_date: "2026-05-31",
            freshness_status: "read_model_lagging" as const,
          }),
        ),
        refreshBalanceMovementAnalysis: refreshSpy,
      },
    });

    await screen.findByTestId("balance-movement-analysis-table");
    await user.click(screen.getByTestId("balance-movement-analysis-refresh"));

    expect(refreshSpy).toHaveBeenCalledWith({
      reportDate: "2026-05-31",
      currencyBasis: "CNX",
    });
  });

  it("polls queued refreshes and selects the newly materialized report date", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    let dateLoadCount = 0;
    const datesSpy = vi.fn(async (currencyBasis = "CNX") => {
      dateLoadCount += 1;
      const readModelCaughtUp = dateLoadCount >= 2;
      return buildMockApiEnvelope("balance-analysis.movement.dates", {
        report_dates: readModelCaughtUp
          ? ["2026-05-31", "2026-04-30"]
          : ["2026-04-30"],
        currency_basis: currencyBasis,
        latest_read_model_report_date: readModelCaughtUp ? "2026-05-31" : "2026-04-30",
        latest_upstream_control_report_date: "2026-05-31",
        freshness_status: readModelCaughtUp ? ("fresh" as const) : ("read_model_lagging" as const),
      });
    });
    const movementSpy = vi.fn(baseClient.getBalanceMovementAnalysis);
    const refreshSpy = vi.fn(async ({
      reportDate,
      currencyBasis = "CNX",
    }: {
      reportDate: string;
      currencyBasis?: string;
    }) => ({
      status: "queued",
      cache_key: "accounting_asset_movement.monthly",
      report_date: reportDate,
      currency_basis: currencyBasis,
      run_id: "accounting_asset_movement_refresh:2026-05-31",
      trigger_mode: "async",
      rule_version: "rv_accounting_asset_movement_v2",
      movement_refreshed_dates: [reportDate],
    }));

    renderWorkbenchApp(["/balance-movement-analysis?report_date=2026-04-30&currency_basis=CNX"], {
      client: {
        ...baseClient,
        getBalanceMovementDates: datesSpy,
        getBalanceMovementAnalysis: movementSpy,
        refreshBalanceMovementAnalysis: refreshSpy,
      },
    });

    await waitFor(() => {
      expect(movementSpy).toHaveBeenCalledWith({
        reportDate: "2026-04-30",
        currencyBasis: "CNX",
      });
    });
    await user.click(screen.getByTestId("balance-movement-analysis-refresh"));

    await waitFor(() => {
      expect(datesSpy).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(movementSpy).toHaveBeenCalledWith({
        reportDate: "2026-05-31",
        currencyBasis: "CNX",
      });
    });
    await waitFor(() => {
      expect((screen.getAllByRole("combobox")[0] as HTMLSelectElement).value).toBe(
        "2026-05-31",
      );
    });
  });

  it("keeps an existing-date queued refresh pending instead of reporting completion", async () => {
    const user = userEvent.setup();
    const baseClient = createApiClient({ mode: "mock" });
    const datesSpy = vi.fn(async (currencyBasis = "CNX") =>
      buildMockApiEnvelope("balance-analysis.movement.dates", {
        report_dates: ["2026-04-30"],
        currency_basis: currencyBasis,
        latest_read_model_report_date: "2026-04-30",
        latest_upstream_control_report_date: "2026-04-30",
        freshness_status: "fresh" as const,
      }),
    );
    const refreshSpy = vi.fn(async ({
      reportDate,
      currencyBasis = "CNX",
    }: {
      reportDate: string;
      currencyBasis?: string;
    }) => ({
      status: "queued",
      cache_key: "accounting_asset_movement.monthly",
      report_date: reportDate,
      currency_basis: currencyBasis,
      run_id: "accounting_asset_movement_refresh:2026-04-30",
      trigger_mode: "async",
      rule_version: "rv_accounting_asset_movement_v2",
      movement_refreshed_dates: [reportDate],
    }));

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: {
        ...baseClient,
        getBalanceMovementDates: datesSpy,
        refreshBalanceMovementAnalysis: refreshSpy,
      },
    });

    await screen.findByTestId("balance-movement-analysis-table");
    await user.click(screen.getByTestId("balance-movement-analysis-refresh"));

    const message = await screen.findByTestId("balance-movement-analysis-refresh-message");
    expect(message).toHaveTextContent("queued: 2026-04-30");
    expect(message).not.toHaveTextContent("completed");
    expect(datesSpy).toHaveBeenCalledTimes(1);
  });

  it("surfaces governed result_meta in the Figma provenance section", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const evidenceClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            trace_id: "tr_balance_movement_evidence_test",
            source_version: "sv_balance_movement_evidence_test",
            rule_version: "rv_balance_movement_evidence_test",
            tables_used: [
              "fact_accounting_asset_movement_monthly",
              "product_category_pnl_canonical_fact",
            ],
            evidence_rows: 192,
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: evidenceClient,
    });

    const evidenceStrip = await screen.findByTestId("balance-movement-analysis-evidence-strip");
    expect(evidenceStrip).toHaveTextContent("EVIDENCE & PROVENANCE");
    expect(evidenceStrip).toHaveTextContent("tr_balance_movement_evidence_test");
    expect(evidenceStrip).toHaveTextContent("fact_accounting_asset_movement_monthly");
    expect(evidenceStrip).toHaveTextContent("product_category_pnl_canonical_fact");
    expect(evidenceStrip).toHaveTextContent("192 rows");
    expect(evidenceStrip).toHaveTextContent("rv_balance_movement_evidence_test");
    expect(evidenceStrip).toHaveTextContent("sv_balance_movement_evidence_test");
  });

  it.each([
    { label: "null", value: null },
    { label: "undefined", value: undefined },
  ])("does not present a $label total balance change as a flat zero", async ({ value }) => {
    const baseClient = createApiClient({ mode: "mock" });
    const missingChangeClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            summary: {
              ...envelope.result.summary,
              balance_change_total: value as unknown as string,
            },
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: missingChangeClient });

    const summary = await screen.findByTestId("balance-movement-analysis-summary");
    const changeCard = within(summary).getByText("本月净增").parentElement;
    expect(changeCard).toHaveTextContent("—");
    expect(changeCard).not.toHaveTextContent("0.00");
    expect(screen.getByTestId("balance-movement-analysis-business-summary")).toHaveTextContent(
      "总变动缺失，暂不判断方向",
    );
    expect(screen.getByTestId("balance-movement-analysis-business-summary")).not.toHaveTextContent(
      "持平 0.00 亿",
    );
    const conclusion = screen.getByTestId("balance-movement-analysis-conclusion");
    expect(conclusion).toHaveTextContent("余额—");
    expect(conclusion).not.toHaveTextContent("余额持平");
  });

  it("keeps a real zero total balance change as flat zero", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const zeroChangeClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            summary: { ...envelope.result.summary, balance_change_total: "0" },
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: zeroChangeClient });

    const summary = await screen.findByTestId("balance-movement-analysis-summary");
    expect(within(summary).getByText("本月净增").parentElement).toHaveTextContent("0.00 亿");
    expect(screen.getByTestId("balance-movement-analysis-business-summary")).toHaveTextContent(
      "本月总余额持平 0.00 亿",
    );
    expect(screen.getByTestId("balance-movement-analysis-conclusion")).toHaveTextContent(
      "余额持平",
    );
  });

  it("keeps missing zqtz deltas as em dash without any delta tone", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const missingDeltaClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        const maturity = envelope.result.zqtz_maturity_structure;
        const concentration = envelope.result.zqtz_concentration_analysis;
        return {
          ...envelope,
          result: {
            ...envelope.result,
            zqtz_maturity_structure: maturity
              ? {
                  ...maturity,
                  buckets: maturity.buckets.map((bucket) => ({
                    ...bucket,
                    delta_amount: null as unknown as string,
                  })),
                }
              : maturity,
            zqtz_concentration_analysis: concentration
              ? {
                  ...concentration,
                  dimensions: concentration.dimensions.map((dimension) => ({
                    ...dimension,
                    items: dimension.items.map((item) => ({ ...item, delta_amount: null })),
                  })),
                }
              : concentration,
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: missingDeltaClient });

    const maturitySection = await screen.findByTestId("balance-movement-analysis-zqtz-maturity");
    expect(within(maturitySection).getAllByText("— 亿").length).toBeGreaterThan(0);
    expect(
      maturitySection.querySelectorAll(".balance-movement-top-moves-table__delta"),
    ).toHaveLength(0);

    const concentrationSection = screen.getByTestId(
      "balance-movement-analysis-zqtz-concentration",
    );
    const firstConcentrationDelta = concentrationSection.querySelector(
      ".balance-movement-concentration-row em",
    );
    expect(firstConcentrationDelta).toHaveTextContent("—");
    expect(
      concentrationSection.querySelectorAll(".balance-movement-top-moves-table__delta"),
    ).toHaveLength(0);
  });

  it("keeps real zero zqtz deltas on the flat delta tone", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const zeroDeltaClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        const maturity = envelope.result.zqtz_maturity_structure;
        const concentration = envelope.result.zqtz_concentration_analysis;
        return {
          ...envelope,
          result: {
            ...envelope.result,
            zqtz_maturity_structure: maturity
              ? {
                  ...maturity,
                  buckets: maturity.buckets.map((bucket) => ({ ...bucket, delta_amount: "0" })),
                }
              : maturity,
            zqtz_concentration_analysis: concentration
              ? {
                  ...concentration,
                  dimensions: concentration.dimensions.map((dimension) => ({
                    ...dimension,
                    items: dimension.items.map((item) => ({ ...item, delta_amount: "0" })),
                  })),
                }
              : concentration,
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: zeroDeltaClient });

    const maturitySection = await screen.findByTestId("balance-movement-analysis-zqtz-maturity");
    const flatMaturityDeltas = Array.from(
      maturitySection.querySelectorAll(".balance-movement-top-moves-table__delta"),
    );
    expect(flatMaturityDeltas.length).toBeGreaterThan(0);
    for (const deltaElement of flatMaturityDeltas) {
      expect(deltaElement.className).toBe("balance-movement-top-moves-table__delta");
      expect(deltaElement).toHaveTextContent("0.00 亿");
    }

    const concentrationSection = screen.getByTestId(
      "balance-movement-analysis-zqtz-concentration",
    );
    const flatConcentrationDeltas = Array.from(
      concentrationSection.querySelectorAll(".balance-movement-top-moves-table__delta"),
    );
    expect(flatConcentrationDeltas.length).toBeGreaterThan(0);
    for (const deltaElement of flatConcentrationDeltas) {
      expect(deltaElement.className).toBe("balance-movement-top-moves-table__delta");
      expect(deltaElement).toHaveTextContent("0.00");
    }
  });

  it.each([
    { label: "null", value: null },
    { label: "undefined", value: undefined },
    { label: "NaN", value: "NaN" },
  ])("keeps a $label driver contribution missing instead of coercing it to zero", async ({ value }) => {
    const baseClient = createApiClient({ mode: "mock" });
    const missingContributionClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: envelope.result.rows.map((row) =>
              row.basis_bucket === "TPL"
                ? {
                    ...row,
                    contribution_pct: value as unknown as string,
                  }
                : row,
            ),
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: missingContributionClient });

    const businessSummary = await screen.findByTestId("balance-movement-analysis-business-summary");
    expect(businessSummary).toHaveTextContent("TPL +51.63 亿 · 贡献 —");
    expect(businessSummary).not.toHaveTextContent("TPL +51.63 亿 · 贡献 0.00%");
    const ranking = screen.getByTestId("balance-movement-analysis-driver-ranking");
    expect(ranking).toHaveTextContent("TPL+51.63 亿 · —");
    const compactBand = screen.getByTestId("balance-movement-driver-composition-band");
    expect(compactBand).toHaveAttribute("data-state", "unavailable");
    expect(compactBand).toHaveAccessibleName("变动贡献构成：数据不可用");
    expect(compactBand).not.toHaveAccessibleName(/0\.00%/);
  });

  it("keeps a real zero driver contribution as 0.00%", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const zeroContributionClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: envelope.result.rows.map((row) =>
              row.basis_bucket === "TPL" ? { ...row, contribution_pct: "0" } : row,
            ),
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: zeroContributionClient });

    const businessSummary = await screen.findByTestId("balance-movement-analysis-business-summary");
    expect(businessSummary).toHaveTextContent("TPL +51.63 亿 · 贡献 0.00%");
    expect(screen.getByTestId("balance-movement-analysis-driver-ranking")).toHaveTextContent(
      "TPL+51.63 亿 · 0.00%",
    );
    expect(screen.getByTestId("balance-movement-driver-composition-band")).toHaveAttribute(
      "data-state",
      "available",
    );
  });

  it("surfaces stale fallback dates on the first screen", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const staleFallbackClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result_meta: {
            ...envelope.result_meta,
            quality_flag: "stale",
            fallback_mode: "latest_snapshot",
            requested_report_date: "2026-04-30",
            resolved_report_date: "2026-03-31",
            fallback_date: "2026-03-31",
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: staleFallbackClient });

    const status = await screen.findByTestId("balance-movement-analysis-result-status");
    expect(status).toHaveTextContent("数据质量异常，仅供参考");
    const visibleFacts = within(status).getByTestId("balance-movement-analysis-result-status-facts");
    expect(visibleFacts.closest("details")).toBeNull();
    expect(visibleFacts).toHaveTextContent("请求报告日 2026-04-30");
    expect(visibleFacts).toHaveTextContent("实际快照日 2026-03-31");
    expect(visibleFacts).toHaveTextContent("回退日期 2026-03-31");
  });

  it("keeps legacy result metadata without optional dates renderable", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const legacyMetaClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        const resultMeta = { ...envelope.result_meta };
        delete resultMeta.requested_report_date;
        delete resultMeta.resolved_report_date;
        delete resultMeta.fallback_date;
        return { ...envelope, result_meta: resultMeta };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], { client: legacyMetaClient });

    expect(await screen.findByTestId("balance-movement-analysis-evidence-strip")).toBeInTheDocument();
    expect(screen.queryByTestId("balance-movement-analysis-result-status")).not.toBeInTheDocument();
  });

  it("exports the current evidence view as a local csv without adding an API call", async () => {
    const user = userEvent.setup();
    const createObjectUrl = vi.fn((_blob: Blob) => "blob:balance-movement-analysis");
    const revokeObjectUrl = vi.fn();
    const clickSpy = vi.fn();
    const originalCreateObjectURL = globalThis.URL.createObjectURL;
    const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;
    const originalCreateElement = document.createElement.bind(document);

    globalThis.URL.createObjectURL = createObjectUrl;
    globalThis.URL.revokeObjectURL = revokeObjectUrl;
    vi.spyOn(document, "createElement").mockImplementation(((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", {
          configurable: true,
          value: clickSpy,
        });
      }
      return element;
    }) as typeof document.createElement);

    try {
      renderWorkbenchApp(["/balance-movement-analysis"], {
        client: createApiClient({ mode: "mock" }),
      });

      await screen.findByTestId("balance-movement-analysis-table");
      await user.click(screen.getByTestId("balance-movement-analysis-export-csv"));

      expect(createObjectUrl).toHaveBeenCalledTimes(1);
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(revokeObjectUrl).toHaveBeenCalledWith("blob:balance-movement-analysis");
      const firstCreateObjectUrlCall = createObjectUrl.mock.calls[0];
      expect(firstCreateObjectUrlCall).toBeDefined();
      const blob = firstCreateObjectUrlCall![0];
      expect(blob).toBeInstanceOf(Blob);
      const csv = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result ?? ""));
        reader.onerror = () => reject(reader.error);
        reader.readAsText(blob);
      });
      expect(csv).toContain("report_date");
      expect(csv).toContain("currency_basis");
      expect(csv).toContain("rule_version");
      expect(csv).toContain("source_version");
      expect(csv).toContain("diagnostic");
      expect(csv).toContain("explanation_closure");
      expect(csv).toContain("unsupported_components");
      expect(csv).toContain("口径待补");
      expect(csv).toContain("residual_ratio");
      expect(csv).toContain("diagnostic,residual_ratio,1.95%");
      expect(csv).toContain("historical_anomaly");
      expect(csv).toContain("sample_count");
      expect(csv).toContain("历史样本不足");
      expect(csv).toContain("basis_bucket");
      expect(csv).toContain("AC");
      expect(csv).toContain("OCI");
      expect(csv).toContain("TPL");
      expect(csv).toContain("估值差");
      expect(csv).toContain("待拆分");
    } finally {
      globalThis.URL.createObjectURL = originalCreateObjectURL;
      globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
      vi.restoreAllMocks();
    }
  });

  it("renders explanation closure diagnostics without treating unsupported valuation or fx gaps as explained zeroes", async () => {
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    const explanationClosure = await screen.findByTestId(
      "balance-movement-analysis-explanation-closure",
    );
    expect(explanationClosure).toHaveTextContent("解释闭合度");
    expect(explanationClosure).toHaveTextContent("已支持解释项");
    expect(explanationClosure).toHaveTextContent("未支持项");
    expect(explanationClosure).toHaveTextContent("未分类 / 残差");
    expect(explanationClosure).toHaveTextContent("估值差");
    expect(explanationClosure).toHaveTextContent("外币折算差");
    expect(explanationClosure).toHaveTextContent("未支持，不反推");
    expect(explanationClosure).toHaveTextContent("1.95%");
    expect(explanationClosure).not.toHaveTextContent("估值差+0.00 亿");
    expect(explanationClosure).not.toHaveTextContent("外币折算差+0.00 亿");
  });

  it("renders the Figma-first compact sequence before the retained detail modules", async () => {
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    const kpiRibbon = await screen.findByTestId("balance-movement-analysis-summary");
    const decisionHero = screen.getByTestId("balance-movement-analysis-decision-hero");
    const driversAndStructure = screen.getByTestId("balance-movement-analysis-drivers-structure");
    const maturityAndConcentration = screen.getByTestId(
      "balance-movement-analysis-maturity-concentration",
    );
    const evidence = screen.getByTestId("balance-movement-analysis-evidence-strip");
    const accountingBuckets = screen.getByTestId("balance-movement-analysis-accounting-buckets");
    const detailedBusiness = screen.getByTestId("balance-movement-analysis-business-summary");

    const orderedSections = [
      decisionHero,
      kpiRibbon,
      driversAndStructure,
      maturityAndConcentration,
      evidence,
      accountingBuckets,
      detailedBusiness,
    ];
    for (let index = 0; index < orderedSections.length - 1; index += 1) {
      expect(
        orderedSections[index]!.compareDocumentPosition(orderedSections[index + 1]!)
        & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    }
  });

  it("preserves backend coverage values in the compact maturity and concentration panel", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const lowCoverageClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            zqtz_maturity_structure: envelope.result.zqtz_maturity_structure
              ? {
                  ...envelope.result.zqtz_maturity_structure,
                  meta: {
                    ...envelope.result.zqtz_maturity_structure.meta,
                    coverage_pct: "79.00",
                  },
                }
              : envelope.result.zqtz_maturity_structure,
            zqtz_concentration_analysis: envelope.result.zqtz_concentration_analysis
              ? {
                  ...envelope.result.zqtz_concentration_analysis,
                  meta: {
                    ...envelope.result.zqtz_concentration_analysis.meta,
                    coverage_pct: "94.00",
                  },
                  dimensions: envelope.result.zqtz_concentration_analysis.dimensions.map(
                    (dimension, index) =>
                      index === 0 ? { ...dimension, coverage_pct: "94.00" } : dimension,
                  ),
                }
              : envelope.result.zqtz_concentration_analysis,
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: lowCoverageClient,
    });

    const compactPanel = await screen.findByTestId(
      "balance-movement-analysis-maturity-concentration",
    );
    expect(compactPanel).toHaveTextContent("覆盖率 79.00%");
    expect(compactPanel).toHaveTextContent("主体覆盖 94.00%");
  });

  it("renders backend-provided unsupported and no-data drilldown states", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const statusMatrixClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        const basis = envelope.result.basis_movement_decomposition;
        const maturity = envelope.result.zqtz_maturity_structure;
        const concentration = envelope.result.zqtz_concentration_analysis;

        return {
          ...envelope,
          result: {
            ...envelope.result,
            basis_movement_decomposition: basis
              ? {
                  ...basis,
                  meta: {
                    ...basis.meta,
                    status: "no_data" as const,
                    covered_total: null,
                    unknown_total: null,
                    coverage_pct: null,
                    caveat: "No governed basis rows returned for this date.",
                  },
                  buckets: basis.buckets.map((bucket) => ({
                    ...bucket,
                    rows: [],
                  })),
                }
              : basis,
            zqtz_maturity_structure: maturity
              ? {
                  ...maturity,
                  meta: {
                    ...maturity.meta,
                    status: "unsupported_missing_columns" as const,
                    covered_total: "0",
                    unknown_total: maturity.meta.eligible_total,
                    coverage_pct: null,
                    caveat: "maturity_date source column is absent.",
                  },
                  buckets: maturity.buckets.map((bucket) => ({
                    ...bucket,
                    share_pct: null,
                  })),
                }
              : maturity,
            zqtz_concentration_analysis: concentration
              ? {
                  ...concentration,
                  meta: {
                    ...concentration.meta,
                    status: "unsupported_low_coverage" as const,
                    covered_total: null,
                    unknown_total: null,
                    coverage_pct: null,
                    caveat:
                      "Issuer, rating, and industry concentration may differ in coverage; inspect each dimension status.",
                  },
                  dimensions: concentration.dimensions.map((dimension, index) => {
                    if (index === 0) {
                      return {
                        ...dimension,
                        status: "unsupported_missing_columns" as const,
                        coverage_pct: null,
                        hhi: null,
                        top5_share_pct: null,
                        items: [],
                        caveat: "Source column issuer_name is absent.",
                      };
                    }
                    if (index === 1) {
                      return {
                        ...dimension,
                        status: "unsupported_low_coverage" as const,
                        coverage_pct: "25.00",
                        hhi: null,
                        top5_share_pct: null,
                        items: [],
                        caveat: "rating coverage is below 80%; rankings are not rendered.",
                      };
                    }
                    return {
                      ...dimension,
                      status: "no_data" as const,
                      coverage_pct: null,
                      hhi: null,
                      top5_share_pct: null,
                      items: [],
                      caveat: "No eligible ZQTZ asset population.",
                    };
                  }),
                }
              : concentration,
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: statusMatrixClient,
    });

    const basisPanel = await screen.findByTestId(
      "balance-movement-analysis-basis-decomposition",
    );
    expect(basisPanel).toHaveTextContent("无数据");
    expect(basisPanel).toHaveTextContent("No governed basis rows returned for this date.");

    const maturityPanel = screen.getByTestId("balance-movement-analysis-zqtz-maturity");
    expect(maturityPanel).toHaveTextContent("字段不足");
    expect(maturityPanel).toHaveTextContent("maturity_date source column is absent.");

    const concentrationPanel = screen.getByTestId("balance-movement-analysis-zqtz-concentration");
    expect(concentrationPanel).toHaveTextContent("覆盖率不足");
    expect(concentrationPanel).toHaveTextContent("字段不足");
    expect(concentrationPanel).toHaveTextContent("无数据");
    expect(concentrationPanel).toHaveTextContent("Source column issuer_name is absent.");
    expect(concentrationPanel).toHaveTextContent(
      "rating coverage is below 80%; rankings are not rendered.",
    );
    expect(concentrationPanel).toHaveTextContent("No eligible ZQTZ asset population.");
    expect(screen.getByTestId("balance-movement-maturity-spectrum")).toHaveAttribute(
      "data-state",
      "unavailable",
    );
    expect(screen.getByTestId("balance-movement-maturity-coverage-band")).toHaveAttribute(
      "data-state",
      "unavailable",
    );
    expect(screen.getByTestId("balance-movement-top5-gauge")).toHaveAttribute(
      "data-state",
      "unavailable",
    );
    expect(screen.getByTestId("balance-movement-top5-gauge")).toHaveTextContent(
      "—数据不可用",
    );
  });

  it("keeps the compact accounting buckets reviewable without a separate evidence drawer", async () => {
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    const compactBuckets = await screen.findByTestId("balance-movement-analysis-accounting-buckets");
    expect(within(compactBuckets).getAllByRole("row")).toHaveLength(4);
    expect(compactBuckets).toHaveTextContent("期初余额");
    expect(compactBuckets).toHaveTextContent("期末余额");
    expect(compactBuckets).toHaveTextContent("变动贡献");
    expect(within(compactBuckets).getByRole("row", { name: /AC/ })).toHaveTextContent("一致");
    expect(within(compactBuckets).getByRole("row", { name: /OCI/ })).toHaveTextContent("一致");
    expect(within(compactBuckets).getByRole("row", { name: /TPL/ })).toHaveTextContent("一致");
    expect(screen.queryByRole("complementary", { name: "分析维度证据" })).not.toBeInTheDocument();
  });

  it("flags accounting and business moves that exceed recent historical baseline", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const anomalyClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await baseClient.getBalanceMovementAnalysis(options);
        const currentRows = envelope.result.rows;
        const currentBusinessRows = envelope.result.business_trend_months[0].rows;
        const trendMonth = (
          reportDate: string,
          reportMonth: string,
          balances: Record<"AC" | "OCI" | "TPL", number>,
        ) => ({
          report_date: reportDate,
          report_month: reportMonth,
          current_balance_total: String(balances.AC + balances.OCI + balances.TPL),
          balance_change_total: "0",
          rows: currentRows.map((row) => ({
            ...row,
            report_date: reportDate,
            report_month: reportMonth,
            current_balance: String(balances[row.basis_bucket]),
          })),
        });
        const businessMonth = (
          reportDate: string,
          reportMonth: string,
          interbankLending: number,
        ) => ({
          report_date: reportDate,
          report_month: reportMonth,
          asset_balance_total: String(interbankLending),
          liability_balance_total: "0",
          net_balance_total: String(interbankLending),
          rows: currentBusinessRows.map((row) => ({
            ...row,
            report_date: reportDate,
            report_month: reportMonth,
            current_balance:
              row.row_key === "asset_interbank_lending"
                ? String(interbankLending)
                : row.current_balance,
          })),
        });
        return {
          ...envelope,
          result: {
            ...envelope.result,
            trend_months: [
              trendMonth("2026-04-30", "2026-04", {
                AC: 100000000000,
                OCI: 50000000000,
                TPL: 80000000000,
              }),
              trendMonth("2026-03-31", "2026-03", {
                AC: 90000000000,
                OCI: 50000000000,
                TPL: 50000000000,
              }),
              trendMonth("2026-02-28", "2026-02", {
                AC: 92000000000,
                OCI: 49000000000,
                TPL: 48000000000,
              }),
              trendMonth("2026-01-31", "2026-01", {
                AC: 91000000000,
                OCI: 50000000000,
                TPL: 47000000000,
              }),
            ],
            business_trend_months: [
              businessMonth("2026-04-30", "2026-04", 15000000000),
              businessMonth("2026-03-31", "2026-03", 5000000000),
              businessMonth("2026-02-28", "2026-02", 4000000000),
              businessMonth("2026-01-31", "2026-01", 3500000000),
            ],
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: anomalyClient,
    });

    const anomalyDiagnostics = await screen.findByTestId(
      "balance-movement-analysis-anomaly-diagnostics",
    );
    expect(anomalyDiagnostics).toHaveTextContent("历史异常定位");
    expect(anomalyDiagnostics).toHaveTextContent("TPL");
    expect(anomalyDiagnostics).toHaveTextContent("高于近 2 期常态");
    expect(anomalyDiagnostics).toHaveTextContent("方向反转");
    expect(anomalyDiagnostics).toHaveTextContent("业务品类异常榜");
    expect(anomalyDiagnostics).toHaveTextContent("资产端-拆放同业");
    expect(anomalyDiagnostics).toHaveTextContent("+100.00 亿");
    expect(anomalyDiagnostics).toHaveTextContent("页面诊断提示，不是正式风险指标");
  });

  it("suppresses the month-over-month conclusion when available snapshots are not adjacent", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const sparseClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            trend_months: envelope.result.trend_months.map((month, index) =>
              index === 1
                ? {
                    ...month,
                    report_date: "2025-12-31",
                    report_month: "2025-12",
                  }
                : month,
            ),
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: sparseClient,
    });

    expect(await screen.findByTestId("balance-movement-analysis-trend-table")).toBeInTheDocument();
    expect(screen.queryByTestId("balance-movement-analysis-trend-conclusion")).not.toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-series-context")).toHaveTextContent(
      "非连续",
    );
  });

  it("surfaces ZQTZ recon issues when any bucket is not matched", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const mismatchClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        const [firstRow, ...restRows] = envelope.result.rows;
        return {
          ...envelope,
          result: {
            ...envelope.result,
            summary: {
              ...envelope.result.summary,
              matched_bucket_count: 2,
            },
            rows: [
              {
                ...firstRow,
                reconciliation_status: "mismatch",
                reconciliation_diff: "100000000",
              },
              ...restRows,
            ],
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: mismatchClient,
    });

    const compactBuckets = await screen.findByTestId("balance-movement-analysis-accounting-buckets");
    const conclusion = screen.getByTestId("balance-movement-analysis-conclusion");
    expect(conclusion).toHaveTextContent("分桶对不平");
    expect(screen.getByTestId("balance-movement-analysis-freshness")).toHaveTextContent(
      "Reconciliation分桶对不平",
    );
    expect(screen.getByTestId("balance-movement-analysis-summary")).toHaveTextContent(
      "对账状态分桶对不平",
    );
    const reconciliationSignal = within(
      screen.getByTestId("balance-movement-analysis-summary"),
    ).getAllByTestId("balance-movement-kpi-signal")[3];
    expect(reconciliationSignal).toHaveAttribute("data-state", "review");
    expect(reconciliationSignal).not.toHaveAttribute("data-state", "matched");
    expect(within(compactBuckets).getByRole("row", { name: /AC/ })).toHaveTextContent("对不平");
  });

  describe("对账结论三态区分", () => {
    function threeStateClient() {
      const baseClient = createApiClient({ mode: "mock" });
      const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
      return {
        ...baseClient,
        async getBalanceMovementAnalysis(
          options: Parameters<typeof getBalanceMovementAnalysis>[0],
        ) {
          const envelope = await getBalanceMovementAnalysis(options);
          const [acRow, ociRow, tplRow] = envelope.result.rows;
          return {
            ...envelope,
            result: {
              ...envelope.result,
              summary: { ...envelope.result.summary, matched_bucket_count: 0 },
              rows: [
                // 两侧都有余额但金额不符。
                {
                  ...acRow,
                  reconciliation_status: "mismatch" as const,
                  reconciliation_diff: "100000000",
                  chain_status: "continuous" as const,
                },
                // 头寸源当期整体缺失：没有对手方可比。
                {
                  ...ociRow,
                  reconciliation_status: "gl_only" as const,
                  zqtz_amount: "0",
                  reconciliation_diff: "-105781745231.25",
                  chain_status: "continuous" as const,
                  position_source_basis: "unavailable",
                },
                // 横截面对得上，但本月期初接不上上月期末。
                {
                  ...tplRow,
                  reconciliation_status: "chain_broken" as const,
                  chain_status: "broken" as const,
                },
              ],
            },
          };
        },
      };
    }

    it("labels gl_only, mismatch and chain_broken as three different states", async () => {
      renderWorkbenchApp(["/balance-movement-analysis"], { client: threeStateClient() });

      const buckets = await screen.findByTestId("balance-movement-analysis-accounting-buckets");
      const statusCells = within(buckets)
        .getAllByTitle(/./)
        .map((node) => ({
          text: node.textContent,
          status: node.getAttribute("data-status"),
          tone: node.getAttribute("data-tone"),
        }));

      expect(statusCells).toEqual([
        { text: "对不平", status: "mismatch", tone: "mismatch" },
        { text: "无头寸对手方", status: "gl_only", tone: "no-counterparty" },
        { text: "跨月断裂", status: "chain_broken", tone: "chain-broken" },
      ]);
      // 三个结论必须落在三种色阶上，不能塌成"匹配 / 不匹配"两态。
      expect(new Set(statusCells.map((cell) => cell.tone)).size).toBe(3);
    });

    it("shows 不适用 instead of a fabricated diff when there is no position counterparty", async () => {
      renderWorkbenchApp(["/balance-movement-analysis"], { client: threeStateClient() });

      const table = await screen.findByTestId("balance-movement-analysis-table");
      const ociCells = within(table)
        .getAllByRole("row")
        .map((row) => Array.from(row.querySelectorAll("td")).map((cell) => cell.textContent))
        .find((cells) => cells[0]?.includes("OCI"));

      // ZQTZ辅助 与 ZQTZ诊断差异 两列：印 0 会被读成"辅助账为零"，
      // 印 -1057.82 亿 会被读成真实缺口，两者都不是这行的事实。
      expect(ociCells?.slice(9, 11)).toEqual(["不适用", "不适用"]);
      expect(ociCells).not.toContain("-1,057.82");
    });

    it("reports the real tie-out counts instead of a hardcoded 3 / 3 matched", async () => {
      renderWorkbenchApp(["/balance-movement-analysis"], { client: threeStateClient() });

      await screen.findByTestId("balance-movement-analysis-table");
      const tieout = document.querySelector(".balance-movement-business-matrix__tieout");

      expect(tieout).toHaveTextContent("0 / 3 一致");
      expect(tieout).toHaveTextContent("对不平 1");
      expect(tieout).toHaveTextContent("无头寸对手方 1");
      expect(tieout).toHaveTextContent("跨月断裂 1");
      expect(tieout).toHaveTextContent("跨月勾稽 衔接 2 · 断裂 1");
      expect(tieout).not.toHaveTextContent("3 / 3 matched");
    });

    it("keeps an unrecorded chain status distinct from a judged one", async () => {
      const baseClient = createApiClient({ mode: "mock" });
      const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
      const legacyClient: typeof baseClient = {
        ...baseClient,
        async getBalanceMovementAnalysis(options) {
          const envelope = await getBalanceMovementAnalysis(options);
          return {
            ...envelope,
            result: {
              ...envelope.result,
              rows: envelope.result.rows.map((row) => ({ ...row, chain_status: null })),
            },
          };
        },
      };

      renderWorkbenchApp(["/balance-movement-analysis"], { client: legacyClient });

      const table = await screen.findByTestId("balance-movement-analysis-table");
      // 迁移落地前写入的行没有判定过跨月勾稽，不能显示成"无上月基准"。
      expect(within(table).getAllByText("未记录")).toHaveLength(3);
      expect(within(table).queryByText("无上月基准")).not.toBeInTheDocument();
    });
  });

  it("flags incomplete bucket payloads instead of presenting 3 / 3 matched", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const incompleteBucketClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: envelope.result.rows.map((row) =>
              row.basis_bucket === "TPL" ? { ...row, basis_bucket: "AC" } : row,
            ),
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: incompleteBucketClient,
    });

    const freshness = await screen.findByTestId("balance-movement-analysis-freshness");
    const summary = await screen.findByTestId("balance-movement-analysis-summary");
    expect(summary).toHaveTextContent("分桶不完整");
    expect(freshness).not.toHaveTextContent("3 / 3 matched");
    expect(summary).not.toHaveTextContent("3 / 3 匹配");
  });

  it("requires the summary matched count before presenting 3 / 3 matched", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const unmatchedSummaryClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            summary: {
              ...envelope.result.summary,
              matched_bucket_count: 2,
            },
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: unmatchedSummaryClient,
    });

    const freshness = await screen.findByTestId("balance-movement-analysis-freshness");
    const summary = await screen.findByTestId("balance-movement-analysis-summary");
    expect(summary).toHaveTextContent("需关注");
    expect(freshness).not.toHaveTextContent("3 / 3 matched");
    expect(summary).not.toHaveTextContent("3 / 3 匹配");
  });

  it("requires the summary bucket count before treating the bucket set as complete", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const incompleteSummaryClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            summary: {
              ...envelope.result.summary,
              bucket_count: 2,
            },
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: incompleteSummaryClient,
    });

    const freshness = await screen.findByTestId("balance-movement-analysis-freshness");
    const summary = await screen.findByTestId("balance-movement-analysis-summary");
    expect(summary).toHaveTextContent("分桶不完整");
    expect(freshness).not.toHaveTextContent("3 / 3 matched");
    expect(summary).not.toHaveTextContent("3 / 3 匹配");
  });

  it("uses accounting basis labels in the business summary without FVAC or FVOCI", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const acDriverClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        return {
          ...envelope,
          result: {
            ...envelope.result,
            rows: envelope.result.rows.map((row) => {
              if (row.basis_bucket === "AC") {
                return {
                  ...row,
                  balance_change: "9900000000",
                  contribution_pct: "80.00",
                };
              }
              if (row.basis_bucket === "TPL") {
                return {
                  ...row,
                  balance_change: "100000000",
                  contribution_pct: "1.00",
                };
              }
              return row;
            }),
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: acDriverClient,
    });

    const businessSummary = await screen.findByTestId(
      "balance-movement-analysis-business-summary",
    );
    const decisionHero = screen.getByTestId("balance-movement-analysis-decision-hero");
    expect(businessSummary).toHaveTextContent("AC 占比至");
    expect(businessSummary).not.toHaveTextContent("FVAC");
    expect(businessSummary).not.toHaveTextContent("FVOCI");
    expect(decisionHero).toHaveTextContent("AC 结构占比");
    expect(decisionHero).not.toHaveTextContent("FVAC");
    expect(decisionHero).not.toHaveTextContent("FVOCI");
  });

  it("keeps compact maturity unknown amount driven by meta unknown_total", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const maturityMetaClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        const structure = envelope.result.zqtz_maturity_structure;
        return {
          ...envelope,
          result: {
            ...envelope.result,
            zqtz_maturity_structure: structure
              ? {
                  ...structure,
                  meta: {
                    ...structure.meta,
                    unknown_total: "12300000000",
                  },
                  buckets: structure.buckets.filter(
                    (bucket) => bucket.maturity_bucket !== "unknown",
                  ),
                }
              : structure,
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: maturityMetaClient,
    });

    const compactPanel = await screen.findByTestId(
      "balance-movement-analysis-maturity-concentration",
    );
    expect(compactPanel).toHaveTextContent("未映射到期日金额 123.00 亿");
  });

  it("keeps optional drilldown modules visible when the backend omits them", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const getBalanceMovementAnalysis = baseClient.getBalanceMovementAnalysis;
    const missingDrilldownClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementAnalysis(options) {
        const envelope = await getBalanceMovementAnalysis(options);
        const result = { ...envelope.result };
        delete result.basis_movement_decomposition;
        delete result.zqtz_maturity_structure;
        delete result.zqtz_concentration_analysis;

        return {
          ...envelope,
          result,
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: missingDrilldownClient,
    });

    expect(await screen.findByTestId("balance-movement-analysis-basis-decomposition")).toHaveTextContent(
      "当前接口未返回 basis_movement_decomposition",
    );
    expect(screen.getByTestId("balance-movement-analysis-zqtz-maturity")).toHaveTextContent(
      "当前接口未返回 zqtz_maturity_structure",
    );
    expect(screen.getByTestId("balance-movement-analysis-zqtz-concentration")).toHaveTextContent(
      "当前接口未返回 zqtz_concentration_analysis",
    );
  });

  it("surfaces date loading failures before the empty detail section", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const failingDatesClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementDates() {
        throw new Error("dates unavailable");
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: failingDatesClient,
    });

    expect(await screen.findByTestId("balance-movement-analysis-date-status")).toHaveTextContent(
      "报告日期加载失败",
    );
    expect(screen.getByTestId("balance-movement-analysis-date-status")).toHaveTextContent(
      "请确认后端 7888 服务与余额变动读模型可用",
    );
  });

  it("keeps an in-flight detail request distinct from an empty read model", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const loadingDetailClient: typeof baseClient = {
      ...baseClient,
      getBalanceMovementAnalysis: () => new Promise<never>(() => undefined),
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: loadingDetailClient,
    });

    const loadingHero = await screen.findByTestId(
      "balance-movement-analysis-loading-hero",
    );
    expect(loadingHero).toHaveAttribute("aria-busy", "true");
    expect(loadingHero).toHaveTextContent("正在读取余额变动分析");
    expect(loadingHero).not.toHaveTextContent("等待物化");
  });

  it("surfaces an empty materialized date set instead of only showing an empty table", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const emptyDatesClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementDates(currencyBasis = "CNX") {
        return buildMockApiEnvelope("balance-analysis.movement.dates", {
          report_dates: [],
          currency_basis: currencyBasis,
        });
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: emptyDatesClient,
    });

    expect(await screen.findByTestId("balance-movement-analysis-date-status")).toHaveTextContent(
      "暂无已物化报告日期",
    );
    expect(screen.getByTestId("balance-movement-analysis-date-status")).toHaveTextContent(
      "CNX",
    );
    const freshness = await screen.findByTestId("balance-movement-analysis-freshness");
    expect(freshness).toHaveClass("balance-movement-data-trust--info");
    expect(freshness).toHaveTextContent("新鲜度待确认");
  });

  it("surfaces when the read model is behind upstream control data", async () => {
    const baseClient = createApiClient({ mode: "mock" });
    const laggingDatesClient: typeof baseClient = {
      ...baseClient,
      async getBalanceMovementDates(currencyBasis = "CNX") {
        return buildMockApiEnvelope("balance-analysis.movement.dates", {
          report_dates: ["2026-04-30"],
          currency_basis: currencyBasis,
          latest_read_model_report_date: "2026-04-30",
          latest_upstream_control_report_date: "2026-05-31",
          freshness_status: "read_model_lagging",
        });
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: laggingDatesClient,
    });

    const freshness = await screen.findByTestId("balance-movement-analysis-freshness");
    expect(freshness).toHaveClass("balance-movement-data-trust--warn");
    expect(freshness).toHaveTextContent("读模型落后上游");
    expect(freshness).toHaveTextContent("2026-05-31");
    expect(freshness).toHaveTextContent("2026-04-30");
  });
});
