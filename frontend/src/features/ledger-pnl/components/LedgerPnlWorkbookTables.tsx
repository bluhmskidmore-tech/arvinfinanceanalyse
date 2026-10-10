import { useRef, useState } from "react";

import type { QdbGlMonthlyAnalysisSheet } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

import "./LedgerPnlWorkbookTables.css";

export type LedgerPnlWorkbookTableSpec = {
  title: string;
  sheet: QdbGlMonthlyAnalysisSheet | undefined;
  testId: string;
  columnLimit?: number;
  rowLimit?: number;
};

export type LedgerPnlWorkbookGroup = {
  id: string;
  label: string;
  tables: LedgerPnlWorkbookTableSpec[];
};

function formatAnalysisValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return EM_DASH;
    }
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  }
  return String(value);
}

/**
 * sheet 的首个展示列始终是后端约定的稳定业务维度字段（科目代码/指标/行业/行业代码等，
 * 见 backend/app/core_finance/qdb_gl_monthly_analysis.py 的 `_sheet(...)` 调用），在绝大多数
 * sheet 中逐行唯一，因此单用该字段即可作为跨重渲染稳定的行 key。
 * "异动预警"等 sheet 会对同一维度产生多条告警行，维度值可能重复；这里按出现次序
 * 追加序号兜底防碰撞，仅对重复值生效，不把 rowIndex 当默认主键。
 * 维度字段缺失（null/undefined/空串）时无稳定业务字段可用，退回该行的位置索引。
 */
function buildRowKeys(testId: string, dimensionColumn: string | undefined, rows: Array<Record<string, unknown>>): string[] {
  const occurrenceCounts = new Map<string, number>();
  return rows.map((row, rowIndex) => {
    const dimensionValue = dimensionColumn ? row[dimensionColumn] : undefined;
    if (dimensionValue === null || dimensionValue === undefined || dimensionValue === "") {
      return `${testId}-row-${rowIndex}`;
    }
    const base = `${testId}-${String(dimensionValue)}`;
    const occurrence = occurrenceCounts.get(base) ?? 0;
    occurrenceCounts.set(base, occurrence + 1);
    return occurrence === 0 ? base : `${base}-dup${occurrence}`;
  });
}

function pickDisplayColumns(sheet: QdbGlMonthlyAnalysisSheet | undefined, limit = 4) {
  return (sheet?.columns ?? []).slice(0, limit);
}

function hasDisplayData(spec: LedgerPnlWorkbookTableSpec) {
  return pickDisplayColumns(spec.sheet, spec.columnLimit ?? 4).length > 0 && (spec.sheet?.rows.length ?? 0) > 0;
}

function firstGroupWithData(groups: LedgerPnlWorkbookGroup[]) {
  return groups.find((group) => group.tables.some(hasDisplayData))?.id ?? groups[0]?.id ?? "";
}

