import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  LedgerPnlDataTable,
  type LedgerPnlDataTableColumn,
} from "../features/ledger-pnl/components/LedgerPnlDataTable";
import { EM_DASH } from "../utils/format";

type Row = {
  id: string;
  name: string;
  category: string;
  amount: number | null;
};

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function buildRows(count: number): Row[] {
  return Array.from({ length: count }, (_, index) => {
    const n = index + 1;
    return {
      id: `row-${n}`,
      name: `科目${pad(n)}`,
      category: n <= 7 ? "含税" : "免税",
      amount: n * 100,
    };
  });
}

function buildColumns(): LedgerPnlDataTableColumn<Row>[] {
  return [
    {
      key: "name",
      header: "科目名称",
      searchValue: (row) => row.name,
      render: (row) => row.name,
    },
    {
      key: "category",
      header: "类别",
      searchValue: (row) => row.category,
      render: (row) => row.category,
    },
    {
      key: "amount",
      header: "金额",
      numeric: true,
      sortValue: (row) => row.amount,
      render: (row) => (row.amount === null ? EM_DASH : row.amount.toFixed(2)),
    },
  ];
}

function bodyRowsOf(container: HTMLElement): HTMLElement[] {
  return within(container).getAllByRole("row").slice(1);
}

function firstCellTextsOf(container: HTMLElement): (string | null)[] {
  return bodyRowsOf(container).map((row) => within(row).getAllByRole("cell")[0].textContent);
}

const BASE_PROPS = {
  testId: "ledger-pnl-data-table-test",
  title: "测试表格",
  loadingMessage: "加载中",
  errorMessage: "加载失败",
  emptyMessage: "暂无数据",
};

