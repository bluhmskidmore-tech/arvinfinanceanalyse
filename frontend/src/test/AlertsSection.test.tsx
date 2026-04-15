import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import type { AlertsPayload } from "../api/contracts";
import { AlertsSection } from "../features/executive-dashboard/components/AlertsSection";

function alertsFixture(): AlertsPayload {
  return {
    title: "预警",
    items: [
      {
        id: "a1",
        severity: "high",
        title: "限额突破",
        occurred_at: "2026-04-12 09:00",
        detail: "DV01 超阈值。",
      },
      {
        id: "a2",
        severity: "medium",
        title: "集中度提示",
        occurred_at: "2026-04-11 16:30",
        detail: "单一发行人占比偏高。",
      },
      {
        id: "a3",
        severity: "low",
        title: "信息",
        occurred_at: "2026-04-10 10:00",
        detail: "例行复核提醒。",
      },
    ],
  };
}

describe("AlertsSection", () => {
  it("renders severity badges, titles, occurred_at, and detail for high / medium / low", () => {
    const data = alertsFixture();

    render(
      <AlertsSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("预警与事件")).toBeInTheDocument();

    expect(screen.getByText("高")).toBeInTheDocument();
    expect(screen.getByText("限额突破")).toBeInTheDocument();
    expect(screen.getByText("2026-04-12 09:00")).toBeInTheDocument();
    expect(screen.getByText("DV01 超阈值。")).toBeInTheDocument();

    expect(screen.getByText("中")).toBeInTheDocument();
    expect(screen.getByText("集中度提示")).toBeInTheDocument();
    expect(screen.getByText("2026-04-11 16:30")).toBeInTheDocument();
    expect(screen.getByText("单一发行人占比偏高。")).toBeInTheDocument();

    expect(screen.getByText("低")).toBeInTheDocument();
    expect(screen.getByText("信息")).toBeInTheDocument();
    expect(screen.getByText("2026-04-10 10:00")).toBeInTheDocument();
    expect(screen.getByText("例行复核提醒。")).toBeInTheDocument();
  });

  it("renders empty state when items is empty", () => {
    const data: AlertsPayload = { title: "预警", items: [] };

    render(
      <AlertsSection
        data={data}
        isLoading={false}
        isError={false}
        onRetry={() => undefined}
      />,
    );

    expect(screen.getByText("当前暂无可展示内容。")).toBeInTheDocument();
  });
});
