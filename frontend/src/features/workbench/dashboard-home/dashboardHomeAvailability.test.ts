import { describe, expect, it } from "vitest";

import type { HomeGovernanceStatusKind } from "./dashboardHomeFirstScreenTypes";
import {
  buildDashboardHomeAvailability,
  dashboardHomeSnapshotFailureCopy,
} from "./dashboardHomeAvailability";

function buildAvailability(status: HomeGovernanceStatusKind, overrides: {
  snapshotErrorDetail?: string | null;
  requestedDate?: string;
  actualDataDate?: string;
  generatedAt?: string;
  divergenceReason?: string | null;
  snapshotRetryingAfterError?: boolean;
  missingDomainLabels?: readonly string[];
} = {}) {
  return buildDashboardHomeAvailability({
    dataStatusKind: status,
    dataSyncPrefix: "快照状态",
    reportDateContext: {
      requestedDate: overrides.requestedDate ?? "",
      actualDataDate: overrides.actualDataDate ?? "",
      divergenceReason: overrides.divergenceReason ?? null,
      dataAsOfDate: "",
      generatedAt: overrides.generatedAt,
      mode:
        status === "fallback" ||
        status === "stale" ||
        status === "error" ||
        status === "loading"
          ? status
          : "exact",
    },
    snapshotMeta: null,
    snapshotErrorDetail: overrides.snapshotErrorDetail,
    snapshotRetryingAfterError: overrides.snapshotRetryingAfterError,
    missingDomainLabels: overrides.missingDomainLabels,
  });
}

describe("dashboardHomeAvailability", () => {
  it("classifies the governed 403 detail as a permission failure", () => {
    const failure = dashboardHomeSnapshotFailureCopy(
      "User is not allowed to read executive.",
    );

    expect(failure.kind).toBe("permission");
    expect(failure.label).toBe("首页快照权限不足");
    expect(failure.reason).toContain("executive");
  });

  it("describes an unknown request error without claiming an outage", () => {
    const availability = buildAvailability("error", {
      snapshotErrorDetail: "snapshot unavailable",
    });

    expect(availability.failureKind).toBe("requestFailed");
    expect(availability.label).toBe("首页快照读取失败");
    expect(availability.title).not.toContain("服务不可达");
    expect(availability.generatedAt).toBeNull();
    expect(availability.hasResolvedReportDate).toBe(false);
  });

  it.each([
    ["ok", "available"],
    ["partial", "partial"],
    ["fallback", "fallback"],
    ["stale", "stale"],
    ["error", "error"],
  ] as const)("maps %s status to %s availability", (status, expectedKind) => {
    expect(buildAvailability(status).kind).toBe(expectedKind);
  });

  it("keeps requested and actual dates distinct for retained stale data", () => {
    const availability = buildAvailability("stale", {
      requestedDate: "2026-05-31",
      actualDataDate: "2026-04-30",
      divergenceReason: "新报告日数据获取失败，当前展示上一版本数据",
      generatedAt: "2026-04-30T16:00:00Z",
    });

    expect(availability.requestedReportDate).toBe("2026-05-31");
    expect(availability.actualReportDate).toBe("2026-04-30");
    expect(availability.generatedAt).toBe("2026-04-30T16:00:00Z");
    expect(availability.reason).toContain("展示上一版本");
  });

  it.each(["", "2026-04-30"])(
    "describes a %s refresh failure without inventing a new report-date transition",
    (requestedDate) => {
      const availability = buildAvailability("stale", {
        requestedDate,
        actualDataDate: "2026-04-30",
        divergenceReason: "新报告日数据获取失败，当前展示上一版本数据",
      });

      expect(availability.title).toBe("主快照刷新失败，当前展示上一版本");
      expect(availability.reason).toBe("主快照刷新未完成，当前沿用上一版本快照");
      expect(availability.impact).not.toContain("请求日与实际数据日差异");
    },
  );

  it("retains the prior failure while an unresolved snapshot retry is loading", () => {
    const availability = buildAvailability("loading", {
      snapshotErrorDetail: "User is not allowed to read executive.",
      snapshotRetryingAfterError: true,
    });

    expect(availability.kind).toBe("error");
    expect(availability.failureKind).toBe("permission");
    expect(availability.label).toBe("首页快照权限不足");
  });

  it("lists only explicit missing domains for a partial snapshot", () => {
    const availability = buildAvailability("partial", {
      actualDataDate: "2026-04-30",
      missingDomainLabels: ["预警", "贡献"],
    });

    expect(availability.title).toBe("主快照部分可用，缺口模块需复核");
    expect(availability.reason).toBe("缺失数据域：预警、贡献");
  });
});
