import { describe, expect, it } from "vitest";

import { isEvidenceBookRowPending } from "../features/macro-toolkit/lib/macroToolkitCommitteeEvidence";

describe("isEvidenceBookRowPending", () => {
  it("does not treat healthy data-health copy as pending", () => {
    expect(isEvidenceBookRowPending("100% 覆盖 · 7/9 源命中", "无待处理项")).toBe(false);
  });

  it("does not treat healthy strategy-supply copy as pending", () => {
    expect(isEvidenceBookRowPending("完整链路 2/2", "无供数降级")).toBe(false);
  });

  it("flags real repair backlog", () => {
    expect(isEvidenceBookRowPending("100% 覆盖 · 7/9 源命中", "3 项待处理")).toBe(true);
  });

  it("flags missing primary signal", () => {
    expect(isEvidenceBookRowPending("主信号待返回", "6/6 指标命中")).toBe(true);
  });

  it("flags capability confirmation gap", () => {
    expect(isEvidenceBookRowPending("脚本 5/5 · 只读观察", "能力闭环待确认")).toBe(true);
  });
});