describe("LedgerPnlDataTable", () => {
  it("renders title, column headers, and only first-page rows", () => {
    render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={buildRows(12)}
        rowKey={(row) => row.id}
        pageSize={5}
      />,
    );

    const table = screen.getByTestId(BASE_PROPS.testId);
    expect(table).toHaveTextContent("测试表格");
    expect(screen.getByRole("columnheader", { name: "科目名称" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "类别" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "金额" })).toBeVisible();

    expect(screen.getByText("科目01")).toBeVisible();
    expect(screen.getByText("科目05")).toBeVisible();
    expect(screen.queryByText("科目06")).not.toBeInTheDocument();
  });

  it("filters rows by search and keeps pagination summary/page count correct", async () => {
    const user = userEvent.setup();
    render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={buildRows(12)}
        rowKey={(row) => row.id}
        pageSize={5}
        searchPlaceholder="搜索科目"
      />,
    );

    const search = screen.getByTestId(`${BASE_PROPS.testId}-search`);
    await user.type(search, "含税");

    expect(screen.getByTestId(`${BASE_PROPS.testId}-range`)).toHaveTextContent("第 1-5 条 / 共 7 条");
    expect(screen.getByText("科目01")).toBeVisible();
    expect(screen.queryByText("科目08")).not.toBeInTheDocument();

    await user.click(screen.getByTestId(`${BASE_PROPS.testId}-next`));

    expect(screen.getByTestId(`${BASE_PROPS.testId}-range`)).toHaveTextContent("第 6-7 条 / 共 7 条");
    expect(screen.getByText("科目06")).toBeVisible();
    expect(screen.getByText("科目07")).toBeVisible();
    expect(screen.queryByText("科目01")).not.toBeInTheDocument();
    expect(screen.getByTestId(`${BASE_PROPS.testId}-next`)).toBeDisabled();
  });

  it("shows a no-match message with a clear-search action when search yields nothing", async () => {
    const user = userEvent.setup();
    render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={buildRows(12)}
        rowKey={(row) => row.id}
        searchPlaceholder="搜索科目"
      />,
    );

    const search = screen.getByTestId(`${BASE_PROPS.testId}-search`);
    await user.type(search, "不存在的科目xyz");

    expect(screen.getByText(/没有匹配/)).toBeVisible();
    expect(screen.getByText(/不存在的科目xyz/)).toBeVisible();
    const clearButton = screen.getByRole("button", { name: "清除搜索" });
    await user.click(clearButton);

    expect(search).toHaveValue("");
    expect(screen.getByText("科目01")).toBeVisible();
  });

  it("sorts asc/desc/original with correct aria-sort and null values sorted last", async () => {
    const user = userEvent.setup();
    const rows: Row[] = [
      { id: "a", name: "科目A", category: "含税", amount: 300 },
      { id: "b", name: "科目B", category: "含税", amount: 100 },
      { id: "c", name: "科目C", category: "含税", amount: null },
      { id: "d", name: "科目D", category: "含税", amount: 200 },
    ];

    render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={rows}
        rowKey={(row) => row.id}
      />,
    );

    const table = screen.getByTestId(BASE_PROPS.testId);
    const amountHeader = screen.getByRole("columnheader", { name: "金额" });
    expect(amountHeader).toHaveAttribute("aria-sort", "none");

    await user.click(within(amountHeader).getByRole("button", { name: "金额" }));
    expect(amountHeader).toHaveAttribute("aria-sort", "ascending");
    expect(firstCellTextsOf(table)).toEqual(["科目B", "科目D", "科目A", "科目C"]);

    await user.click(within(amountHeader).getByRole("button", { name: "金额" }));
    expect(amountHeader).toHaveAttribute("aria-sort", "descending");
    expect(firstCellTextsOf(table)).toEqual(["科目A", "科目D", "科目B", "科目C"]);

    await user.click(within(amountHeader).getByRole("button", { name: "金额" }));
    expect(amountHeader).toHaveAttribute("aria-sort", "none");
    expect(firstCellTextsOf(table)).toEqual(["科目A", "科目B", "科目C", "科目D"]);
  });

  it("paginates: next reveals the second page, and prev is disabled on the first page", async () => {
    const user = userEvent.setup();
    render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={buildRows(12)}
        rowKey={(row) => row.id}
        pageSize={5}
      />,
    );

    expect(screen.getByTestId(`${BASE_PROPS.testId}-prev`)).toBeDisabled();

    await user.click(screen.getByTestId(`${BASE_PROPS.testId}-next`));

    expect(screen.getByText("科目06")).toBeVisible();
    expect(screen.queryByText("科目01")).not.toBeInTheDocument();
    expect(screen.getByTestId(`${BASE_PROPS.testId}-prev`)).not.toBeDisabled();
    expect(screen.getByTestId(`${BASE_PROPS.testId}-range`)).toHaveTextContent("第 6-10 条 / 共 12 条");
  });

  it("renders all rows with no pagination bar when pageSize is 0", () => {
    render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={buildRows(30)}
        rowKey={(row) => row.id}
        pageSize={0}
      />,
    );

    expect(screen.getByText("科目01")).toBeVisible();
    expect(screen.getByText("科目30")).toBeVisible();
    expect(screen.queryByTestId(`${BASE_PROPS.testId}-prev`)).not.toBeInTheDocument();
    expect(screen.queryByTestId(`${BASE_PROPS.testId}-next`)).not.toBeInTheDocument();
    expect(screen.queryByTestId(`${BASE_PROPS.testId}-range`)).not.toBeInTheDocument();
  });

  it("renders loading, error, and empty states with distinct copy", () => {
    const { rerender } = render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={[]}
        rowKey={(row) => row.id}
        isLoading
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("加载中");

    rerender(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={[]}
        rowKey={(row) => row.id}
        isError
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("加载失败");

    rerender(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={[]}
        rowKey={(row) => row.id}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("暂无数据");
  });

  it("clamps back to page 1 when the rows prop shrinks below the current page", async () => {
    // 页面场景：用户翻到第 3 页后，从贡献者卡片触发「定位」，rows 骤减到 1 行。
    // currentPage 必须是渲染期派生钳制，被定位的行必须立即可见。
    const user = userEvent.setup();
    const { rerender } = render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={buildRows(60)}
        rowKey={(row) => row.id}
        pageSize={5}
      />,
    );

    await user.click(screen.getByTestId(`${BASE_PROPS.testId}-next`));
    await user.click(screen.getByTestId(`${BASE_PROPS.testId}-next`));
    expect(screen.getByTestId(`${BASE_PROPS.testId}-range`)).toHaveTextContent(
      "第 11-15 条 / 共 60 条",
    );

    rerender(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={buildRows(60).slice(41, 42)}
        rowKey={(row) => row.id}
        pageSize={5}
      />,
    );

    expect(screen.getByText("科目42")).toBeVisible();
    expect(
      screen.queryByTestId(`${BASE_PROPS.testId}-range`),
    ).not.toBeInTheDocument();
  });

  it("invokes onRowClick on click and on Enter keydown", async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    const rows = buildRows(3);

    render(
      <LedgerPnlDataTable
        {...BASE_PROPS}
        columns={buildColumns()}
        rows={rows}
        rowKey={(row) => row.id}
        onRowClick={onRowClick}
      />,
    );

    const firstRowCell = screen.getByText("科目01");
    const firstRow = firstRowCell.closest("tr");
    if (!firstRow) throw new Error("Expected a table row");
    await user.click(firstRow);
    expect(onRowClick).toHaveBeenCalledWith(rows[0]);

    const secondRowCell = screen.getByText("科目02");
    const secondRow = secondRowCell.closest("tr");
    if (!secondRow) throw new Error("Expected a table row");
    (secondRow as HTMLElement).focus();
    await user.keyboard("{Enter}");
    expect(onRowClick).toHaveBeenCalledWith(rows[1]);
  });
});
