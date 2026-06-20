import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TracePanel } from "../features/kpi-performance/components/TracePanel";

describe("TracePanel", () => {
  it("renders fetch and score trace details while preserving the caller class hook", () => {
    render(
      <TracePanel
        className="test-trace-panel"
        fetchTrace={{
          sql_template_id: "tpl_daily_kpi",
          sql_hash: "hash-123",
          params: { owner_id: 1, as_of_date: "2026-06-04" },
          execution_time_ms: 17,
          row_count: 3,
          fetched_at: "2026-06-04T09:00:00Z",
        }}
        scoreTrace={{
          rule_type: "LINEAR_RATIO",
          score_input_field: "completion_ratio",
          inputs: { target: "100", actual: "92" },
          formula: "actual / target * weight",
          intermediate: {},
          final_score: "13.80",
          capped: true,
          rounding: "HALF_UP(2)",
          reason: "cap applied",
          scored_at: "2026-06-04T09:01:00Z",
        }}
      />,
    );

    expect(document.querySelector(".test-trace-panel")).not.toBeNull();
    expect(screen.getAllByText(/tpl_daily_kpi/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("hash-123")).toBeInTheDocument();
    expect(screen.getByText(/owner_id: 1/)).toBeInTheDocument();
    expect(screen.getByText("LINEAR_RATIO")).toBeInTheDocument();
    expect(screen.getByText("actual / target * weight")).toBeInTheDocument();
    expect(screen.getByText("13.80")).toBeInTheDocument();
    expect(screen.getByText("cap applied")).toBeInTheDocument();
  });

  it("renders an empty trace state when no trace payload is available", () => {
    render(<TracePanel className="test-empty-trace-panel" />);

    expect(document.querySelector(".test-empty-trace-panel")).not.toBeNull();
    expect(screen.getByText(/暂无追溯信息/)).toBeInTheDocument();
  });
});
