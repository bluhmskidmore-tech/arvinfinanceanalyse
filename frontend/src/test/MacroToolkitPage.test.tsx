import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("MacroToolkitPage", () => {
  it("renders from the workbench route", async () => {
    renderWorkbenchApp(["/macro-toolkit"]);

    expect(
      await screen.findByRole("heading", { level: 1, name: "宏观分析结果" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "核心信号" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "指标矩阵" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 2, name: "脚本注册表" }),
    ).toBeInTheDocument();
    expect(await screen.findAllByText("signal_aggregator")).toHaveLength(2);
  });
});
