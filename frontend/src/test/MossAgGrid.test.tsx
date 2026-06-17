import { render, screen } from "@testing-library/react";
import type { AgGridReactProps } from "ag-grid-react";
import { describe, expect, it, vi } from "vitest";

import { MossAgGrid, mossGridDefaultColDef, mossGridLocaleText, mossGridNumericCellClass, numericCol } from "../components/grid";

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: AgGridReactProps) => (
    <div
      data-testid="mock-ag-grid"
      data-theme={String(props.theme)}
      data-loading={String(props.loading)}
      data-row-height={String(props.rowHeight)}
      data-header-height={String(props.headerHeight)}
      data-no-rows={String(props.localeText?.noRowsToShow)}
    />
  ),
}));

describe("MossAgGrid", () => {
  it("exposes shared grid defaults and numeric column helpers", () => {
    expect(mossGridDefaultColDef).toMatchObject({
      sortable: true,
      filter: true,
      resizable: true,
      flex: 1,
      minWidth: 100,
    });
    expect(mossGridLocaleText.noRowsToShow).toBe("暂无数据");
    expect(mossGridLocaleText.loadingOoo).toBe("加载中...");

    const col = numericCol({ field: "amount", headerName: "金额" });
    expect(col.headerClass).toContain("ag-right-aligned-header");
    expect(col.cellClass).toContain(mossGridNumericCellClass);
  });

  it("renders one legacy themed grid shell with unified height and loading defaults", () => {
    render(
      <MossAgGrid
        rowData={[{ id: "A", amount: 1 }]}
        columnDefs={[numericCol({ field: "amount" })]}
        getRowId={(params) => String(params.data.id)}
        loading
        height={240}
        className="sample-grid"
      />,
    );

    const shell = screen.getByTestId("moss-ag-grid");
    expect(shell).toHaveClass("moss-ag-grid");
    expect(shell).toHaveClass("ag-theme-alpine");
    expect(shell).toHaveClass("sample-grid");
    expect(shell).toHaveStyle({ height: "240px" });

    const grid = screen.getByTestId("mock-ag-grid");
    expect(grid).toHaveAttribute("data-theme", "legacy");
    expect(grid).toHaveAttribute("data-loading", "true");
    expect(grid).toHaveAttribute("data-row-height", "36");
    expect(grid).toHaveAttribute("data-header-height", "36");
    expect(grid).toHaveAttribute("data-no-rows", "暂无数据");
  });
});
