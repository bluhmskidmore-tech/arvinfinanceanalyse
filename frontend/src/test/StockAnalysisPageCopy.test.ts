import { describe, expect, it } from "vitest";

import {
  buildStockAnalysisRailReviewState,
  buildStockRailActionLabel,
  buildThemeBreakoutBlockerCopy,
  compactStockText,
  filterChipClass,
  formatGeneratedAtLabel,
  iconTone,
  kpiToneToDelta,
  riskExitBlockedDetail,
  riskExitBlockedSummary,
  riskStatusLabel,
  statusIconClass,
  tonePillClass,
  toneTextClass,
  localizeStockErrorMessage,
  rawStockErrorMessage,
  stockPageErrorMessage,
  stockStatusLabel,
  stockStrategyPanelErrorMessage,
  stockSupplyBasisLabel,
  stockSupplyFallbackLabel,
  stockSupplyQualityLabel,
  stockSupplyVendorLabel,
} from "../features/stock-analysis/lib/stockAnalysisPageCopy";

describe("stockAnalysisPageCopy", () => {
  it("localizes page-level stock service errors before exposing them", () => {
    expect(stockPageErrorMessage(new Error("strategy unavailable"))).toBe("策略服务暂不可用，请稍后重试。");
    expect(localizeStockErrorMessage("Failed because source_table livermore_signal is missing")).toBe(
      "请求失败：必需数据源缺失，稍后复核供数状态。",
    );
    expect(localizeStockErrorMessage("Request failed for /ui/market-data/livermore")).toBe(
      "供数暂不可用，请稍后复核。",
    );
    expect(localizeStockErrorMessage("Permission not allowed")).toBe("数据权限待确认，请联系管理员。");
  });

  it("keeps panel error summaries and raw diagnostics on separate paths", () => {
    const error = new Error("Failed to fetch because source_table market_priority is missing.");

    expect(stockStrategyPanelErrorMessage(error)).toContain("必需数据源缺失");
    expect(rawStockErrorMessage(error)).toBe("Failed to fetch because source_table market_priority is missing.");
  });

  it("maps backend status and supply flags into business labels", () => {
    expect(stockStatusLabel("pass")).toBe("通过");
    expect(stockStatusLabel("stale")).toBe("已陈旧");
    expect(stockStatusLabel("unknown_vendor_code")).toBe("状态待确认");

    expect(stockSupplyQualityLabel("warning")).toBe("需复核");
    expect(stockSupplyQualityLabel("vendor_pending")).toBe("质量待确认");
    expect(stockSupplyVendorLabel("degraded")).toBe("降级");
    expect(stockSupplyVendorLabel("vendor_unavailable")).toBe("异常");
    expect(stockSupplyVendorLabel("vendor_stale")).toBe("陈旧");
    expect(stockSupplyVendorLabel("vendor_pending")).toBe("供数待确认");
    expect(stockSupplyFallbackLabel("none")).toBe("无回退");
    expect(stockSupplyFallbackLabel("latest_snapshot")).toBe("回退快照");
    expect(stockSupplyFallbackLabel("unknown")).toBe("回退待确认");
    expect(stockSupplyBasisLabel("analytical")).toBe("分析口径");
    expect(stockSupplyBasisLabel("formal")).toBe("正式口径");
    expect(stockSupplyBasisLabel("vendor_pending")).toBe("口径待确认");
  });

  it("builds compact decision-rail action labels without leaking long fallback copy", () => {
    expect(compactStockText("  A   long   fallback label  ", 10)).toBe("A long fa…");
    expect(
      buildStockRailActionLabel(
        {
          stockName: "Alpha",
          distanceToBreakoutPct: "+0.46%",
        },
        "ignored",
      ),
    ).toBe("首位 Alpha · +0.46%");
    expect(buildStockRailActionLabel(null, "多因子观察池等待复核")).toBe("多因子池");
    expect(buildStockRailActionLabel(null, "候选复核等待确认")).toBe("候选复核");
    expect(buildStockRailActionLabel(null, "风险观察等待确认")).toBe("风险复核");
    expect(buildStockRailActionLabel(null, "超长回退行动说明需要裁剪并继续复核")).toBe("超长回退行动说明需要裁剪并…");
  });

  it("builds rail review state from review queue and risk rows", () => {
    expect(
      buildStockAnalysisRailReviewState({
        reviewQueue: [
          {
            stockName: "Alpha",
            distanceToBreakoutPct: "+0.46%",
          },
        ],
        riskRows: [{ status: "triggered" }, { status: "watch" }, { status: "watch" }],
        nextReviewAction: "ignored",
      }),
    ).toEqual({
      riskTriggeredCount: 1,
      riskWatchCount: 2,
      railRiskTone: "negative",
      railNextActionFullLabel: "Alpha \u00b7 \u8ddd\u89c2\u5bdf +0.46%",
      railNextActionLabel: "\u9996\u4f4d Alpha \u00b7 +0.46%",
    });

    expect(
      buildStockAnalysisRailReviewState({
        reviewQueue: [],
        riskRows: [{ status: "watch" }],
        nextReviewAction: "\u98ce\u9669\u89c2\u5bdf\u7b49\u5f85\u786e\u8ba4",
      }),
    ).toMatchObject({
      riskTriggeredCount: 0,
      riskWatchCount: 1,
      railRiskTone: "warning",
      railNextActionFullLabel: "\u98ce\u9669\u89c2\u5bdf\u7b49\u5f85\u786e\u8ba4",
      railNextActionLabel: "\u98ce\u9669\u590d\u6838",
    });

    expect(
      buildStockAnalysisRailReviewState({
        reviewQueue: [],
        riskRows: [],
        nextReviewAction: null,
      }),
    ).toMatchObject({
      railRiskTone: "positive",
      railNextActionFullLabel: "\u7b49\u5f85\u590d\u6838\u961f\u5217",
      railNextActionLabel: "\u7b49\u5f85\u590d\u6838",
    });
  });

  it("builds compact theme breakout blocker copy from unsupported output reasons", () => {
    expect(
      buildThemeBreakoutBlockerCopy({
        key: "theme_breakout",
        reason: "Theme breakout execution is paused because market gate is OVERHEAT.",
      }),
    ).toEqual({
      text: "\u5e02\u573a\u8fc7\u70ed\u95e8\u63a7\u4e0b\u6682\u505c\u9898\u6750\u89c2\u5bdf\uff1b\u5386\u53f2\u56de\u653e\u663e\u793a\u8be5\u6876\u62d6\u7d2f\u3002",
      label: "\u95e8\u63a7\u6682\u505c",
    });

    expect(buildThemeBreakoutBlockerCopy(null)).toEqual({ text: null, label: null });
    expect(
      buildThemeBreakoutBlockerCopy({
        key: "theme_breakout",
        reason: "\u9898\u6750\u8f93\u5165\u672a\u843d\u5730\u6216\u95e8\u63a7\u672a\u5f00\u653e\uff0c\u6682\u4e0d\u51fa\u6267\u884c\u7ed3\u8bba\u3002",
      }),
    ).toMatchObject({ label: "\u95e8\u63a7\u6682\u505c" });
  });

  it("formats generated timestamps and maps display tones into stable utility classes", () => {
    expect(formatGeneratedAtLabel(null)).toBe("");
    expect(formatGeneratedAtLabel("2026-04-29T15:06:00+08:00")).toBe("04-29 15:06");
    expect(formatGeneratedAtLabel("source_table_pending_generated_at")).toBe("source_tabl…");

    expect(iconTone("positive")).toBe("positive");
    expect(iconTone("negative")).toBe("negative");
    expect(iconTone("warning")).toBe("warning");
    expect(iconTone("vendor_pending")).toBe("neutral");
    expect(kpiToneToDelta("positive")).toBe("up");
    expect(kpiToneToDelta("negative")).toBe("down");
    expect(kpiToneToDelta("warning")).toBe("flat");

    expect(filterChipClass(true)).toContain("border-primary-500");
    expect(filterChipClass(false)).toContain("hover:bg-neutral-100");
    expect(statusIconClass("warning")).toContain("text-warning-700");
    expect(toneTextClass("negative")).toBe("text-danger-600");
    expect(tonePillClass("positive")).toContain("bg-success-50");
    expect(tonePillClass("unknown")).toContain("text-neutral-600");
  });

  it("localizes risk-exit rail status and blocker reasons without leaking technical source codes", () => {
    expect(riskStatusLabel("triggered")).toBe("触发复核");
    expect(riskStatusLabel("watch")).toBe("观察中");

    expect(riskExitBlockedSummary("")).toBe("供数状态待确认");
    expect(riskExitBlockedSummary("livermore_position_snapshot has no ACTIVE A-share rows.")).toBe(
      "持仓快照缺失",
    );
    expect(riskExitBlockedDetail("livermore_position_snapshot has no ACTIVE A-share rows.", "risk_exit")).toBe(
      "持仓快照缺失，暂无可执行风险退出样本。",
    );
    expect(riskExitBlockedSummary("sourceTableRiskExitSignal")).toBe("风险退出待确认");
    expect(riskExitBlockedDetail("sourceTableRiskExitSignal", "risk_exit")).toBe("风险退出待确认");
    expect(riskExitBlockedSummary("等待最新风险退出供数完成后再复核")).toBe("等待最新风险退出供数完成后再复核");
  });
});
