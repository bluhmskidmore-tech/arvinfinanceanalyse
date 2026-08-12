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

export const LEDGER_PNL_WORKBOOK_GROUP_DEFS = [
  {
    id: "overview",
    label: "总览与预警",
    titles: ["财务指标落地状态", "3位科目总览", "11位偏离TOP", "异动预警"],
  },
  {
    id: "structure",
    label: "资产负债结构",
    titles: ["资产结构", "负债结构", "贷款行业", "存款行业_活期", "存款行业_定期", "行业存贷差"],
  },
  {
    id: "segment",
    label: "分部与条线规模",
    titles: [
      "分部基础规模",
      "分部规模同比环比",
      "公司规模",
      "公司规模同比环比",
      "零售规模",
      "零售规模同比环比",
      "金融市场规模",
      "金融市场规模同比环比",
    ],
  },
  {
    id: "income",
    label: "收益与利息",
    titles: ["收益率分析（总账可复算）", "收益量价归因（年累计同比）", "存款利息拆分", "母公司营收分项", "外币分析"],
  },
] as const;

export function buildLedgerPnlWorkbookGroups(
  specsByTitle: Record<string, LedgerPnlWorkbookTableSpec>,
): LedgerPnlWorkbookGroup[] {
  return LEDGER_PNL_WORKBOOK_GROUP_DEFS.map((definition) => ({
    id: definition.id,
    label: definition.label,
    tables: definition.titles.flatMap((title) => {
      const spec = specsByTitle[title];
      return spec ? [spec] : [];
    }),
  }));
}

function formatAnalysisValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return EM_DASH;
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  }
  return String(value);
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
  const columns = pickDisplayColumns(spec.sheet, spec.columnLimit ?? 4);
  const rows = spec.sheet?.rows.slice(0, spec.rowLimit ?? 5) ?? [];
  const hasData = columns.length > 0 && rows.length > 0;

  return (
    <section
      data-testid={spec.testId}
      className={`ledger-pnl-workbook-tables__table${hasData ? "" : " ledger-pnl-workbook-tables__table--empty"}`}
    >
      <h3 className="ledger-pnl-workbook-tables__table-title">{spec.title}</h3>
      {hasData ? (
        <div className="ledger-pnl-workbook-tables__table-scroll">
          <table className="ledger-pnl-workbook-tables__table-data">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`${spec.testId}-${rowIndex}`}>
                  {columns.map((column) => (
                    <td key={column}>{formatAnalysisValue(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
