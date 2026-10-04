import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Numeric } from "../../api/contracts";
import { EM_DASH } from "../../pageModel";
import { TONE_DH_CSS_VAR } from "../../utils/tone";
import { DataTable, type DataTableColumn } from "./DataTable";

const cssPath = resolve(process.cwd(), "src/components/layout/DataTable.module.css");
const tsxPath = resolve(process.cwd(), "src/components/layout/DataTable.tsx");
const cssText = readFileSync(cssPath, "utf8");
const tsxText = readFileSync(tsxPath, "utf8");
const cssWithoutComments = cssText.replace(/\/\*[\s\S]*?\*\//g, "");

function escapeForRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * 取一条 CSS 规则的声明块。`grouped` 允许目标选择器只是选择器列表中的一项
 * （如 `.cell[data-align="numeric"], .footCell[data-align="numeric"]`）。
 */
function ruleBody(selector: string, options?: { grouped?: boolean }): string {
  const tail = options?.grouped ? "[^{}]*" : "\\s*";
  const pattern = new RegExp(`${escapeForRegExp(selector)}${tail}\\{([^}]*)\\}`);
  const match = cssWithoutComments.match(pattern);
  expect(match, `CSS rule for "${selector}" not found`).not.toBeNull();
  return match?.[1] ?? "";
}

function pxValue(body: string, property: string): number {
  const match = body.match(new RegExp(`${escapeForRegExp(property)}\\s*:\\s*(\\d+(?:\\.\\d+)?)px`));
  expect(match, `"${property}" not declared in px`).not.toBeNull();
  return Number(match?.[1]);
}

type IndustryRow = {
  industry_name: string;
  total_market_value: Numeric;
  bond_count: number;
  percentage: Numeric | null;
};

function numeric(raw: number | null, display: string): Numeric {
  return { raw, unit: "yuan", display, precision: 2, sign_aware: true };
}

const BASIC_COLUMNS: DataTableColumn<IndustryRow>[] = [
  { key: "industry_name", title: "行业" },
  { key: "total_market_value", title: "金额", unit: "亿", align: "numeric" },
  { key: "bond_count", title: "只数", align: "numeric" },
  { key: "percentage", title: "占比", unit: "%", align: "numeric", note: "Top10 内占比" },
];

function industryRow(name: string, count: number): IndustryRow {
  return {
    industry_name: name,
    total_market_value: numeric(1_200_000_000, "+1,200,000,000.00"),
    bond_count: count,
    percentage: null,
  };
}

const THREE_ROWS: IndustryRow[] = [industryRow("城投", 12), industryRow("银行", 8), industryRow("能源", 3)];

describe("DataTable 密度纪律（样式契约）", () => {
  it("keeps the primitive free of !important, bare hex, and --ib-* variables", () => {
    // 注释里会引用这些禁令名字，所以只对去注释后的声明正文断言。
    expect(cssWithoutComments).not.toMatch(/!important/);
    expect(cssWithoutComments).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(cssWithoutComments).not.toMatch(/--ib-/);
    expect(cssWithoutComments).not.toMatch(/\brgba?\(/);
  });

  it("locks the header at 12px/500, the body at 12px, and a hairline bottom border", () => {
    const head = ruleBody(".headCell");
    expect(head).toContain("font-size: var(--moss-table-font-size, 12px);");
    expect(head).toContain("font-weight: var(--moss-table-header-weight, 500);");
    expect(head).toContain("border-bottom: 1px solid var(--moss-table-border, var(--dh-api-line-soft));");

    const cell = ruleBody(".cell");
    expect(cell).toContain("font-size: var(--moss-table-font-size, 12px);");
    expect(cell).toContain("font-weight: var(--moss-table-cell-weight, 400);");
    expect(cell).toContain("height: var(--moss-table-row-h, 32px);");
    expect(ruleBody('.root[data-density="compact"] .cell')).toContain("height: var(--moss-table-row-h-compact, 28px);");
    expect(cell).toContain("border-bottom: 1px solid var(--moss-table-border, var(--dh-api-line-soft));");
  });

  it("expresses depth with panel layers and hairlines instead of shadows", () => {
    expect(cssWithoutComments).not.toMatch(/box-shadow/);
    expect(cssWithoutComments).toContain("var(--dh-api-panel-2)");
  });

  it("right-aligns numeric columns with the tabular number stack", () => {
    const numericCell = ruleBody('.cell[data-align="numeric"]', { grouped: true });
    expect(numericCell).toContain("text-align: right;");
    expect(numericCell).toContain("font-family: var(--moss-font-tabular);");
    expect(numericCell).toContain("font-variant-numeric: tabular-nums;");
    expect(ruleBody('.headCell[data-align="numeric"]')).toContain("text-align: right;");
  });

  it("keeps every radius on the Nocturne token except the Shape Lock 2px skeleton bar", () => {
    const radii = [...cssWithoutComments.matchAll(/border-radius\s*:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(radii.length).toBeGreaterThan(0);
    for (const radius of radii) {
      expect(["var(--dh-api-radius)", "2px"]).toContain(radius);
    }
  });

  it("collapses the empty surface to a self-sized message box with no hard height cap", () => {
    const surface = ruleBody(".surface");
    expect(pxValue(surface, "min-height")).toBeLessThanOrEqual(120);
    // 不许加 max-height：封顶会让长错误文案溢出边框（centered flex 会上下双向溢出）。
    expect(surface).not.toContain("max-height");
    expect(surface).toContain("justify-content: center;");
  });

  it("gives the loading skeleton a backdrop and a near-real min-height", () => {
    const skeleton = ruleBody(".skeleton");
    expect(skeleton).toContain("background: var(--dh-api-panel-2);");
    expect(skeleton).toContain("border: 1px solid var(--dh-api-line-soft);");
    expect(pxValue(skeleton, "min-height")).toBeGreaterThanOrEqual(100);
  });

  it("scrolls wide tables inside the container instead of bursting the page grid", () => {
    expect(ruleBody(".scroll")).toContain("overflow-x: auto;");
    const root = ruleBody(".root");
    expect(root).toContain("min-width: 0;");
    expect(root).toContain("max-width: 100%;");
    expect(ruleBody(".table")).toContain("min-width: max-content;");
  });

  it("mirrors TONE_DH_CSS_VAR value for value so the two never drift", () => {
    for (const [tone, cssVariable] of Object.entries(TONE_DH_CSS_VAR)) {
      expect(ruleBody(`.statusRow[data-tone="${tone}"]`)).toContain(`color: ${cssVariable};`);
    }
  });

  it("imports nothing from antd and declares no inline style props", () => {
    expect(tsxText).not.toMatch(/from\s+["']antd/);
    expect(tsxText).not.toMatch(/style\s*=/);
  });
});

describe("DataTable envelope 未到达 vs 真实空 payload", () => {
  it("keeps the skeleton height while the envelope has not arrived", () => {
    render(<DataTable<IndustryRow> rows={undefined} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);

    expect(screen.getByTestId("t")).toHaveAttribute("data-view", "skeleton");
    expect(screen.getByTestId("t-skeleton")).toBeInTheDocument();
    expect(screen.queryByText("暂无数据")).not.toBeInTheDocument();
  });

  it("collapses to the empty message for a truly empty payload", () => {
    render(<DataTable<IndustryRow> rows={[]} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);

    expect(screen.getByTestId("t")).toHaveAttribute("data-view", "empty");
    expect(screen.getByTestId("t-empty")).toHaveTextContent("暂无数据");
    expect(screen.queryByTestId("t-skeleton")).not.toBeInTheDocument();
  });

  it("treats a missing envelope like an empty payload under the collapse policy", () => {
    render(
      <DataTable<IndustryRow>
        rows={undefined}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        emptyPolicy="collapse"
        emptyMessage="本期没有行业敞口"
        testId="t"
      />,
    );

    expect(screen.getByTestId("t")).toHaveAttribute("data-view", "empty");
    expect(screen.getByTestId("t-empty")).toHaveTextContent("本期没有行业敞口");
    expect(screen.queryByTestId("t-skeleton")).not.toBeInTheDocument();
  });
});

describe("DataTable 表格语义与列契约", () => {
  it("renders a semantic table with scoped column headers", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        ariaLabel="行业分布"
        testId="t"
      />,
    );

    const table = screen.getByRole("table", { name: "行业分布" });
    expect(table.querySelector("thead")).not.toBeNull();
    expect(table.querySelector("tbody")).not.toBeNull();
    for (const header of screen.getAllByRole("columnheader")) {
      expect(header).toHaveAttribute("scope", "col");
    }
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("marks numeric columns on both the header and the body cells", () => {
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);

    const headers = screen.getAllByRole("columnheader");
    expect(headers[0]).toHaveAttribute("data-align", "text");
    expect(headers[1]).toHaveAttribute("data-align", "numeric");

    const firstBodyRow = screen.getAllByRole("row")[1];
    const cells = within(firstBodyRow).getAllByRole("cell");
    expect(cells[0]).toHaveAttribute("data-align", "text");
    expect(cells[1]).toHaveAttribute("data-align", "numeric");
    expect(cells[2]).toHaveAttribute("data-align", "numeric");
  });

  it("renders the column unit as a header suffix", () => {
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);

    expect(screen.getAllByRole("columnheader")[1]).toHaveTextContent("金额(亿)");
    expect(screen.getAllByRole("columnheader")[3]).toHaveTextContent("占比(%)");
  });

  it("applies column width through colgroup rather than an inline style", () => {
    const { container } = render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={[{ key: "industry_name", title: "行业", width: 180 }]}
        testId="t"
      />,
    );

    const col = container.querySelector("col");
    expect(col).toHaveAttribute("width", "180");
    expect(container.querySelector("[style]")).toBeNull();
  });
});

describe("DataTable 缺值与治理 Numeric", () => {
  type MixedRow = {
    id: string;
    governed: Numeric;
    missingGoverned: Numeric;
    blank: string;
    absent: number | null;
    opaque: { nested: number };
  };

  const mixedColumns: DataTableColumn<MixedRow>[] = [
    { key: "governed", title: "治理值", align: "numeric" },
    { key: "missingGoverned", title: "缺失治理值", align: "numeric" },
    { key: "blank", title: "空串" },
    { key: "absent", title: "空值" },
    { key: "opaque", title: "未知对象" },
  ];

  const mixedRow: MixedRow = {
    id: "r1",
    governed: numeric(1_200_000_000, "+1,200,000,000.00"),
    // 后端可以给 raw=null 却带非空 display；null 语义以 raw 为准。
    missingGoverned: { raw: null, unit: "pct", display: "0.00%", precision: 2, sign_aware: true },
    blank: "   ",
    absent: null,
    opaque: { nested: 1 },
  };

  it("renders a governed Numeric through its backend display string", () => {
    render(<DataTable<MixedRow> rows={[mixedRow]} rowKey="id" columns={mixedColumns} testId="t" />);

    const cells = within(screen.getAllByRole("row")[1]).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("+1,200,000,000.00");
  });

  it("renders every missing shape as the canonical em dash and never [object Object]", () => {
    render(<DataTable<MixedRow> rows={[mixedRow]} rowKey="id" columns={mixedColumns} testId="t" />);

    const cells = within(screen.getAllByRole("row")[1]).getAllByRole("cell");
    expect(cells[1]).toHaveTextContent(EM_DASH);
    expect(cells[1]).not.toHaveTextContent("0.00%");
    expect(cells[2]).toHaveTextContent(EM_DASH);
    expect(cells[3]).toHaveTextContent(EM_DASH);
    expect(cells[4]).toHaveTextContent(EM_DASH);
    expect(screen.getByTestId("t")).not.toHaveTextContent("[object Object]");
  });

  it("lets a column render override the default so pages keep their own unit scale", () => {
    const yiColumn: DataTableColumn<MixedRow> = {
      key: "governed",
      title: "金额",
      unit: "亿",
      align: "numeric",
      render: (row) => (row.governed.raw === null ? EM_DASH : (row.governed.raw / 1e8).toFixed(2)),
    };
    render(<DataTable<MixedRow> rows={[mixedRow]} rowKey="id" columns={[yiColumn]} testId="t" />);

    expect(within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0]).toHaveTextContent("12.00");
  });
});

describe("DataTable 整列缺失原因只说一次", () => {
  it("states a column-wide missing reason once regardless of row count", () => {
    const manyRows = Array.from({ length: 20 }, (_unused, index) => industryRow(`行业${index}`, index));
    render(
      <DataTable<IndustryRow>
        rows={manyRows}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        columnNotices={[{ columnKey: "percentage", reason: "占比源未回数" }]}
        testId="t"
      />,
    );

    expect(screen.getAllByText(/占比源未回数/)).toHaveLength(1);
    expect(screen.getByTestId("t-notices")).toHaveTextContent("占比：占比源未回数");
  });

  it("merges columns sharing one reason and exposes the reason on the header title", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        columnNotices={[
          { columnKey: "percentage", reason: "占比源未回数" },
          { columnKey: "bond_count", reason: "占比源未回数" },
        ]}
        testId="t"
      />,
    );

    const notices = screen.getByTestId("t-notices");
    expect(within(notices).getAllByRole("listitem")).toHaveLength(1);
    expect(notices).toHaveTextContent("占比 / 只数：占比源未回数");

    const headers = screen.getAllByRole("columnheader");
    expect(headers[2]).toHaveAttribute("title", "占比源未回数");
    expect(headers[3]).toHaveAttribute("title", "Top10 内占比；占比源未回数");
    expect(screen.getByRole("table")).toHaveAttribute("aria-describedby", notices.id);
  });
});

