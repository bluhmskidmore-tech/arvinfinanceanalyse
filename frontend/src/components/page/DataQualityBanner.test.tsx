import { render, screen } from "@testing-library/react";
import type { ResultMeta } from "../../api/contracts";
import { DataQualityBanner } from "./DataQualityBanner";

const baseMeta: ResultMeta = {
  trace_id: "test",
  basis: "formal",
  result_kind: "test",
  formal_use_allowed: true,
  source_version: "sv_test",
  vendor_version: "vv_none",
  rule_version: "rv_test",
  cache_version: "cv_test",
  quality_flag: "ok",
  vendor_status: "ok",
  fallback_mode: "none",
  scenario_flag: false,
  generated_at: "2026-05-05T00:00:00Z",
};

describe("DataQualityBanner", () => {
  it("renders nothing when quality is ok and no warnings", () => {
    const { container } = render(<DataQualityBanner resultMeta={baseMeta} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders partial banner for warning quality_flag", () => {
    render(<DataQualityBanner resultMeta={{ ...baseMeta, quality_flag: "warning" }} />);
    expect(screen.getByRole("alert")).toHaveClass("data-quality-banner--partial");
    expect(screen.getByText("部分数据使用回退值")).toBeInTheDocument();
  });

  it("renders degraded banner for error quality_flag", () => {
    render(<DataQualityBanner resultMeta={{ ...baseMeta, quality_flag: "error" }} />);
    expect(screen.getByRole("alert")).toHaveClass("data-quality-banner--degraded");
  });

  it("renders degraded banner for stale quality_flag", () => {
    render(<DataQualityBanner resultMeta={{ ...baseMeta, quality_flag: "stale" }} />);
    expect(screen.getByRole("alert")).toHaveClass("data-quality-banner--degraded");
  });

  it("shows partial when degradedReasons provided", () => {
    render(
      <DataQualityBanner resultMeta={baseMeta} degradedReasons={["应计利息使用回退值"]} />,
    );
    expect(screen.getByRole("alert")).toHaveClass("data-quality-banner--partial");
    expect(screen.getByText("应计利息使用回退值")).toBeInTheDocument();
  });

  it("shows partial when warnings provided", () => {
    render(
      <DataQualityBanner resultMeta={baseMeta} warnings={["missing_curve:treasury_current"]} />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("renders null resultMeta with degradedReasons", () => {
    render(<DataQualityBanner resultMeta={null} degradedReasons={["数据准备中"]} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("数据准备中")).toBeInTheDocument();
  });
});
