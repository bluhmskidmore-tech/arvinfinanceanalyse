import { describe, expect, it } from "vitest";

import type { CrossAssetStatusFlag } from "./crossAssetDriversPageModel";
import { buildStatusStripFlags } from "./crossAssetStatusStrip";

function flag(overrides: Partial<CrossAssetStatusFlag> & { id: string }): CrossAssetStatusFlag {
  return {
    label: overrides.id,
    tone: "warning",
    detail: "测试明细",
    ...overrides,
  };
}

describe("crossAssetStatusStrip", () => {
  it("tone 归一：danger→error，warning/caution→warn，normal→ok", () => {
    const flags = buildStatusStripFlags([
      flag({ id: "access-denied", tone: "danger" }),
      flag({ id: "analytical-only", tone: "warning" }),
      flag({ id: "fallback", tone: "caution" }),
      flag({ id: "other-normal", tone: "normal" }),
    ]);
    expect(flags.map((item) => item.tone)).toEqual(["error", "warn", "warn", "ok"]);
  });

  it("id 特判：stale→stale，dual-source→info", () => {
    const flags = buildStatusStripFlags([
      flag({ id: "stale", tone: "warning", label: "可能陈旧" }),
      flag({ id: "dual-source", tone: "normal", label: "双源就绪" }),
    ]);
    expect(flags).toEqual([
      { tone: "stale", label: "可能陈旧", title: "测试明细" },
      { tone: "info", label: "双源就绪", title: "测试明细" },
    ]);
  });

  it("label 取自 CrossAssetStatusFlag.label，detail 收进 title（token 不占正文）", () => {
    const flags = buildStatusStripFlags([flag({ id: "no-data", tone: "danger", label: "暂无数据" })]);
    expect(flags).toEqual([{ tone: "error", label: "暂无数据", title: "测试明细" }]);
  });

  it("detail 与 label 相同或为空时不产生 title", () => {
    const flags = buildStatusStripFlags([
      flag({ id: "no-data", tone: "danger", label: "暂无数据", detail: "暂无数据" }),
    ]);
    expect(flags).toEqual([{ tone: "error", label: "暂无数据", title: undefined }]);
  });

  it("空态：undefined / null / 空数组 → []", () => {
    expect(buildStatusStripFlags(undefined)).toEqual([]);
    expect(buildStatusStripFlags(null)).toEqual([]);
    expect(buildStatusStripFlags([])).toEqual([]);
  });

  it("过滤空 label 并按 tone|label 去重", () => {
    const flags = buildStatusStripFlags([
      flag({ id: "analytical-only", tone: "warning", label: "仅分析口径" }),
      flag({ id: "linkage-quality-warning", tone: "warning", label: "仅分析口径" }),
      flag({ id: "blank", tone: "warning", label: "   " }),
    ]);
    expect(flags).toEqual([{ tone: "warn", label: "仅分析口径", title: "测试明细" }]);
  });
});