describe("DataTable 五态", () => {
  it("surfaces an error inline without masking the rows already on screen", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        status="error"
        errorMessage="行业分布刷新失败"
        testId="t"
      />,
    );

    expect(screen.getByTestId("t")).toHaveAttribute("data-view", "rows");
    expect(screen.getByRole("alert")).toHaveTextContent("行业分布刷新失败");
    expect(screen.getByTestId("t-status")).toHaveAttribute("data-tone", "negative");
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("surfaces stale and partial as inline status rows with a warning tone", () => {
    const { rerender } = render(
      <DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} status="stale" testId="t" />,
    );
    expect(screen.getByTestId("t-status")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByTestId("t-status")).toHaveTextContent("延迟快照");

    rerender(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        status="partial"
        statusMessage="缺 2 个行业的估值"
        testId="t"
      />,
    );
    expect(screen.getByTestId("t-status")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByTestId("t-status")).toHaveTextContent("缺 2 个行业的估值");
  });

  it("keeps existing rows visible while a refresh is in flight", () => {
    render(
      <DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} status="loading" testId="t" />,
    );

    expect(screen.getByTestId("t")).toHaveAttribute("data-view", "rows");
    expect(screen.queryByTestId("t-skeleton")).not.toBeInTheDocument();
    expect(screen.getByTestId("t-status")).toHaveTextContent("数据刷新中");
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("collapses to an error surface when the request failed before any row arrived", () => {
    render(
      <DataTable<IndustryRow>
        rows={undefined}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        status="error"
        errorMessage="行业分布接口不可用"
        testId="t"
      />,
    );

    expect(screen.getByTestId("t")).toHaveAttribute("data-view", "error");
    expect(screen.getByTestId("t-error")).toHaveTextContent("行业分布接口不可用");
    expect(screen.queryByTestId("t-skeleton")).not.toBeInTheDocument();
  });
});

