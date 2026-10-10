import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FormalResultMetaPanel } from "../components/page/FormalResultMetaPanel";
import type { ResultMeta } from "../api/contracts";
import { buildMockMeta } from "../mocks/mockApiEnvelope";
import { EM_DASH } from "../utils/format";

function buildMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_formal_meta",
    basis: "formal",
    result_kind: "pnl.data",
    formal_use_allowed: true,
    source_version: "sv_formal_meta",
    vendor_version: "vv_none",
    rule_version: "rv_formal_meta",
    cache_version: "cv_formal_meta",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-04-17",
    generated_at: "2026-04-17T02:00:00Z",
    ...overrides,
  };
}

describe("FormalResultMetaPanel", () => {
  it("renders structured provenance fields, as_of_date, and status badges", () => {
    const { container } = render(
      <FormalResultMetaPanel
        testId="formal-meta-panel"
        sections={[
          {
            key: "data",
            title: "Formal detail",
            vendor_status: "vendor_stale",
            fallback_mode: "latest_snapshot",
            meta: buildMeta({
              tables_used: ["fact_formal_pnl_fi"],
              filters_applied: { report_date: "2025-12-31", basis: "formal" },
              requested_report_date: "2026-04-16",
              resolved_report_date: "2026-04-17",
              date_basis: "formal_snapshot",
              fallback_date: "2026-04-15",
              evidence_rows: 42,
              next_drill: ["portfolio", { dimension: "issuer", label: "Issuer" }],
            }),
          },
        ]}
      />,
    );

    const panel = screen.getByTestId("formal-meta-panel");
    expect(panel).toHaveTextContent("Formal detail");
    expect(panel).toHaveTextContent("tr_formal_meta");
    expect(panel).toHaveTextContent("sv_formal_meta");
    expect(panel).toHaveTextContent("vv_none");
    expect(panel).toHaveTextContent("rv_formal_meta");
    expect(panel).toHaveTextContent("cv_formal_meta");
    expect(panel).toHaveTextContent("2026-04-16");
    expect(panel).toHaveTextContent("2026-04-17");
    expect(panel).toHaveTextContent("formal_snapshot");
    expect(panel).toHaveTextContent("2026-04-15");
    expect(panel).toHaveTextContent("fact_formal_pnl_fi");
    expect(panel).toHaveTextContent('"report_date":"2025-12-31"');
    expect(panel).toHaveTextContent("42");
    expect(panel).toHaveTextContent("portfolio");
    expect(panel).toHaveTextContent('"dimension":"issuer","label":"Issuer"');
    expect(container.querySelectorAll("[title]").length).toBeGreaterThan(0);
  });

  it("collapses composite identifiers to a first-segment summary instead of printing the whole hash chain", () => {
    // adb.insights 线上形态：几百个来源版本用 "__" 拼进一个 source_version（2026-09-02 走查 3.8k px 哈希墙）。
    const parts = Array.from({ length: 300 }, (_, index) => `sv_${index.toString(16).padStart(12, "0")}`);
    const compositeSourceVersion = parts.join("__");
    render(
      <FormalResultMetaPanel
        testId="formal-meta-panel"
        sections={[{ key: "adb", title: "ADB 深度分析", meta: buildMeta({ source_version: compositeSourceVersion }) }]}
      />,
    );

    const panel = screen.getByTestId("formal-meta-panel");
    const summary = panel.querySelector(".formal-result-meta-panel__long-value-summary");
    expect(summary).not.toBeNull();
    expect(summary).toHaveTextContent("sv_000000000000 等 300 项");
    // 全文仍在 DOM 里可展开、可复制，只是默认折叠。
    const body = panel.querySelector(".formal-result-meta-panel__long-value-body");
    expect(body).toHaveTextContent(parts[299]!);
    expect(panel.querySelector("details")).not.toHaveAttribute("open");
    // 常规长度的标识不受影响。
    expect(panel).toHaveTextContent("tr_formal_meta");
    expect(panel.querySelectorAll("details")).toHaveLength(2);
  });

  it("renders an empty state when no section has meta", () => {
    render(
      <FormalResultMetaPanel
        testId="formal-meta-empty"
        sections={[{ key: "dates", title: "Dates", meta: null }]}
      />,
    );

    expect(screen.getByTestId("formal-meta-empty")).toHaveTextContent(
      "暂无数据说明，请在数据加载后查看。",
    );
  });
  it("dashes a missing as_of_date and keeps the reason in the cell title", () => {
    const { container } = render(
      <FormalResultMetaPanel
        testId="formal-meta-missing-date"
        sections={[
          {
            key: "data",
            title: "Formal detail",
            meta: buildMeta({ as_of_date: undefined }),
          },
        ]}
      />,
    );

    // 缺值占位统一 EM_DASH（不再用「未提供」第二套缺值词），语义差异收 title。
    const missingCell = container.querySelector('dd[title="尚未提供数据截至日"]');
    expect(missingCell).not.toBeNull();
    expect(missingCell).toHaveTextContent(EM_DASH);
    expect(screen.getByTestId("formal-meta-missing-date")).not.toHaveTextContent("未提供");
  });

  it("separates data materialization time from response assembly time", () => {
    const { container } = render(
      <FormalResultMetaPanel
        testId="formal-meta-built-at"
        sections={[
          {
            key: "data",
            title: "Formal detail",
            meta: buildMeta({
              data_built_at: "2026-04-15T18:30:00Z",
              generated_at: "2026-04-17T02:00:00Z",
            }),
          },
        ]}
      />,
    );

    const builtCell = container.querySelector(
      'dd[title="数据物化完成时刻（治理流 cache_build_run.finished_at）"]',
    );
    expect(builtCell).toHaveTextContent("2026-04-15T18:30:00Z");

    const generatedCell = container.querySelector(
      'dd[title="本次响应的组装时刻，不代表数据新鲜度"]',
    );
    expect(generatedCell).toHaveTextContent("2026-04-17T02:00:00Z");
  });

  it("dashes data_built_at without inventing a time when no build terminal resolved", () => {
    const { container } = render(
      <FormalResultMetaPanel
        testId="formal-meta-no-build"
        sections={[
          {
            key: "data",
            title: "Formal detail",
            meta: buildMeta({ data_built_at: undefined }),
          },
        ]}
      />,
    );

    const missingCell = container.querySelector(
      'dd[title="本结果未解析到已完成的物化构建终态"]',
    );
    expect(missingCell).toHaveTextContent(EM_DASH);
  });

  it("adds a quality badge that follows quality_flag instead of staying green", () => {
    const { container } = render(
      <FormalResultMetaPanel
        testId="formal-meta-quality"
        sections={[
          {
            key: "data",
            title: "Formal detail",
            meta: buildMeta({ quality_flag: "warning" }),
          },
        ]}
      />,
    );

    const badge = container.querySelector('[title="质量标记：预警"]');
    expect(badge).not.toBeNull();
    expect(badge).toHaveTextContent("质量预警");
    // warning 走琥珀 tone 变量出口，不再与卡内质量行矛盾地保持绿徽标。
    expect((badge as HTMLElement).style.background).toContain("--formal-meta-badge-warn-bg");
  });

  it("keeps normal data states in the explanation without repeated badges", () => {
    const { container } = render(
      <FormalResultMetaPanel
        testId="formal-meta-quality-ok"
        sections={[
          {
            key: "data",
            title: "Formal detail",
            meta: buildMeta(),
          },
        ]}
      />,
    );

    const badges = container.querySelectorAll(".formal-result-meta-panel__badge");
    expect(badges).toHaveLength(0);
    expect(screen.getAllByText("正常")).toHaveLength(2);
    expect(screen.getByText("使用所选日期数据")).toBeVisible();
  });

  it("keeps usage restrictions and fallback dates visible while diagnostics require expansion", async () => {
    const user = userEvent.setup();
    render(
      <FormalResultMetaPanel
        sections={[{
          key: "analysis",
          title: "持仓分析",
          meta: buildMeta({
            basis: "analytical",
            formal_use_allowed: false,
            quality_flag: "stale",
            fallback_mode: "latest_snapshot",
            requested_report_date: "2026-04-17",
            resolved_report_date: "2026-04-16",
            fallback_date: "2026-04-16",
          }),
        }]}
      />,
    );
    expect(screen.getByText("仅供分析，尚未获准正式使用")).toBeVisible();
    expect(screen.getByText("已过期")).toBeVisible();
    expect(screen.getAllByText("2026-04-16").every((node) => !node.closest("details"))).toBe(true);
    const trace = screen.getByText("tr_formal_meta");
    expect(trace).not.toBeVisible();
    await user.click(screen.getByText("技术诊断"));
    expect(trace).toBeVisible();
    expect(screen.getByText("仅供分析，尚未获准正式使用")).toBeVisible();
  });

  it("buildMockMeta leaves as_of_date unset unless overridden", () => {
    expect(buildMockMeta("pnl.data").as_of_date).toBeUndefined();
    expect(
      {
        ...buildMockMeta("pnl.data"),
        as_of_date: "2026-04-17",
      }.as_of_date,
    ).toBe("2026-04-17");
  });
});
