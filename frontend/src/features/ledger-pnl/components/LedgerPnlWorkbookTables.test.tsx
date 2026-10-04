import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QdbGlMonthlyAnalysisSheet } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { LedgerPnlWorkbookTables, type LedgerPnlWorkbookGroup } from "./LedgerPnlWorkbookTables";

function buildSheet(rows: Array<Record<string, unknown>>): QdbGlMonthlyAnalysisSheet {
  return {
    key: "summary_3d",
    title: "3位科目总览",
    columns: ["科目代码", "期末余额"],
    rows,
  };
}

function buildGroups(rows: Array<Record<string, unknown>>): LedgerPnlWorkbookGroup[] {
  return [
    {
      id: "overview",
      label: "总览与预警",
      tables: [
        {
          title: "3位科目总览",
          sheet: buildSheet(rows),
          testId: "summary-3d-table",
        },
      ],
    },
  ];
}

describe("LedgerPnlWorkbookTables", () => {
  it("renders EM_DASH instead of literal NaN/Infinity for non-finite numeric values", () => {
    render(
      <LedgerPnlWorkbookTables
        groups={buildGroups([
          { 科目代码: "101", 期末余额: Number.NaN },
          { 科目代码: "102", 期末余额: Number.POSITIVE_INFINITY },
          { 科目代码: "103", 期末余额: Number.NEGATIVE_INFINITY },
        ])}
      />,
    );

    const table = screen.getByTestId("summary-3d-table");
    const cells = within(table).getAllByRole("cell");
    const balanceCells = cells.filter((cell) =>
      ["101", "102", "103"].every((code) => cell.textContent !== code),
    );

    expect(within(table).queryByText("NaN")).not.toBeInTheDocument();
    expect(within(table).queryByText("Infinity")).not.toBeInTheDocument();
    expect(within(table).queryByText("-Infinity")).not.toBeInTheDocument();
    expect(balanceCells.length).toBeGreaterThan(0);
    balanceCells.forEach((cell) => {
      expect(cell.textContent).toBe(EM_DASH);
    });
  });

  it("still renders a finite formatted number normally", () => {
    render(<LedgerPnlWorkbookTables groups={buildGroups([{ 科目代码: "101", 期末余额: 1234.5 }])} />);

    expect(screen.getByText("1,234.5")).toBeInTheDocument();
  });

  it("keys rows by the stable business dimension column instead of raw row position", () => {
    const { rerender } = render(
      <LedgerPnlWorkbookTables
        groups={buildGroups([
          { 科目代码: "101", 期末余额: 1 },
          { 科目代码: "102", 期末余额: 2 },
        ])}
      />,
    );

    const table = screen.getByTestId("summary-3d-table");
    const rowFor102Before = within(table)
      .getAllByRole("row")
      .find((row) => within(row).queryByText("102"));

    // Prepend a new row: with an index-based key the old second row (102)
    // would be re-keyed as the third row and remounted; with a
    // dimension-based key the "102" row keeps its own <tr> DOM node.
    rerender(
      <LedgerPnlWorkbookTables
        groups={buildGroups([
          { 科目代码: "100", 期末余额: 0 },
          { 科目代码: "101", 期末余额: 1 },
          { 科目代码: "102", 期末余额: 2 },
        ])}
      />,
    );

    const rowFor102After = within(table)
      .getAllByRole("row")
      .find((row) => within(row).queryByText("102"));
    expect(rowFor102After).toBe(rowFor102Before);
  });

  it("falls back to index-suffixed keys without crashing when duplicate dimension values repeat (e.g. multi-alert rows)", () => {
    render(
      <LedgerPnlWorkbookTables
        groups={buildGroups([
          { 科目代码: "101", 期末余额: 10 },
          { 科目代码: "101", 期末余额: 20 },
        ])}
      />,
    );

    const table = screen.getByTestId("summary-3d-table");
    const rows = within(table).getAllByRole("row");
    // header row + 2 data rows, both rendered distinctly despite the duplicate dimension value.
    expect(rows).toHaveLength(3);
  });
});
