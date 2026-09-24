import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MacroToolkitReportBundle } from "../api/macroToolkitClient";
import { MacroToolkitReportBundlePanel } from "../features/macro-toolkit/panels/MacroToolkitReportBundlePanel";

const READY_BUNDLE: MacroToolkitReportBundle = {
  status: "ready",
  reason: null,
  schema_version: "macro-report-bundle-v1",
  bundle_id: "china-macro-rates-2026-07-20",
  title: "2026 中国宏观与利率策略",
  basis: "analytical",
  as_of_date: "2026-07-20",
  curve_date: "2026-07-17",
  account_report_date: "2026-06-30",
  observation_only: true,
  formal_use_allowed: false,
  validation: {
    passed: 93,
    failed: 0,
    scope: "交付物一致性校验，不构成外部市场真值复核",
  },
  warnings: ["研究材料，只读观察，不构成正式指标、限额依据或交易信号。"],
  artifacts: [
    {
      id: "full-report",
      filename: "report.pdf",
      label: "完整报告",
      kind: "report",
      media_type: "application/pdf",
      size_bytes: 3_182_018,
      sha256: "a".repeat(64),
    },
    {
      id: "one-page-preview",
      filename: "onepager.png",
      label: "一页摘要预览",
      kind: "preview",
      media_type: "image/png",
      size_bytes: 261_287,
      sha256: "b".repeat(64),
    },
  ],
};

describe("MacroToolkitReportBundlePanel", () => {
  it("surfaces dates, validation scope, and allowlisted download links", () => {
    render(<MacroToolkitReportBundlePanel bundle={READY_BUNDLE} />);

    const panel = screen.getByLabelText("宏观策略报告资产");
    expect(panel).toHaveTextContent("2026 中国宏观与利率策略");
    expect(panel).toHaveTextContent("研究级只读");
    expect(panel).toHaveTextContent("非正式口径");
    expect(panel).toHaveTextContent("材料日2026-07-20");
    expect(panel).toHaveTextContent("曲线日2026-07-17");
    expect(panel).toHaveTextContent("账户日2026-06-30");
    expect(panel).toHaveTextContent("93/93");
    expect(panel).toHaveTextContent("不构成外部市场真值复核");
    expect(within(panel).getByRole("link", { name: /下载完整报告/ })).toHaveAttribute(
      "href",
      "/ui/macro/toolkit/report-bundle/full-report",
    );
    expect(within(panel).getByRole("link", { name: /下载一页摘要预览/ })).toHaveAttribute(
      "href",
      "/ui/macro/toolkit/report-bundle/one-page-preview",
    );
  });

  it.each([
    ["missing", "报告资产尚未发布"],
    ["invalid", "资产校验失败，下载已关闭"],
  ] as const)("fails closed for %s bundles", (status, message) => {
    render(
      <MacroToolkitReportBundlePanel
        bundle={{
          status,
          reason: status === "missing" ? "manifest_missing" : "artifact_hash_mismatch",
          basis: "analytical",
          observation_only: true,
          formal_use_allowed: false,
          artifacts: [],
          warnings: [message],
        }}
      />,
    );

    const panel = screen.getByLabelText("宏观策略报告资产");
    expect(panel).toHaveTextContent(message);
    expect(within(panel).queryByRole("link")).not.toBeInTheDocument();
  });
});
