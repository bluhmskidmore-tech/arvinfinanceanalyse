import { render, screen } from "@testing-library/react";

import {
  DataQualityPill,
  DataSourceBadge,
  DiagnosticDisclosure,
} from "./StatusPill";
import { mapRawStatusToBusinessStatus } from "./StatusContract";

describe("status contract primitives", () => {
  it("maps raw data quality flags to business-facing labels", () => {
    expect(mapRawStatusToBusinessStatus("ok", "dataQuality")).toMatchObject({
      status: "fresh",
      label: "数据正常",
    });
    expect(mapRawStatusToBusinessStatus("latest_snapshot", "dataQuality")).toMatchObject({
      status: "stale",
      label: "数据延迟",
    });
    expect(mapRawStatusToBusinessStatus("source_pending", "dataQuality")).toMatchObject({
      status: "partial",
      label: "部分缺失",
    });
    expect(mapRawStatusToBusinessStatus("error", "dataQuality")).toMatchObject({
      status: "unavailable",
      label: "不可用",
    });
  });

  it("maps source and access states without exposing raw transport words", () => {
    expect(mapRawStatusToBusinessStatus("analytical", "dataSource")).toMatchObject({
      status: "analysis",
      label: "仅分析使用",
    });
    expect(mapRawStatusToBusinessStatus("proxy_only", "dataSource")).toMatchObject({
      status: "proxy",
      label: "代理数据",
    });
    expect(mapRawStatusToBusinessStatus("mock", "dataSource")).toMatchObject({
      status: "mock",
      label: "演示数据",
    });
    expect(mapRawStatusToBusinessStatus("not read", "systemAccess")).toMatchObject({
      status: "missing",
      label: "未接入",
    });
  });

  it("renders shared status badges and diagnostic disclosure", () => {
    render(
      <>
        <DataQualityPill raw="stale" testId="quality" />
        <DataSourceBadge raw="formal" testId="source" />
        <DiagnosticDisclosure testId="diagnostic">
          <p>trace_id stays in diagnostics</p>
        </DiagnosticDisclosure>
      </>,
    );

    expect(screen.getByTestId("quality")).toHaveTextContent("数据延迟");
    expect(screen.getByTestId("source")).toHaveTextContent("正式可用");
    expect(screen.getByTestId("diagnostic")).toHaveTextContent("查看数据诊断");
    expect(screen.getByTestId("diagnostic")).toHaveTextContent("trace_id stays in diagnostics");
  });
});
