import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ResultMeta } from "../api/contracts";
import MacroObservationDataHealthSection from "../features/macro-observation/sections/MacroObservationDataHealthSection";
import MacroObservationEvidenceSection from "../features/macro-observation/sections/MacroObservationEvidenceSection";
import {
  buildEvidenceMetaView,
  MACRO_OBSERVATION_QUALITY_FLAG_NOTE,
  type MacroObservationDataHealthView,
  type MacroObservationReportBundleView,
} from "../features/macro-observation/model/macroObservationPageModel";
import { EM_DASH } from "../pageModel";

function makeHealthView(
  overrides: Partial<MacroObservationDataHealthView> = {},
): MacroObservationDataHealthView {
  return {
    coverage: [
      { key: "indicator-coverage", label: "指标覆盖", value: "8/10", note: "命中 80%" },
      { key: "source-coverage", label: "来源覆盖", value: "5/6", date: "2026-08-12" },
      {
        key: "capability-results",
        label: "能力结果",
        value: "4/6",
        note: "4 完整 / 1 降级 / 1 不可用",
      },
    ],
    repairItems: [],
    repairMoreNote: null,
    deferredSectionLabels: [],
    warningCount: 0,
    ...overrides,
  };
}

function makeMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "trace-observation-1234567890abcdef",
    basis: "analytical",
    result_kind: "macro_toolkit_analysis",
    formal_use_allowed: false,
    source_version: "sv-1",
    vendor_version: "vv-1",
    rule_version: "rv-1",
    cache_version: "cv-1",
    quality_flag: "warning",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-08-13T10:00:00+08:00",
    ...overrides,
  };
}

const READY_BUNDLE: MacroObservationReportBundleView = {
  status: "ready",
  statusText: "可下载",
  downloadable: true,
  reason: null,
  validationText: "6 通过 / 0 未通过",
  validationFailedCount: 0,
  warningCount: 0,
  artifacts: [
    {
      id: "macro-strategy-report",
      filename: "macro-strategy-2026.pdf",
      label: "策略报告",
      kind: "pdf",
      sizeText: "1.2 MB",
      downloadHref: "/ui/macro/toolkit/report-bundle/macro-strategy-report",
    },
  ],
};

const MISSING_BUNDLE: MacroObservationReportBundleView = {
  status: "missing",
  statusText: "报告资产尚未发布",
  downloadable: false,
  reason: "报告清单缺失，等待发布流程补齐。",
  validationText: EM_DASH,
  validationFailedCount: 0,
  warningCount: 0,
  artifacts: [],
};

function renderEvidenceSection(
  overrides: Partial<Parameters<typeof MacroObservationEvidenceSection>[0]> = {},
) {
  const analysisMeta = makeMeta();
  const strategyMeta = makeMeta({ trace_id: "trace-strategy-0987654321fedcba" });
  return render(
    <MacroObservationEvidenceSection
      metaView={buildEvidenceMetaView(analysisMeta, strategyMeta)}
      analysisMeta={analysisMeta}
      strategyMeta={strategyMeta}
      reportBundle={READY_BUNDLE}
      runtimeSummary="证据已完整读取"
      deferredSectionLabels={[]}
      {...overrides}
    />,
  );
}

