import { render, screen } from "@testing-library/react";

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

  it("renders an empty state when no section has meta", () => {
    render(
      <FormalResultMetaPanel
        testId="formal-meta-empty"
        sections={[{ key: "dates", title: "Dates", meta: null }]}
      />,
    );

    expect(screen.getByTestId("formal-meta-empty")).toHaveTextContent(
      "当前还没有可展示的溯源信封。",
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
    const missingCell = container.querySelector('dd[title="后端未提供数据截至日"]');
    expect(missingCell).not.toBeNull();
    expect(missingCell).toHaveTextContent(EM_DASH);
    expect(screen.getByTestId("formal-meta-missing-date")).not.toHaveTextContent("未提供");
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

  it("keeps the ok quality badge green alongside vendor/fallback badges", () => {
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
    expect(badges).toHaveLength(3);
    const quality = container.querySelector('[title="质量标记：正常"]');
    expect(quality).not.toBeNull();
    expect(quality).toHaveTextContent("质量正常");
    expect((quality as HTMLElement).style.background).toContain("--formal-meta-badge-ok-bg");
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
