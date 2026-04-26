import { describe, expect, it } from "vitest";

import {
  BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT,
  buildBalanceStageRealDataModel,
  distributionChartBarWidthPercent,
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
  formatBalanceGridThousandsValue,
  formatBalanceOverviewNumber,
  formatBalanceScopeTotalAmountToYi,
  formatBalanceWorkbookCellDisplay,
  formatBalanceWorkbookWanAmountDisplay,
  formatBalanceWorkbookWanTextDisplay,
  gapChartBarWidthPercent,
  maxAbsFiniteChartScale,
  maxFiniteChartScale,
  parseBalanceChartMagnitude,
  summarizeBalanceAmountsByPositionScope,
} from "./balanceAnalysisPageModel";

describe("balanceAnalysisPageModel", () => {
  describe("display formatters", () => {
    it("shows em dash for null, undefined, and empty string", () => {
      expect(formatBalanceOverviewNumber(null)).toBe("—");
      expect(formatBalanceOverviewNumber(undefined)).toBe("—");
      expect(formatBalanceOverviewNumber("")).toBe("—");
      expect(formatBalanceAmountToYiFromYuan(null)).toBe("—");
      expect(formatBalanceAmountToYiFromYuan(undefined)).toBe("—");
      expect(formatBalanceAmountToYiFromYuan("")).toBe("—");
      expect(formatBalanceAmountToYiFromWan(null)).toBe("—");
      expect(formatBalanceWorkbookCellDisplay(null)).toBe("—");
      expect(formatBalanceWorkbookCellDisplay(undefined)).toBe("—");
      expect(formatBalanceWorkbookCellDisplay("")).toBe("—");
      expect(formatBalanceGridThousandsValue(null)).toBe("—");
      expect(formatBalanceGridThousandsValue(undefined)).toBe("—");
      expect(formatBalanceGridThousandsValue("")).toBe("—");
    });

    it("treats string zero as a legitimate numeric zero, not missing", () => {
      expect(formatBalanceOverviewNumber("0")).toBe("0");
      expect(parseBalanceChartMagnitude("0")).toEqual({ kind: "finite", value: 0 });
      expect(formatBalanceWorkbookCellDisplay("0")).toBe("0");
      expect(formatBalanceGridThousandsValue("0")).toBe("0");
    });

    it("keeps invalid strings visible as the original input for overview and yi formatters", () => {
      expect(formatBalanceOverviewNumber("not-a-number")).toBe("not-a-number");
      expect(formatBalanceAmountToYiFromYuan("12abc")).toBe("12abc");
      expect(formatBalanceAmountToYiFromWan("n/a")).toBe("n/a");
    });

    it("formats comma-containing numeric strings like the page helpers", () => {
      expect(formatBalanceOverviewNumber("1,234.5")).toBe("1,234.5");
      expect(formatBalanceGridThousandsValue("1,234")).toBe("1,234");
      expect(formatBalanceAmountToYiFromYuan("100,000,000")).toBe("1.00");
      expect(formatBalanceAmountToYiFromYuan("0E-8")).toBe("0.00");
    });

    it("matches yuan-to-yi and wan-to-yi locale precision (zh-CN, 2 decimals)", () => {
      expect(formatBalanceAmountToYiFromYuan(100_000_000)).toBe("1.00");
      expect(formatBalanceAmountToYiFromYuan("123456789")).toBe(
        (123_456_789 / 100_000_000).toLocaleString("zh-CN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }),
      );
      expect(formatBalanceAmountToYiFromWan(10_000)).toBe("1.00");
      expect(formatBalanceAmountToYiFromWan("25000.25")).toBe(
        (25_000.25 / 10_000).toLocaleString("zh-CN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }),
      );
    });

    it("adds yi unit labels for workbook wan-yuan amount cells", () => {
      expect(formatBalanceWorkbookWanAmountDisplay("4290357.07")).toBe("429.04 亿元");
      expect(formatBalanceWorkbookWanAmountDisplay("-128000.00")).toBe("-12.80 亿元");
      expect(formatBalanceWorkbookWanAmountDisplay("n/a")).toBe("n/a");
    });

    it("rewrites governed workbook reason text from wan yuan to yi yuan", () => {
      expect(formatBalanceWorkbookWanTextDisplay("Bucket gap is 4290357.07 wan yuan.")).toBe(
        "Bucket gap is 429.04 亿元.",
      );
      expect(formatBalanceWorkbookWanTextDisplay("Gap dropped to -128000.00 wan yuan.")).toBe(
        "Gap dropped to -12.80 亿元.",
      );
      expect(formatBalanceWorkbookWanTextDisplay("No numeric amount here.")).toBe("No numeric amount here.");
    });

    it("rewrites 万元 (Chinese) amounts in workbook notes the same as wan yuan", () => {
      expect(formatBalanceWorkbookWanTextDisplay("观测峰值 99.00 万元。")).toBe("观测峰值 0.01 亿元。");
    });
  });

  describe("chart magnitude and widths", () => {
    it("does not treat invalid magnitudes as legitimate zero-width bars (null, not min bar)", () => {
      const invalid = parseBalanceChartMagnitude("oops");
      expect(invalid.kind).toBe("invalid");
      expect(distributionChartBarWidthPercent(invalid, 100)).toBeNull();
      expect(gapChartBarWidthPercent(invalid, 100)).toBeNull();
    });

    it("treats finite zero as a real zero magnitude with the minimum bar width", () => {
      const zero = parseBalanceChartMagnitude("0");
      expect(zero).toEqual({ kind: "finite", value: 0 });
      expect(distributionChartBarWidthPercent(zero, 100)).toBe(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT);
      expect(gapChartBarWidthPercent(zero, 100)).toBe(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT);
    });

    it("uses absolute magnitude for gap bar width while preserving negative sign in workbook display", () => {
      const neg = parseBalanceChartMagnitude("-40");
      expect(neg).toEqual({ kind: "finite", value: -40 });
      expect(formatBalanceWorkbookCellDisplay(-40)).toBe("-40");
      expect(formatBalanceWorkbookCellDisplay("-40")).toBe("-40");
      expect(maxAbsFiniteChartScale(["-40", "10"])).toBe(40);
      expect(gapChartBarWidthPercent(neg, 40)).toBe(
        Math.max(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT, (40 / 40) * 100),
      );
    });

    it("ignores invalid cells when computing max scale so bars are not pinned to a fake zero denominator", () => {
      expect(maxFiniteChartScale(["bad", 50, 30])).toBe(50);
      expect(maxAbsFiniteChartScale(["bad", "-30", 10])).toBe(30);
    });
  });

  describe("position-scope amount summaries", () => {
    it("separates asset and liability totals instead of combining them", () => {
      const totals = summarizeBalanceAmountsByPositionScope([
        {
          position_scope: "asset",
          row_count: 174,
          market_value_amount: "24145782559.52",
          amortized_cost_amount: "24145782559.52",
          accrued_interest_amount: "186447192.86",
        },
        {
          position_scope: "liability",
          row_count: 2125,
          market_value_amount: "64768888887.83",
          amortized_cost_amount: "64768888887.83",
          accrued_interest_amount: "13996586.21",
        },
        {
          position_scope: "asset",
          row_count: 1711,
          market_value_amount: "333925726735.544",
          amortized_cost_amount: "327352769214.272",
          accrued_interest_amount: "25793215.37",
        },
        {
          position_scope: "liability",
          row_count: 129,
          market_value_amount: "119804097177.69",
          amortized_cost_amount: "120453500738.43",
          accrued_interest_amount: "0E-8",
        },
      ]);

      expect(totals.asset.rowCount).toBe(1885);
      expect(formatBalanceScopeTotalAmountToYi(totals.asset, "marketValueAmount")).toBe("3,580.72");
      expect(formatBalanceScopeTotalAmountToYi(totals.asset, "amortizedCostAmount")).toBe("3,514.99");
      expect(formatBalanceScopeTotalAmountToYi(totals.asset, "accruedInterestAmount")).toBe("2.12");
      expect(totals.liability.rowCount).toBe(2254);
      expect(formatBalanceScopeTotalAmountToYi(totals.liability, "marketValueAmount")).toBe("1,845.73");
      expect(formatBalanceScopeTotalAmountToYi(totals.liability, "amortizedCostAmount")).toBe("1,852.22");
      expect(formatBalanceScopeTotalAmountToYi(totals.liability, "accruedInterestAmount")).toBe("0.14");
    });
  });

  describe("stage real-data model", () => {
    it("derives staged summary, contribution, risk, and calendar panels from workbook payloads", () => {
      const model = buildBalanceStageRealDataModel({
        overview: {
          report_date: "2025-12-31",
          position_scope: "all",
          currency_basis: "CNY",
          detail_row_count: 3,
          summary_row_count: 2,
          total_market_value_amount: "0",
          total_amortized_cost_amount: "0",
          total_accrued_interest_amount: "0",
        },
        workbook: {
          report_date: "2025-12-31",
          position_scope: "all",
          currency_basis: "CNY",
          cards: [
            { key: "bond_assets_excluding_issue", label: "债券资产", value: "2000000" },
            { key: "interbank_assets", label: "同业资产", value: "1000000" },
            { key: "issuance_liabilities", label: "发行类负债", value: "500000" },
            { key: "interbank_liabilities", label: "同业负债", value: "250000" },
          ],
          tables: [
            {
              key: "bond_business_types",
              title: "债券业务种类",
              section_kind: "table",
              columns: [],
              rows: [{ bond_type: "政策性金融债", balance_amount: "2000000", share: "1" }],
            },
            {
              key: "issuance_business_types",
              title: "发行类分析",
              section_kind: "table",
              columns: [],
              rows: [{ bond_type: "同业存单", balance_amount: "500000", share: "1" }],
            },
            {
              key: "maturity_gap",
              title: "期限缺口分析",
              section_kind: "table",
              columns: [],
              rows: [
                {
                  bucket: "已到期/逾期",
                  asset_total_amount: "0",
                  full_scope_liability_amount: "10000",
                  full_scope_gap_amount: "-10000",
                },
                {
                  bucket: "3-6个月",
                  asset_total_amount: "5000",
                  full_scope_liability_amount: "30000",
                  full_scope_gap_amount: "-25000",
                },
                {
                  bucket: "1-2年",
                  asset_total_amount: "60000",
                  full_scope_liability_amount: "10000",
                  full_scope_gap_amount: "50000",
                },
              ],
            },
          ],
          operational_sections: [],
        },
        decisionRows: [
          {
            decision_key: "decision-1",
            title: "Review 3-6 month gap",
            action_label: "Review gap",
            severity: "high",
            reason: "Bucket gap is -25000 wan yuan.",
            source_section: "maturity_gap",
            rule_id: "rule-gap",
            rule_version: "v1",
            latest_status: {
              decision_key: "decision-1",
              status: "pending",
              updated_at: null,
              updated_by: null,
              comment: null,
            },
          },
        ],
        riskAlertRows: [
          {
            title: "Negative gap in 3-6 months",
            severity: "high",
            reason: "Gap dropped to -25000 wan yuan.",
            source_section: "maturity_gap",
            rule_id: "risk-gap",
            rule_version: "v1",
          },
        ],
        eventCalendarRows: [
          {
            event_date: "2026-03-05",
            event_type: "funding_rollover",
            title: "repo-1 maturity",
            source: "internal_governed_schedule",
            impact_hint: "liability book / repo",
            source_section: "maturity_gap",
          },
        ],
      });

      expect(model.hasRealData).toBe(true);
      expect(model.summary.content).toContain("资产端合计 300.00 亿元");
      expect(model.summary.content).toContain("发行类首位为 同业存单");
      expect(model.summary.allocationNetValue).toBe("225.00");
      expect(model.contribution.rows).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            item: "债券资产",
            assetBal: "200.00",
            assetPct: "66.7%",
            netGap: "+200.00",
          }),
          expect.objectContaining({
            item: "发行类负债",
            liabBal: "50.00",
            liabPct: "66.7%",
            netGap: "-50.00",
          }),
          expect.objectContaining({
            item: "3-6个月全口径缺口",
            netGap: "-2.50",
            rowKind: "gap",
          }),
        ]),
      );
      expect(model.contribution.watchItems[0]).toMatchObject({
        level: "danger",
        title: "Review 3-6 month gap",
      });
      expect(model.contribution.watchItems[0].detail).toContain("-2.50 亿元");
      expect(model.bottom.maturityCategories).toEqual(["已到期/逾期", "3-6个月", "1-2年"]);
      expect(model.bottom.gapSeries).toEqual([-1, -2.5, 5]);
      expect(model.bottom.riskMetrics).toEqual(
        expect.arrayContaining([
          { label: "资产/全口径负债比", value: "4.00x" },
          { label: "1年内全口径缺口", value: "-3.50 亿" },
        ]),
      );
      expect(model.bottom.calendarItems[0]).toMatchObject({
        date: "2026-03-05",
        event: "repo-1 maturity",
        amount: "maturity_gap",
        level: "high",
      });
    });

    it("uses explicit no-data rows instead of static demonstration numbers", () => {
      const model = buildBalanceStageRealDataModel({});

      expect(model.hasRealData).toBe(false);
      expect(model.summary.content).toContain("未返回可用于 stage 的真实 workbook 切片");
      expect(model.contribution.rows).toEqual([
        {
          item: "暂无真实数据",
          assetBal: "—",
          assetPct: "—",
          liabBal: "—",
          liabPct: "—",
          netGap: "—",
          rowKind: "empty",
        },
      ]);
      expect(model.contribution.watchItems[0].title).toBe("当前报告日未返回治理事项");
      expect(model.bottom.calendarItems[0].event).toBe("当前报告日未返回事件日历");
    });
    it("uses detail summary fallback in stage summary copy when workbook is unavailable", () => {
      const model = buildBalanceStageRealDataModel({
        overview: {
          report_date: "2026-03-31",
          position_scope: "all",
          currency_basis: "CNY",
          detail_row_count: 2,
          summary_row_count: 2,
          total_market_value_amount: "14000000000",
          total_amortized_cost_amount: "14000000000",
          total_accrued_interest_amount: "0",
        },
        summaryRows: [
          {
            source_family: "combined",
            position_scope: "asset",
            currency_basis: "CNY",
            row_count: 1,
            market_value_amount: "10000000000",
            amortized_cost_amount: "10000000000",
            accrued_interest_amount: "0",
          },
          {
            source_family: "combined",
            position_scope: "liability",
            currency_basis: "CNY",
            row_count: 1,
            market_value_amount: "4000000000",
            amortized_cost_amount: "4000000000",
            accrued_interest_amount: "0",
          },
        ],
      });

      expect(model.hasRealData).toBe(true);
      expect(model.summary.allocationItems.map((item) => item.value)).toEqual([100, -40]);
      expect(model.summary.allocationNetValue).toBe("60.00");
      expect(model.summary.content).toContain("100.00");
      expect(model.summary.content).toContain("40.00");
      expect(model.summary.content).not.toContain("workbook");
    });
  });
});