describe("MacroObservationDataHealthSection", () => {
  it("renders the three-cell coverage band with percentage note and latest date", () => {
    render(<MacroObservationDataHealthSection health={makeHealthView()} />);

    const coverage = screen.getByTestId("macro-observation-datahealth-coverage");
    const cells = coverage.querySelectorAll(".macro-observation-datahealth__coverage-cell");
    expect(cells).toHaveLength(3);
    expect(within(coverage).getByText("指标覆盖")).toBeInTheDocument();
    expect(within(coverage).getByText("8/10")).toBeInTheDocument();
    expect(within(coverage).getByText("命中 80%")).toBeInTheDocument();
    expect(within(coverage).getByText("2026-08-12")).toBeInTheDocument();
    expect(within(coverage).getByText("4 完整 / 1 降级 / 1 不可用")).toBeInTheDocument();
  });

  it("renders repair rows with priority badges, deferred honesty badge and the more-note", () => {
    render(
      <MacroObservationDataHealthSection
        health={makeHealthView({
          repairItems: [
            {
              key: "repair-0-cn_cpi",
              label: "CPI 同比",
              typeText: "缺失",
              priorityText: "高",
              actionText: "运行宏观来源补数脚本，补齐 CPI 序列后重跑分析。",
              latestDateText: "2026-07-15",
              staleDaysText: "29 天",
            },
            {
              key: "repair-1-strategy_summaries",
              label: "策略证据",
              typeText: "完整分析后确认",
              priorityText: "低",
              actionText: "打开完整分析后确认这部分证据，不把首屏延后加载当作缺失。",
              latestDateText: EM_DASH,
              staleDaysText: EM_DASH,
            },
          ],
          repairMoreNote: "另 3 项",
        })}
      />,
    );

    const highBadge = screen.getByText("高");
    expect(highBadge).toHaveAttribute("data-priority", "high");
    const lowBadge = screen.getByText("低");
    expect(lowBadge).toHaveAttribute("data-priority", "low");

    const deferredRow = screen.getByText("策略证据").closest("tr");
    expect(deferredRow).not.toBeNull();
    expect(deferredRow).toHaveAttribute("data-deferred", "true");
    expect(within(deferredRow as HTMLElement).getByText("延后确认")).toBeInTheDocument();

    const missingRow = screen.getByText("CPI 同比").closest("tr");
    expect(missingRow).not.toHaveAttribute("data-deferred");

    expect(screen.getByTestId("macro-observation-repair-more")).toHaveTextContent("另 3 项");
    expect(screen.getByRole("link", { name: "完整修复清单见宏观工具页" })).toHaveAttribute(
      "href",
      "/macro-toolkit",
    );
  });

  it("omits the more-note when repair items fit within the visible limit", () => {
    render(<MacroObservationDataHealthSection health={makeHealthView()} />);

    expect(screen.queryByTestId("macro-observation-repair-more")).not.toBeInTheDocument();
    expect(screen.getByText("当前没有待处理数据项。")).toBeInTheDocument();
  });

  it("renders a single-line empty state when health evidence is not returned", () => {
    render(<MacroObservationDataHealthSection health={null} />);

    expect(screen.getByTestId("macro-observation-datahealth-empty")).toHaveTextContent(
      "数据健康读数尚未返回；核心分析落地后这里会补上覆盖读数与修复项。",
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("MacroObservationEvidenceSection", () => {
  it("renders the runtime status line with deferred section pills", () => {
    renderEvidenceSection({
      runtimeSummary: "2 项证据延后确认",
      deferredSectionLabels: ["功能结果", "策略证据"],
    });

    const runtime = screen.getByTestId("macro-observation-evidence-runtime");
    expect(runtime).toHaveTextContent("2 项证据延后确认");
    expect(within(runtime).getByText("功能结果")).toBeInTheDocument();
    expect(within(runtime).getByText("策略证据")).toBeInTheDocument();
  });

  it("renders both envelope sections through FormalResultMetaPanel", () => {
    renderEvidenceSection();

    expect(screen.getByTestId("macro-observation-meta-panel-analysis")).toBeInTheDocument();
    expect(screen.getByTestId("macro-observation-meta-panel-strategy")).toBeInTheDocument();
    expect(screen.getByText("宏观分析信封")).toBeInTheDocument();
    expect(screen.getByText("策略摘要信封")).toBeInTheDocument();
  });

  it("renders the quality-flag anti-misread note from the model view", () => {
    renderEvidenceSection();

    expect(screen.getByTestId("macro-observation-evidence-caliber")).toHaveTextContent(
      MACRO_OBSERVATION_QUALITY_FLAG_NOTE,
    );
    // 正式使用说明（仅观察）也在速读补充行内。
    expect(screen.getAllByText("仅观察").length).toBeGreaterThan(0);
  });

  it("renders the downloadable artifact list with the correct download href", () => {
    renderEvidenceSection();

    const bundle = screen.getByTestId("macro-observation-report-bundle");
    expect(bundle).toHaveTextContent("可下载");
    expect(bundle).toHaveTextContent("校验 6 通过 / 0 未通过");
    const link = within(bundle).getByRole("link", { name: "macro-strategy-2026.pdf" });
    expect(link).toHaveAttribute("href", "/ui/macro/toolkit/report-bundle/macro-strategy-report");
    expect(link).toHaveAttribute("download", "macro-strategy-2026.pdf");
    expect(within(bundle).getByText("策略报告 · pdf")).toBeInTheDocument();
    expect(within(bundle).getByText("1.2 MB")).toBeInTheDocument();
  });

  it("renders the missing bundle as a muted reason line without download links", () => {
    renderEvidenceSection({ reportBundle: MISSING_BUNDLE });

    const bundle = screen.getByTestId("macro-observation-report-bundle");
    expect(bundle).toHaveTextContent("报告资产尚未发布");
    expect(bundle).toHaveTextContent("报告清单缺失，等待发布流程补齐。");
    expect(within(bundle).queryByRole("link")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("macro-observation-bundle-validation-warning"),
    ).not.toBeInTheDocument();
  });

  it("renders the amber validation note only when validation failures exist", () => {
    renderEvidenceSection({
      reportBundle: {
        ...READY_BUNDLE,
        validationText: "5 通过 / 2 未通过",
        validationFailedCount: 2,
      },
    });

    expect(screen.getByTestId("macro-observation-bundle-validation-warning")).toHaveTextContent(
      "2 项校验未通过，使用报告前需先复核校验明细。",
    );
  });
});
