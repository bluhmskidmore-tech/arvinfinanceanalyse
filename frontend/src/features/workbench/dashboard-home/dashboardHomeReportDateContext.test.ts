import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../../../api/contracts";
import { createMockHomeFirstScreenView } from "./dashboardHomeFirstScreenMockView";
import { mapToHomeFirstScreenView } from "./dashboardHomeFirstScreenView";
import {
  hasReportDateDivergence,
  reportDateContextLabel,
  formatShortDate,
} from "./homeReportDateLabel";

function baseMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "trace-1",
    basis: "analytical",
    result_kind: "home_snapshot",
    formal_use_allowed: true,
    source_version: "v1",
    vendor_version: "v1",
    rule_version: "v1",
    cache_version: "v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-30T16:00:00",
    ...overrides,
  };
}

const baseInput = {
  useMockFallback: false,
  verdict: null,
  metrics: [],
  attribution: null,
  bondHeadline: null,
  portfolio: null,
  alertCount: 0,
  snapshotUnavailable: false,
  snapshotStale: false,
  snapshotLoading: false,
  productCategoryHeadline: {
    state: "ready" as const,
    metrics: [
      { id: "annual-pnl", label: "Annual PnL", value: "+1.00", detail: "governed" },
    ],
  },
};

describe("mapToHomeFirstScreenView reportDateContext", () => {
  it("exact: 请求日与实际数据日一致，只显示一个报告日", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      requestedReportDate: "2026-04-30",
      snapshotMeta: baseMeta({
        requested_report_date: "2026-04-30",
        resolved_report_date: "2026-04-30",
      }),
    });
    expect(view.reportDateContext.mode).toBe("exact");
    expect(view.reportDateContext.actualDataDate).toBe("2026-04-30");
    expect(view.reportDateContext.divergenceReason).toBeNull();
    expect(hasReportDateDivergence(view.reportDateContext)).toBe(false);
    expect(reportDateContextLabel(view.reportDateContext)).toBe("报告日 2026-04-30");
  });

  it("fallback: 请求日无数据，回退到最近可用快照，显式标注原因", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      requestedReportDate: "2026-04-18",
      snapshotMeta: baseMeta({
        requested_report_date: "2026-04-18",
        resolved_report_date: "2026-04-30",
        fallback_mode: "latest_snapshot",
      }),
    });
    expect(view.reportDateContext.mode).toBe("fallback");
    expect(view.reportDateContext.requestedDate).toBe("2026-04-18");
    expect(view.reportDateContext.actualDataDate).toBe("2026-04-30");
    expect(view.reportDateContext.divergenceReason).toContain("回退");
    expect(hasReportDateDivergence(view.reportDateContext)).toBe(true);
    const label = reportDateContextLabel(view.reportDateContext);
    expect(label).toContain("请求 04/18");
    expect(label).toContain("实际数据 04/30");
    expect(label).toContain("原因");
  });

  it("stale: 新报告日获取失败，沿用上一版本数据，标注原因", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      requestedReportDate: "2026-04-18",
      snapshotStale: true,
      staleWarning: "新报告日数据获取失败，当前展示上一版本数据",
      snapshotMeta: baseMeta({
        requested_report_date: "2026-04-18",
        resolved_report_date: "2026-04-30",
      }),
    });
    expect(view.reportDateContext.mode).toBe("stale");
    expect(view.reportDateContext.divergenceReason).toContain("上一版本");
    expect(hasReportDateDivergence(view.reportDateContext)).toBe(true);
  });

  it.each(["", "2026-04-30"])(
    "stale: %s 刷新失败只说明沿用上一版本，不制造请求日分歧",
    (requestedReportDate) => {
      const view = mapToHomeFirstScreenView({
        ...baseInput,
        reportDate: "2026-04-30",
        requestedReportDate,
        snapshotStale: true,
        staleWarning: "新报告日数据获取失败，当前展示上一版本数据",
        snapshotMeta: baseMeta({
          requested_report_date: "2026-03-31",
          resolved_report_date: "2026-04-30",
        }),
      });

      expect(view.reportDateContext.mode).toBe("stale");
      expect(view.reportDateContext.requestedDate).toBe(requestedReportDate);
      expect(view.reportDateContext.divergenceReason).toBe(
        "主快照刷新失败，当前展示上一版本数据",
      );
      expect(hasReportDateDivergence(view.reportDateContext)).toBe(false);
      expect(reportDateContextLabel(view.reportDateContext)).toBe(
        "实际数据 04/30 · 原因：主快照刷新失败，当前展示上一版本数据",
      );
    },
  );

  it("loading: 主快照读取中", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "",
      requestedReportDate: "2026-04-30",
      snapshotLoading: true,
      snapshotMeta: null,
    });
    expect(view.reportDateContext.mode).toBe("loading");
    expect(reportDateContextLabel(view.reportDateContext)).toBe("主快照读取中");
  });

  it("error: preserves the permission reason instead of claiming service outage", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "",
      requestedReportDate: "2026-04-30",
      snapshotUnavailable: true,
      snapshotErrorDetail: "User is not allowed to read executive.",
      snapshotMeta: null,
    });
    expect(view.reportDateContext.mode).toBe("error");
    expect(reportDateContextLabel(view.reportDateContext)).toBe(
      "当前账号缺少 executive 读取权限",
    );
  });

  it("mock: 样例数据日语义一致", () => {
    const view = createMockHomeFirstScreenView();
    expect(view.reportDateContext.mode).toBe("mock");
    expect(view.reportDateContext.actualDataDate).toBe("2026-04-30");
    expect(view.reportDateContext.divergenceReason).toBe("样例数据日");
    expect(reportDateContextLabel(view.reportDateContext)).toBe("样例数据日 2026-04-30");
    expect(view.reportDateContext.dataAsOfDate).toBe("2026-04-30");
    expect(view.reportDateContext.generatedAt).toBe("2026-04-30 09:15");
  });

  it("实际数据日只取首页快照 result.report_date，不被 result_meta 覆盖", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      requestedReportDate: "2026-04-30",
      snapshotMeta: baseMeta({
        resolved_report_date: "2026-04-18",
        fallback_date: "2026-04-17",
      }),
    });

    expect(view.reportDateContext.actualDataDate).toBe("2026-04-30");
    expect(view.reportDateContext.mode).toBe("exact");
  });

  it("空快照不使用请求日或 result_meta 日期伪造实际数据日", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "",
      requestedReportDate: "2026-04-18",
      snapshotMeta: baseMeta({
        requested_report_date: "2026-04-18",
        resolved_report_date: "2026-04-30",
        fallback_date: "2026-04-30",
      }),
    });

    expect(view.reportDateContext.actualDataDate).toBe("");
    expect(view.reportDateContext.mode).toBe("empty");
    expect(view.headerStatus.dataStatusKind).not.toBe("ok");
  });

  it("数据有效日取 domains_effective_date，generated_at 仅保留为生成时间", () => {
    const input = {
      ...baseInput,
      reportDate: "2026-04-30",
      domainsEffectiveDate: {
        balance_sheet: "2026-04-30",
        pnl: "2026-04-29",
      },
      snapshotMeta: baseMeta({
        as_of_date: "2026-05-01",
        generated_at: "2026-05-02T09:15:00",
      }),
    };
    const view = mapToHomeFirstScreenView(input);

    expect(view.reportDateContext.dataAsOfDate).toBe(
      "资产负债 2026-04-30 · 损益 2026-04-29",
    );
    expect(view.reportDateContext.generatedAt).toBe("2026-05-02 09:15");
  });

  it.each([
    [
      "fallback 快照",
      { snapshotMeta: baseMeta({ fallback_mode: "latest_snapshot" }) },
      "fallback",
    ],
    [
      "请求日与实际快照日不一致",
      { requestedReportDate: "2026-04-18", snapshotMeta: baseMeta() },
      "fallback",
    ],
    [
      "vendor 降级",
      { snapshotMeta: baseMeta({ vendor_status: "vendor_stale" }) },
      "stale",
    ],
    [
      "同日报告组件不可用",
      {
        snapshotMeta: baseMeta({
          quality_flag: "warning",
          vendor_status: "vendor_unavailable",
        }),
      },
      "partial",
    ],
    [
      "quality 异常",
      { snapshotMeta: baseMeta({ quality_flag: "warning" }) },
      "partial",
    ],
  ] as const)("%s 不得标记为通过", (_label, overrides, expectedKind) => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      ...overrides,
    });

    expect(view.headerStatus.dataStatusKind).toBe(expectedKind);
    expect(view.headerStatus.dataSyncPrefix).toContain("复核");
  });

  it("does not describe same-date component degradation as a previous snapshot", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      snapshotMeta: baseMeta({
        quality_flag: "warning",
        vendor_status: "vendor_unavailable",
      }),
    });

    expect(view.headerStatus.dataStatusKind).toBe("partial");
    expect(view.headerStatus.dataSyncPrefix).toContain("复核");
    expect(view.headerStatus.dataSyncPrefix).not.toContain("上一版本");
  });

  it.each([
    ["empty", "partial", "未下发"],
    ["partial", "partial", "不完整"],
    ["stale", "stale", "偏旧"],
    ["error", "partial", "读取异常"],
  ] as const)("产品分类 %s 会降级全局治理状态", (state, expectedKind, copy) => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      snapshotMeta: baseMeta(),
      productCategoryHeadline: { state, metrics: [] },
    });

    expect(view.headerStatus.dataStatusKind).toBe(expectedKind);
    expect(view.headerStatus.dataSyncPrefix).toContain(copy);
  });

  it("does not treat the allow-partial mode as a missing-domain signal by itself", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      snapshotMode: "partial",
      domainsMissing: [],
      snapshotMeta: baseMeta(),
    });

    expect(view.headerStatus.dataStatusKind).toBe("ok");
    expect(view.headerStatus.dataSyncPrefix).not.toContain("复核");
  });

  it("requires review when the governed snapshot reports missing domains", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      snapshotMode: "partial",
      domainsMissing: ["attribution"],
      snapshotMeta: baseMeta(),
    });

    expect(view.headerStatus.dataStatusKind).toBe("partial");
    expect(view.headerStatus.dataSyncPrefix).toContain("部分数据域缺失");
  });

  it("请求日为空(latest)且后端返回 resolved 时不算分歧", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      requestedReportDate: "",
      snapshotMeta: baseMeta({
        resolved_report_date: "2026-04-30",
      }),
    });
    expect(view.reportDateContext.mode).toBe("exact");
    expect(hasReportDateDivergence(view.reportDateContext)).toBe(false);
  });

  it("formatShortDate 把 ISO 日期格式化为 MM/DD", () => {
    expect(formatShortDate("2026-04-18")).toBe("04/18");
    expect(formatShortDate("")).toBe("—");
    expect(formatShortDate(null)).toBe("—");
  });
});

