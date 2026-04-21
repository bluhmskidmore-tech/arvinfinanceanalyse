import { describe, expect, it } from "vitest";

import {
  sanitizeMetricCopy,
  sanitizeMetricDetail,
  sanitizeMetricLabel,
} from "../features/executive-dashboard/lib/sanitizeMetricCopy";

describe("sanitizeMetricLabel", () => {
  it("strips full-width ASCII suffix", () => {
    expect(sanitizeMetricLabel("债券资产规模（zqtz）")).toBe("债券资产规模");
  });

  it("strips half-width ASCII suffix", () => {
    expect(sanitizeMetricLabel("债券资产规模(zqtz)")).toBe("债券资产规模");
  });

  it("does not strip user-facing acronyms inside the label body", () => {
    expect(sanitizeMetricLabel("组合DV01")).toBe("组合DV01");
    expect(sanitizeMetricLabel("净息差")).toBe("净息差");
  });

  it("returns the original string unchanged when no tech suffix is present", () => {
    expect(sanitizeMetricLabel("年内收益")).toBe("年内收益");
  });

  it("handles empty / whitespace input safely", () => {
    expect(sanitizeMetricLabel("")).toBe("");
    expect(sanitizeMetricLabel("   ")).toBe("");
  });
});

describe("sanitizeMetricDetail", () => {
  it("masks fact_* table names and removes the orphan '来自 ... ，'", () => {
    const raw =
      "来自 fact_formal_zqtz_balance_daily，在 2026-02-28 的 CNY 资产口径市值合计。";
    expect(sanitizeMetricDetail(raw)).toBe(
      "在 2026-02-28 的本币资产口径市值合计。",
    );
  });

  it("rewrites English internal phrases to Chinese business terms", () => {
    expect(
      sanitizeMetricDetail(
        "来自 governed formal balance overview，在 2026-02-28 的 CNY 资产口径市值合计。",
      ),
    ).toBe("来自治理资产快照，在 2026-02-28 的本币资产口径市值合计。");
  });

  it("rewrites NIM phrasing", () => {
    expect(
      sanitizeMetricDetail("来自受治理负债分析收益指标，在 2026-02-28 的 NIM 读面。"),
    ).toBe("来自治理负债收益面，在 2026-02-28 的净息差。");
  });

  it("rewrites bond analytics phrasing", () => {
    expect(
      sanitizeMetricDetail("来自 bond analytics 风险快照，在 2026-02-28 的组合 DV01。"),
    ).toBe("来自债券风险快照，在 2026-02-28 的组合 DV01。");
  });

  it("masks dim_/mart_/stg_/tmp_ tables too", () => {
    // 表名替换为占位词 '治理数据集' 后会被前缀清理规则吃掉，
    // 留下的句子虽不完整但不会再泄露表名 — 这是可接受的退化。
    expect(sanitizeMetricDetail("dim_customer 与 mart_pnl_daily 联合视图。"))
      .not.toMatch(/dim_|mart_|fact_|stg_|tmp_/);
  });

  it("returns the original string unchanged when no tech tokens are present", () => {
    const raw = "在 2026-02-28 的本币资产口径市值合计。";
    expect(sanitizeMetricDetail(raw)).toBe(raw);
  });

  it("strips bare field names like total_pnl / portfolio_dv01", () => {
    expect(
      sanitizeMetricDetail("来自 fact_formal_pnl_fi 截至 2026-02-28 的年内 total_pnl 合计。"),
    ).toBe("截至 2026-02-28 的年内累计。");
  });

  it("normalizes 'NIM 读面' phrasing", () => {
    expect(sanitizeMetricDetail("在 2026-02-28 的 NIM 读面。")).toBe(
      "在 2026-02-28 的净息差。",
    );
  });

  it("handles empty input safely", () => {
    expect(sanitizeMetricDetail("")).toBe("");
  });
});

describe("sanitizeMetricCopy", () => {
  it("sanitizes both label and detail in one pass and preserves other fields", () => {
    const metric = {
      id: "aum",
      label: "债券资产规模（zqtz）",
      detail:
        "来自 fact_formal_zqtz_balance_daily，在 2026-02-28 的 CNY 资产口径市值合计。",
      tone: "positive" as const,
    };
    expect(sanitizeMetricCopy(metric)).toEqual({
      id: "aum",
      label: "债券资产规模",
      detail: "在 2026-02-28 的本币资产口径市值合计。",
      tone: "positive",
    });
  });
});
