import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QdbGlMonthlyAnalysisSheet } from "../api/contracts";
import {
  LedgerPnlWorkbookTables,
  type LedgerPnlWorkbookGroup,
} from "../features/ledger-pnl/components/LedgerPnlWorkbookTables";

function sheet(title: string): QdbGlMonthlyAnalysisSheet {
  return {
    key: title,
    title,
    columns: ["科目", "金额"],
    rows: [{ 科目: "利息收入", 金额: 1234567.8 }],
  };
}

const GROUPS: LedgerPnlWorkbookGroup[] = [
  {
    id: "overview",
    label: "总览与预警",
    tables: [
      {
        title: "财务指标落地状态",
        sheet: undefined,
        testId: "financial-indicator-status",
      },
    ],
  },
  {
    id: "structure",
    label: "资产负债结构",
    tables: [
      {
        title: "资产结构",
        sheet: sheet("资产结构"),
        testId: "asset-structure",
      },
      {
        title: "负债结构",
        sheet: undefined,
        testId: "liability-structure",
      },
    ],
  },
];

describe("LedgerPnlWorkbookTables", () => {
  it("渲染分组标签及有数据表数量", () => {
    render(<LedgerPnlWorkbookTables groups={GROUPS} />);

    expect(screen.getByRole("tablist")).toBeVisible();
    expect(screen.getByRole("tab", { name: "总览与预警 0/1" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "资产负债结构 1/2" })).toBeVisible();
  });

  it("默认选中第一个有数据的分组且只渲染该组表格", () => {
    render(<LedgerPnlWorkbookTables groups={GROUPS} />);

    expect(screen.getByRole("tab", { name: "资产负债结构 1/2" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("asset-structure")).toBeVisible();
    expect(screen.queryByTestId("financial-indicator-status")).not.toBeInTheDocument();
  });

  it("点击标签后替换当前面板内容", () => {
    render(<LedgerPnlWorkbookTables groups={GROUPS} />);

    fireEvent.click(screen.getByRole("tab", { name: "总览与预警 0/1" }));

    expect(screen.getByTestId("financial-indicator-status")).toBeVisible();
    expect(screen.queryByTestId("asset-structure")).not.toBeInTheDocument();
  });

  it("用左右方向键切换标签", () => {
    render(<LedgerPnlWorkbookTables groups={GROUPS} />);

    fireEvent.keyDown(screen.getByRole("tab", { name: "资产负债结构 1/2" }), { key: "ArrowLeft" });

    expect(screen.getByRole("tab", { name: "总览与预警 0/1" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("financial-indicator-status")).toBeVisible();
  });

  it("在无数据表中显示空态文案", () => {
    render(<LedgerPnlWorkbookTables groups={GROUPS} />);

    fireEvent.click(screen.getByRole("tab", { name: "总览与预警 0/1" }));

    expect(screen.getByTestId("financial-indicator-status")).toHaveTextContent("暂无可展示数据");
  });

  it("全部分组无数据时仍选中第一个分组", () => {
    const emptyGroups: LedgerPnlWorkbookGroup[] = GROUPS.map((group) => ({
      ...group,
      tables: group.tables.map((table) => ({ ...table, sheet: undefined })),
    }));

    render(<LedgerPnlWorkbookTables groups={emptyGroups} />);

    expect(screen.getByRole("tab", { name: "总览与预警 0/1" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("financial-indicator-status")).toHaveTextContent("暂无可展示数据");
  });
});