function WorkbookTable({ spec }: { spec: LedgerPnlWorkbookTableSpec }) {
  const [expanded, setExpanded] = useState(false);
  const columns = pickDisplayColumns(spec.sheet, spec.columnLimit ?? 4);
  const allRows = spec.sheet?.rows ?? [];
  const numericColumns = new Set(columns.filter((column) =>
    allRows.some((row) => typeof row[column] === "number")
    && allRows.every((row) => row[column] == null || row[column] === "" || typeof row[column] === "number"),
  ));
  const rowLimit = spec.rowLimit ?? 5;
  const isTruncated = allRows.length > rowLimit;
  const rows = expanded || !isTruncated ? allRows : allRows.slice(0, rowLimit);
  const hasData = columns.length > 0 && allRows.length > 0;
  const rowKeys = buildRowKeys(spec.testId, columns[0], rows);

  return (
    <section
      data-testid={spec.testId}
      className={`ledger-pnl-workbook-tables__table${hasData ? "" : " ledger-pnl-workbook-tables__table--empty"}`}
    >
      <h3 className="ledger-pnl-workbook-tables__table-title">{spec.title}</h3>
      {hasData ? (
        <>
          {isTruncated ? (
            <div
              className="ledger-pnl-workbook-tables__truncation"
              data-testid={`${spec.testId}-truncation`}
            >
              <span>
                {expanded
                  ? `已展开全部 ${allRows.length} 行`
                  : `共 ${allRows.length} 行，仅显示前 ${rowLimit} 行`}
              </span>
              <button
                type="button"
                className="ledger-pnl-workbook-tables__truncation-toggle"
                onClick={() => setExpanded((prev) => !prev)}
              >
                {expanded ? "收起" : "展开全部"}
              </button>
            </div>
          ) : null}
          <div className="ledger-pnl-workbook-tables__table-scroll">
            <table className="ledger-pnl-workbook-tables__table-data">
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th key={column} data-numeric={numericColumns.has(column)}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={rowKeys[rowIndex]}>
                    {columns.map((column) => (
                      <td key={column} data-numeric={numericColumns.has(column)}>{formatAnalysisValue(row[column])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="ledger-pnl-workbook-tables__empty">暂无可展示数据</p>
      )}
    </section>
  );
}

export function LedgerPnlWorkbookTables(props: {
  groups: LedgerPnlWorkbookGroup[];
  /** 默认 "ledger-pnl-workbook-tables" */
  testId?: string;
}): JSX.Element {
  const testId = props.testId ?? "ledger-pnl-workbook-tables";
  const [selectedGroupId, setSelectedGroupId] = useState(() => firstGroupWithData(props.groups));
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedGroup = props.groups.find((group) => group.id === selectedGroupId) ?? props.groups[0];

  const selectGroupAt = (index: number) => {
    const nextGroup = props.groups[index];
    if (!nextGroup) {
      return;
    }
    setSelectedGroupId(nextGroup.id);
    tabRefs.current[index]?.focus();
  };

  return (
    <section className="ledger-pnl-workbook-tables" data-testid={testId}>
      <div className="ledger-pnl-workbook-tables__tabs" role="tablist" aria-label="总账月度工作簿分组">
        {props.groups.map((group, index) => {
          const tabId = `${testId}-tab-${group.id}`;
          const panelId = `${testId}-panel-${group.id}`;
          const availableCount = group.tables.filter(hasDisplayData).length;
          const isSelected = group.id === selectedGroup?.id;

          return (
            <button
              key={group.id}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              id={tabId}
              data-testid={`${testId}-tab-${group.id}`}
              className={`ledger-pnl-workbook-tables__tab${availableCount === 0 ? " ledger-pnl-workbook-tables__tab--empty" : ""}`}
              type="button"
              role="tab"
              aria-selected={isSelected}
              aria-controls={panelId}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => setSelectedGroupId(group.id)}
              onKeyDown={(event) => {
                if (event.key === "ArrowLeft") {
                  event.preventDefault();
                  selectGroupAt((index - 1 + props.groups.length) % props.groups.length);
                }
                if (event.key === "ArrowRight") {
                  event.preventDefault();
                  selectGroupAt((index + 1) % props.groups.length);
                }
              }}
            >
              <span>{group.label}</span>
              <span className="ledger-pnl-workbook-tables__tab-count">
                {availableCount}/{group.tables.length}
              </span>
            </button>
          );
        })}
      </div>

      {selectedGroup ? (
        <div
          id={`${testId}-panel-${selectedGroup.id}`}
          data-testid={`${testId}-panel-${selectedGroup.id}`}
          className="ledger-pnl-workbook-tables__panel"
          role="tabpanel"
          aria-labelledby={`${testId}-tab-${selectedGroup.id}`}
        >
          <div className="ledger-pnl-workbook-tables__grid">
            {selectedGroup.tables.map((spec) => (
              <WorkbookTable key={spec.testId} spec={spec} />
            ))}
          </div>
        </div>
      ) : (
        <div className="ledger-pnl-workbook-tables__empty-group" role="status">
          暂无工作簿数据
        </div>
      )}
    </section>
  );
}