describe("DataTable Top N 与合计行", () => {
  const manyRows = Array.from({ length: 12 }, (_unused, index) => industryRow(`行业${index}`, index));

  it("renders only the first maxRows rows and expands to all on demand", async () => {
    const user = userEvent.setup();
    render(
      <DataTable<IndustryRow> rows={manyRows} rowKey="industry_name" columns={BASIC_COLUMNS} maxRows={5} testId="t" />,
    );

    expect(screen.getAllByRole("row")).toHaveLength(6);
    const toggle = screen.getByRole("button", { name: "展开全部" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByTestId("t-truncation")).toHaveTextContent("共 12 行，当前显示前 5 行");

    await user.click(toggle);

    expect(screen.getAllByRole("row")).toHaveLength(13);
    expect(screen.getByRole("button", { name: "收起" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("t-truncation")).toHaveTextContent("已展开全部 12 行");
  });

  it("keeps the truncation bar mounted in both states and the toggle keyboard reachable", async () => {
    const user = userEvent.setup();
    render(
      <DataTable<IndustryRow> rows={manyRows} rowKey="industry_name" columns={BASIC_COLUMNS} maxRows={5} testId="t" />,
    );

    const bar = screen.getByTestId("t-truncation");
    await user.tab();
    const toggle = screen.getByRole("button");
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute("aria-controls", screen.getByRole("table").querySelector("tbody")?.id);

    await user.keyboard("{Enter}");
    expect(screen.getByTestId("t-truncation")).toBe(bar);
  });

  it("renders the summary row in tfoot and dashes columns without a summary value", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        summaryRow={{ industry_name: "合计 / 后端加权", bond_count: 23 }}
        testId="t"
      />,
    );

    const summary = screen.getByTestId("t-summary");
    expect(summary.tagName).toBe("TFOOT");
    expect(within(summary).getByRole("rowheader")).toHaveTextContent("合计 / 后端加权");
    const summaryCells = within(summary).getAllByRole("cell");
    expect(summaryCells[0]).toHaveTextContent(EM_DASH);
    expect(summaryCells[1]).toHaveTextContent("23");
    expect(summaryCells[1]).toHaveAttribute("data-align", "numeric");
  });
});

describe("DataTable 行级 testId", () => {
  it("does not attach a data-testid to <tr> when rowTestId is not provided (backward compat)", () => {
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);

    const bodyRow = screen.getAllByRole("row")[1];
    expect(bodyRow).not.toHaveAttribute("data-testid");
  });

  it("derives a stable per-row testid from row data, not just the row index", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        rowTestId={(row) => `risk-row-${row.industry_name}`}
        testId="t"
      />,
    );

    expect(screen.getByTestId("risk-row-银行")).toHaveTextContent("银行");
    expect(screen.getByTestId("risk-row-城投")).toHaveTextContent("城投");
  });

  it("lets rowTestId skip individual rows by returning undefined", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        rowTestId={(row) => (row.industry_name === "城投" ? undefined : `risk-row-${row.industry_name}`)}
        testId="t"
      />,
    );

    expect(screen.queryByTestId("risk-row-城投")).not.toBeInTheDocument();
    expect(screen.getByTestId("risk-row-银行")).toBeInTheDocument();
  });
});

