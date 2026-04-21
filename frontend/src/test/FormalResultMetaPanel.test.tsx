import { render, screen } from "@testing-library/react";

import { FormalResultMetaPanel } from "../components/page/FormalResultMetaPanel";
import type { ResultMeta } from "../api/contracts";

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
    generated_at: "2026-04-17T02:00:00Z",
    ...overrides,
  };
}

describe("FormalResultMetaPanel", () => {
  it("renders structured provenance fields and optional evidence data", () => {
    render(
      <FormalResultMetaPanel
        testId="formal-meta-panel"
        sections={[
          {
            key: "data",
            title: "正式明细",
            meta: buildMeta({
              tables_used: ["fact_formal_pnl_fi"],
              filters_applied: { report_date: "2025-12-31", basis: "formal" },
              evidence_rows: 42,
              next_drill: ["portfolio", { dimension: "issuer", label: "发行人" }],
            }),
          },
        ]}
      />,
    );

    const panel = screen.getByTestId("formal-meta-panel");
    expect(panel).toHaveTextContent("正式明细");
    expect(panel).toHaveTextContent("tr_formal_meta");
    expect(panel).toHaveTextContent("sv_formal_meta");
    expect(panel).toHaveTextContent("vv_none");
    expect(panel).toHaveTextContent("rv_formal_meta");
    expect(panel).toHaveTextContent("cv_formal_meta");
    expect(panel).toHaveTextContent("vendor_status");
    expect(panel).toHaveTextContent("fallback_mode");
    expect(panel).toHaveTextContent("fact_formal_pnl_fi");
    expect(panel).toHaveTextContent('"report_date":"2025-12-31"');
    expect(panel).toHaveTextContent("42");
    expect(panel).toHaveTextContent("portfolio");
    expect(panel).toHaveTextContent('"dimension":"issuer","label":"发行人"');
  });

  it("renders an empty state when no section has meta", () => {
    render(
      <FormalResultMetaPanel
        testId="formal-meta-empty"
        sections={[{ key: "dates", title: "报告日列表", meta: null }]}
      />,
    );

    expect(screen.getByTestId("formal-meta-empty")).toHaveTextContent(
      "当前还没有可展示的 provenance envelope。",
    );
  });
});