describe("mapToHomeFirstScreenView mandatory product governance", () => {
  it("treats an omitted mandatory product headline as a global review gap", () => {
    const { productCategoryHeadline: _omitted, ...inputWithoutProduct } = baseInput;
    const view = mapToHomeFirstScreenView({
      ...inputWithoutProduct,
      reportDate: "2026-04-30",
      snapshotMeta: baseMeta(),
    });

    expect(view.headerStatus.dataStatusKind).toBe("partial");
    expect(view.productCategoryHeadline).toEqual({ state: "empty", metrics: [] });
  });

  it("maps a quality-stale snapshot to stale rather than generic partial", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      snapshotMeta: baseMeta({ quality_flag: "stale" }),
    });

    expect(view.headerStatus.dataStatusKind).toBe("stale");
  });

  it("keeps stale governance visible when completeness gaps also exist", () => {
    const view = mapToHomeFirstScreenView({
      ...baseInput,
      reportDate: "2026-04-30",
      domainsMissing: ["attribution"],
      snapshotMeta: baseMeta({ vendor_status: "vendor_stale" }),
      productCategoryHeadline: { state: "empty", metrics: [] },
    });

    expect(view.headerStatus.dataStatusKind).toBe("stale");
    expect(view.missingDomains).toEqual([
      expect.objectContaining({ id: "attribution" }),
    ]);
    expect(view.productCategoryHeadline.state).toBe("empty");
  });
});