describe("DataTable 行级 data-* 属性", () => {
  it("attaches per-row data attributes so a whole row can be toned down", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        rowAttrs={(row) => (row.industry_name === "城投" ? { "data-deferred": "true" } : undefined)}
        rowTestId={(row) => `row-${row.industry_name}`}
        testId="t"
      />,
    );

    expect(screen.getByTestId("row-城投")).toHaveAttribute("data-deferred", "true");
    expect(screen.getByTestId("row-银行")).not.toHaveAttribute("data-deferred");
  });

  it("keeps rowTestId authoritative when rowAttrs also returns a data-testid", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        rowAttrs={() => ({ "data-testid": "from-rowAttrs" })}
        rowTestId={(row) => `row-${row.industry_name}`}
        testId="t"
      />,
    );

    expect(screen.getByTestId("row-银行")).toBeInTheDocument();
    expect(screen.queryByTestId("from-rowAttrs")).not.toBeInTheDocument();
  });

  it("leaves <tr> untouched when rowAttrs is absent (backward compat)", () => {
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);
    const bodyRow = screen.getAllByRole("row")[1] as HTMLElement;
    expect(bodyRow.getAttributeNames().filter((n) => n.startsWith("data-"))).toEqual([]);
  });
});

describe("DataTable 行头列", () => {
  it("renders the named column as <th scope=row> so a screen reader can name the row", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={BASIC_COLUMNS}
        rowHeaderKey="industry_name"
        testId="t"
      />,
    );

    const header = screen.getByRole("rowheader", { name: "银行" });
    expect(header.tagName).toBe("TH");
    expect(header).toHaveAttribute("scope", "row");
  });

  it("renders every cell as <td> when rowHeaderKey is absent (backward compat)", () => {
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);
    expect(screen.queryAllByRole("rowheader")).toHaveLength(0);
  });

  it("keeps alignment and ellipsis behaviour on the row header, not just on <td>", () => {
    render(
      <DataTable<IndustryRow>
        rows={THREE_ROWS}
        rowKey="industry_name"
        columns={[{ ...BASIC_COLUMNS[0]!, ellipsis: true }, ...BASIC_COLUMNS.slice(1)]}
        rowHeaderKey={BASIC_COLUMNS[0]!.key}
        testId="t"
      />,
    );

    const header = screen.getAllByRole("rowheader")[0] as HTMLElement;
    expect(header).toHaveAttribute("data-ellipsis", "true");
    expect(header).toHaveAttribute("data-align");
  });
});

