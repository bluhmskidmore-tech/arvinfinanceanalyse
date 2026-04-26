import { describe, expect, it } from "vitest";

import { buildDashboardTodoTasksFromAlerts } from "../features/workbench/dashboard/dashboardTodoModel";
import type { DashboardAlert } from "../features/workbench/dashboard/DashboardOverviewSections";

describe("buildDashboardTodoTasksFromAlerts", () => {
  it("derives actionable today tasks from high and medium governance alerts", () => {
    const alerts: DashboardAlert[] = [
      {
        id: "low-observe",
        title: "当前无强治理预警",
        detail: "低优先级观察",
        severity: "low",
      },
      {
        id: "medium-partial",
        title: "快照含缺域",
        detail: "部分字段缺失",
        severity: "medium",
      },
      {
        id: "high-mock",
        title: "当前处于模拟模式",
        detail: "演示数据源",
        severity: "high",
      },
    ];

    expect(buildDashboardTodoTasksFromAlerts(alerts)).toEqual([
      {
        id: "todo-high-mock",
        title: "复核：当前处于模拟模式",
        due: "今日复核 · 来源：治理预警",
        priority: "high",
      },
      {
        id: "todo-medium-partial",
        title: "确认：快照含缺域",
        due: "今日确认 · 来源：治理预警",
        priority: "medium",
      },
    ]);
  });

  it("keeps deterministic priority order and caps the dashboard list", () => {
    const alerts: DashboardAlert[] = [
      { id: "medium-1", title: "中优先级一", detail: "", severity: "medium" },
      { id: "high-1", title: "高优先级一", detail: "", severity: "high" },
      { id: "high-2", title: "高优先级二", detail: "", severity: "high" },
      { id: "medium-2", title: "中优先级二", detail: "", severity: "medium" },
    ];

    expect(buildDashboardTodoTasksFromAlerts(alerts, 3).map((task) => task.title)).toEqual([
      "复核：高优先级一",
      "复核：高优先级二",
      "确认：中优先级一",
    ]);
  });
});
