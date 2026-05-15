import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { createApiClient } from "../api/client";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="balance-movement-echarts-stub" />,
}));

describe("BalanceMovementAnalysisPage", () => {
  it("renders AC OCI TPL balance movement from the governed read model", async () => {
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("balance-movement-analysis-title")).toHaveTextContent(
      "余额变动分析",
    );
    expect(await screen.findByTestId("balance-movement-analysis-summary")).toHaveTextContent(
      "3,358.73",
    );
    const conclusion = await screen.findByTestId("balance-movement-analysis-conclusion");
    expect(conclusion).toHaveTextContent("总账控制核对通过");
    expect(screen.getByTestId("balance-movement-analysis-recon-summary")).toHaveTextContent(
      "ZQTZ 分桶对账",
    );
    expect(screen.getByTestId("balance-movement-analysis-recon-summary")).toHaveTextContent("一致");
    expect(conclusion).toHaveTextContent("3,358.73 亿");
    expect(conclusion).toHaveTextContent("AC 42.44%");
    expect(conclusion).toHaveTextContent("OCI 31.49%");
    expect(conclusion).toHaveTextContent("TPL 26.07%");
    expect(conclusion).toHaveTextContent("排除 144020 股权 OCI");
    expect(conclusion).toHaveTextContent("ZQTZ 诊断同步读取 CNX 余额表");
    expect(screen.getByTestId("balance-movement-analysis-diagnostic-reason")).toHaveTextContent(
      "口径差异原因",
    );
    expect(screen.getByTestId("balance-movement-analysis-diagnostic-reason")).toHaveTextContent(
      "ZQTZ 诊断应使用 CNX 表",
    );
    expect(screen.getByTestId("balance-movement-analysis-diagnostic-reason")).toHaveTextContent(
      "误读 CNY",
    );
    expect(await screen.findByTestId("balance-movement-analysis-trend-conclusion")).toHaveTextContent(
      "较 2026-01-31 +129.80 亿",
    );
    expect(screen.getByTestId("balance-movement-analysis-trend-conclusion")).toHaveTextContent(
      "TPL +51.63 亿、OCI +44.87 亿、AC +33.29 亿",
    );
    const evidenceStrip = await screen.findByTestId("balance-movement-analysis-evidence-strip");
    expect(evidenceStrip).toHaveTextContent("quality_flag");
    expect(evidenceStrip).toHaveTextContent("ok");
    expect(evidenceStrip).toHaveTextContent("trace_id");
    expect(evidenceStrip).toHaveTextContent("mock_balance-analysis.movement.detail");
    const dimensionOverview = await screen.findByTestId(
      "balance-movement-analysis-dimension-overview",
    );
    expect(dimensionOverview).toHaveTextContent("分析维度总览");
    expect(dimensionOverview.querySelectorAll(".balance-movement-dimension-card")).toHaveLength(4);
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-business")).toHaveTextContent(
      "业务品类 Top 变动",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-business")).toHaveTextContent(
      "资产端-拆放同业 +30.00 亿",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-basis")).toHaveTextContent(
      "AC / OCI / FVTPL",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-basis")).toHaveTextContent(
      "TPL +51.63 亿",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-residual")).toHaveTextContent(
      "对账残差",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-residual")).toHaveTextContent(
      "估值差、外币折算差 未支持，不反推",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-coverage")).toHaveTextContent(
      "期限 / 集中度覆盖",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-coverage")).toHaveTextContent(
      "期限 99.15% / 集中度 97.68%",
    );
    const anomalyDiagnostics = await screen.findByTestId(
      "balance-movement-analysis-anomaly-diagnostics",
    );
    expect(anomalyDiagnostics).toHaveTextContent("历史异常定位");
    expect(anomalyDiagnostics).toHaveTextContent("历史样本不足");
    expect(anomalyDiagnostics).toHaveTextContent("仅 2 期样本");
    const businessSummary = await screen.findByTestId(
      "balance-movement-analysis-business-summary",
    );
    expect(businessSummary).toHaveTextContent(
      "本月余额增加 129.80 亿，最大驱动是 TPL",
    );
    expect(businessSummary).toHaveTextContent(
      "结构整体稳定，最大占比变化为 AC -0.67pp",
    );
    expect(businessSummary).toHaveTextContent(
      "AC 压舱石占比 42.44%，较期初 -0.67pp",
    );
    expect(businessSummary).toHaveTextContent(
      "OCI 配置占比 31.49%，较期初 +0.12pp",
    );
    expect(businessSummary).toHaveTextContent(
      "TPL 增量最大：+51.63 亿，贡献 39.78%",
    );
    expect(screen.getByTestId("balance-movement-analysis-driver-chart")).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-driver-ranking")).toHaveTextContent(
      "TPL +51.63 亿 39.78%",
    );
    expect(screen.getByTestId("balance-movement-analysis-driver-ranking")).toHaveTextContent(
      "OCI +44.87 亿 34.57%",
    );
    expect(screen.getByTestId("balance-movement-analysis-driver-ranking")).toHaveTextContent(
      "AC +33.29 亿 25.65%",
    );
    expect(screen.getByTestId("balance-movement-analysis-structure-shift")).toHaveTextContent(
      "期初 43.11% 期末 42.44%",
    );
    expect(screen.getByTestId("balance-movement-analysis-structure-driver-hint")).toHaveTextContent(
      "变动额",
    );
    expect(screen.getByTestId("balance-movement-analysis-business-top-moves")).toHaveTextContent(
      "业务行Top变动",
    );
    expect(screen.getByTestId("balance-movement-analysis-business-top-moves")).toHaveTextContent(
      "资产端-拆放同业",
    );
    const topMovesMom = screen.getByTestId("balance-movement-analysis-business-top-moves-mom");
    expect(topMovesMom).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-business-top-moves")).toHaveTextContent("MoM Top 5");
    expect(within(topMovesMom).queryAllByRole("row").length).toBeGreaterThan(1);
    const interbankLendingTopMove = within(topMovesMom)
      .getByText("资产端-拆放同业")
      .closest("tr");
    expect(interbankLendingTopMove).toHaveTextContent("Ledger");
    expect(interbankLendingTopMove).toHaveTextContent("总账对账科目余额");
    const topMovesSix = screen.getByTestId("balance-movement-analysis-business-top-moves-sixmonth");
    expect(topMovesSix).toBeInTheDocument();
    expect(screen.getByTestId("balance-movement-analysis-business-top-moves")).toHaveTextContent("Top 5");
    const topMoveSources = screen.getAllByTestId("balance-movement-analysis-business-top-moves-source");
    expect(topMoveSources.length).toBeGreaterThan(0);
    expect(screen.getByTestId("balance-movement-analysis-slice-note")).toHaveTextContent(
      "总账 AC/OCI/TPL",
    );
    expect(screen.getByTestId("balance-movement-analysis-series-context")).toHaveTextContent(
      "两个月度",
    );
    expect(screen.getByTestId("balance-movement-analysis-governance")).toHaveTextContent(
      "rule_version",
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
    expect(zqtzDetail).toHaveTextContent("单独页");
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

    const matrixTitle = screen.getByText("月度余额分析矩阵");
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
    expect(screen.getAllByTestId("balance-movement-echarts-stub").length).toBeGreaterThanOrEqual(2);
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
    expect(within(trendTable).getByText("分类")).toBeInTheDocument();
    expect(within(trendTable).getByText("项目")).toBeInTheDocument();
    expect(within(trendTable).getAllByText("2026年2月").length).toBeGreaterThan(0);
    expect(within(trendTable).getAllByText("2026年1月").length).toBeGreaterThan(0);
    expect(within(trendTable).getAllByText("较上月").length).toBeGreaterThan(0);
    expect(within(trendTable).getAllByText("较年初").length).toBeGreaterThan(0);
    expect(within(trendTable).getByText("资产端-拆放同业")).toBeInTheDocument();
    expect(within(trendTable).getByText("资产端-买入返售")).toBeInTheDocument();
    expect(within(trendTable).getByText("资产端-同业存放-活期")).toBeInTheDocument();
    expect(within(trendTable).getByText("资产端-存放同业境内-定期")).toBeInTheDocument();
    expect(within(trendTable).getByText("资产端-存放同业境外-定期")).toBeInTheDocument();
    expect(within(trendTable).queryByText("央行票据")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("地方政府债")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("政策性金融债")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("外国债券")).not.toBeInTheDocument();
    expect(within(trendTable).queryByText("长期股权投资（亿元）")).not.toBeInTheDocument();
    expect(within(trendTable).getByText("FVTPL")).toBeInTheDocument();
    expect(within(trendTable).getByText("AC/OCI/FVTPL 合计")).toBeInTheDocument();
    const basisEmphasisRows = trendTable.querySelectorAll(
      ".balance-movement-report-matrix__row--emphasis",
    );
    expect(basisEmphasisRows.length).toBe(4);
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

  it("surfaces governed result_meta in the first-screen evidence strip", async () => {
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
    expect(evidenceStrip).toHaveTextContent("quality_flag");
    expect(evidenceStrip).toHaveTextContent("ok");
    expect(evidenceStrip).toHaveTextContent("tr_balance_movement_evidence_test");
    expect(evidenceStrip).toHaveTextContent("fact_accounting_asset_movement_monthly");
    expect(evidenceStrip).toHaveTextContent("product_category_pnl_canonical_fact");
    expect(evidenceStrip).toHaveTextContent("192");
    expect(evidenceStrip).toHaveTextContent("rv_balance_movement_evidence_test");
    expect(evidenceStrip).toHaveTextContent("sv_balance_movement_evidence_test");
  });

  it("exports the current evidence view as a local csv without adding an API call", async () => {
    const user = userEvent.setup();
    const createObjectUrl = vi.fn(() => "blob:balance-movement-analysis");
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
      const blob = createObjectUrl.mock.calls[0]?.[0] as Blob;
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

  it("renders diagnostic tags on the analysis dimension cards", async () => {
    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    expect(await screen.findByTestId("balance-movement-analysis-dimension-card-business")).toHaveTextContent(
      "主导变动",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-basis")).toHaveTextContent(
      "主导分桶",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-residual")).toHaveTextContent(
      "口径待补",
    );
    expect(screen.getByTestId("balance-movement-analysis-dimension-card-coverage")).toHaveTextContent(
      "覆盖",
    );
  });

  it("marks low coverage diagnostics with warning and critical tones", async () => {
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
                }
              : envelope.result.zqtz_concentration_analysis,
          },
        };
      },
    };

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: lowCoverageClient,
    });

    const coverageCard = await screen.findByTestId(
      "balance-movement-analysis-dimension-card-coverage",
    );
    expect(within(coverageCard).getByText("期限覆盖")).toHaveClass(
      "balance-movement-dimension-tag--critical",
    );
    expect(within(coverageCard).getByText("集中度覆盖")).toHaveClass(
      "balance-movement-dimension-tag--warn",
    );
  });

  it("opens and closes the residual evidence drawer with diagnostics evidence", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/balance-movement-analysis"], {
      client: createApiClient({ mode: "mock" }),
    });

    await screen.findByTestId("balance-movement-analysis-dimension-card-residual");
    await user.click(screen.getByTestId("balance-movement-analysis-dimension-evidence-residual"));

    const evidenceDialog = await screen.findByRole("complementary", { name: "分析维度证据" });
    expect(evidenceDialog).toHaveTextContent("对账残差");
    expect(evidenceDialog).toHaveTextContent("估值差");
    expect(evidenceDialog).toHaveTextContent("外币折算差");
    expect(evidenceDialog).toHaveTextContent("未支持，不反推");
    expect(evidenceDialog).toHaveTextContent("trace_id");
    expect(evidenceDialog).toHaveTextContent("rule_version");
    expect(evidenceDialog).toHaveTextContent("source_version");

    await user.click(within(evidenceDialog).getByRole("button", { name: "关闭证据" }));

    await waitFor(() => {
      expect(screen.queryByRole("complementary", { name: "分析维度证据" })).not.toBeInTheDocument();
    });
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

    const conclusion = await screen.findByTestId("balance-movement-analysis-conclusion");
    expect(conclusion).toHaveTextContent("ZQTZ 分桶对账需关注");
    const recon = screen.getByTestId("balance-movement-analysis-recon-summary");
    expect(recon).toHaveTextContent("不一致");
    expect(recon.querySelector("a")).toHaveAttribute("href", "#balance-movement-analysis-detail-anchor");
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
  });
});