describe("DataTable 列头换行", () => {
  it("keeps every header nowrap by default, matching production tables unchanged", () => {
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);

    for (const header of screen.getAllByRole("columnheader")) {
      expect(header).not.toHaveAttribute("data-wrap");
    }
  });

  it("marks only the column that opts into headerWrap", () => {
    const columns: DataTableColumn<IndustryRow>[] = [
      { ...BASIC_COLUMNS[0], headerWrap: true },
      ...BASIC_COLUMNS.slice(1),
    ];
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={columns} testId="t" />);

    const headers = screen.getAllByRole("columnheader");
    expect(headers[0]).toHaveAttribute("data-wrap", "true");
    expect(headers[1]).not.toHaveAttribute("data-wrap");
  });

  it("keeps the default nowrap rule and gives wrapped headers an explicit vertical-align so mixed columns don't look staggered", () => {
    const headCell = ruleBody(".headCell");
    expect(headCell).toContain("white-space: nowrap;");
    expect(headCell).toContain("vertical-align: bottom;");

    const wrapped = ruleBody('.headCell[data-wrap="true"]', { grouped: true });
    expect(wrapped).toContain("white-space: normal;");
  });
});

describe("DataTable 单元格单行省略", () => {
  it("keeps table-layout auto and leaves cells unmarked when no column declares ellipsis", () => {
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={BASIC_COLUMNS} testId="t" />);

    expect(screen.getByRole("table")).not.toHaveAttribute("data-layout");
    const firstCell = within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0];
    expect(firstCell).not.toHaveAttribute("data-ellipsis");
    expect(firstCell).not.toHaveAttribute("title");
  });

  it("switches the table to a fixed layout and gives the ellipsis cell a full-text title", () => {
    const columns: DataTableColumn<IndustryRow>[] = [
      { ...BASIC_COLUMNS[0], ellipsis: true, width: 96 },
      ...BASIC_COLUMNS.slice(1),
    ];
    render(<DataTable<IndustryRow> rows={THREE_ROWS} rowKey="industry_name" columns={columns} testId="t" />);

    expect(screen.getByRole("table")).toHaveAttribute("data-layout", "fixed");
    const firstCell = within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0];
    expect(firstCell).toHaveAttribute("data-ellipsis", "true");
    expect(firstCell).toHaveAttribute("title", "城投");

    const otherCell = within(screen.getAllByRole("row")[1]).getAllByRole("cell")[1];
    expect(otherCell).not.toHaveAttribute("data-ellipsis");
  });

  it("declares the fixed-layout and ellipsis CSS rules with the same Nocturne restrictions as the rest of the file", () => {
    expect(ruleBody('.table[data-layout="fixed"]')).toContain("table-layout: fixed;");
    const ellipsisCell = ruleBody('.cell[data-ellipsis="true"]');
    expect(ellipsisCell).toContain("overflow: hidden;");
    expect(ellipsisCell).toContain("text-overflow: ellipsis;");
    expect(ellipsisCell).toContain("white-space: nowrap;");
  });
});

describe("DataTable rowKey", () => {
  it("accepts a key selector function and falls back to an index key for blank keys", () => {
    const rows: IndustryRow[] = [industryRow("", 1), industryRow("", 2)];

    expect(() =>
      render(
        <DataTable<IndustryRow>
          rows={rows}
          rowKey={(row) => row.industry_name}
          columns={BASIC_COLUMNS}
          testId="t"
        />,
      ),
    ).not.toThrow();
    expect(screen.getAllByRole("row")).toHaveLength(3);
  });
});
