import { EM_DASH } from "../../../utils/format";
import type { ModuleHomeDetailPanel, ModuleHomeDetailRow, ModuleHomeTone } from "./moduleHomeModel";
import { PortfolioStructureChart } from "./PortfolioStructureChart";
import dhStyles from "../dashboard-home/dashboardHome.module.css";
import styles from "./portfolioHome.module.css";

function toneClass(tone: ModuleHomeTone) {
  if (tone === "ok") return styles.toneOk;
  if (tone === "watch") return styles.toneWatch;
  if (tone === "error") return styles.toneError;
  return styles.toneMuted;
}

function statePillClass(tone: ModuleHomeTone) {
  if (tone === "ok") return `${styles.statePill} ${styles.stateOk}`;
  if (tone === "error") return `${styles.statePill} ${styles.stateError}`;
  if (tone === "watch") return `${styles.statePill} ${styles.stateWatch}`;
  return styles.statePill;
}

function sourceParts(row: ModuleHomeDetailRow) {
  return row.source
    .split("·")
    .map((part) => part.trim())
    .filter(Boolean);
}

type StructureTableHeader = {
  key: string;
  label: string;
  title?: string;
};

type StructureTableLayout = {
  headers: StructureTableHeader[];
  /** 返回 label 之后各列的展示文本，与 headers[1..] 对齐。 */
  rowCells: (row: ModuleHomeDetailRow) => string[];
};

/**
 * 表头与取数随结构维度切换：四个面板的行数据字段各不相同
 * （子组合带 dv01Display/countDisplay；收益率桶 source=只数；
 * 利差 source=市值·只数、value=中位收益率；业务类型 source=市值·久期来源）。
 */
const STRUCTURE_TABLE_LAYOUTS: Record<string, StructureTableLayout> = {
  "portfolio-comparison": {
    headers: [
      { key: "label", label: "子组合" },
      { key: "dv01", label: "DV01" },
      { key: "count", label: "持仓" },
      { key: "value", label: "市值" },
    ],
    rowCells: (row) => {
      const parts = sourceParts(row);
      return [
        row.dv01Display ?? parts[0]?.replace(/^DV01\s*/i, "") ?? EM_DASH,
        row.countDisplay ? `${row.countDisplay} 只` : parts[1] ?? EM_DASH,
        row.value,
      ];
    },
  },
  "yield-distribution": {
    headers: [
      { key: "label", label: "收益率桶" },
      { key: "count", label: "只数" },
      { key: "value", label: "市值" },
    ],
    rowCells: (row) => [row.source || EM_DASH, row.value],
  },
  "spread-analysis": {
    headers: [
      { key: "label", label: "券种" },
      { key: "scale", label: "市值" },
      { key: "count", label: "只数" },
      {
        key: "value",
        label: "中位收益率",
        title: "券种内个券 YTM 中位数（median_yield），非对国债利差",
      },
    ],
    rowCells: (row) => {
      const parts = sourceParts(row);
      return [parts[0] ?? EM_DASH, parts[1] ?? EM_DASH, row.value];
    },
  },
  "business-type-metrics": {
    headers: [
      { key: "label", label: "业务类型" },
      { key: "scale", label: "市值" },
      { key: "duration-source", label: "久期来源" },
      { key: "value", label: "收益率与久期" },
    ],
    rowCells: (row) => {
      const parts = sourceParts(row);
      return [
        parts[0]?.replace(/^市值\s*/, "") ?? EM_DASH,
        parts[1] ?? EM_DASH,
        row.value,
      ];
    },
  },
};

const FALLBACK_LAYOUT = STRUCTURE_TABLE_LAYOUTS["portfolio-comparison"];

const CELL_CLASSES_BY_COLUMN_COUNT: Record<number, string[]> = {
  4: [styles.compactSource, styles.compactCount, styles.compactValue],
  3: [styles.compactCount, styles.compactValue],
};

/** 收益率面板的组合汇总行不属于桶明细，抽出为表格上方的汇总读数。 */
function isYieldSummaryRow(row: ModuleHomeDetailRow) {
  return row.key === "yield-weighted-ytm" || row.source === "weighted_ytm";
}

type PortfolioStructureTabPanelProps = {
  panel: ModuleHomeDetailPanel;
};

export function PortfolioStructureTabPanel({ panel }: PortfolioStructureTabPanelProps) {
  const hasChart = Boolean(panel.chart && panel.chart.categories.length > 0);
  const layout = STRUCTURE_TABLE_LAYOUTS[panel.key] ?? FALLBACK_LAYOUT;
  const cellClasses =
    CELL_CLASSES_BY_COLUMN_COUNT[layout.headers.length] ?? CELL_CLASSES_BY_COLUMN_COUNT[4];
  const summaryRows =
    panel.key === "yield-distribution" ? panel.rows.filter(isYieldSummaryRow) : [];
  const tableRows =
    summaryRows.length > 0 ? panel.rows.filter((row) => !isYieldSummaryRow(row)) : panel.rows;

  return (
    <div className={`${styles.embeddedPanel} ${hasChart ? styles.structureSplit : ""}`}>
      <div
        className={styles.structureListCol}
        role="region"
        aria-label={`${panel.title}结构明细`}
        tabIndex={panel.rows.length > 0 ? 0 : undefined}
      >
        <div className={styles.embeddedPanelHead}>
          <span className={statePillClass(panel.tone)}>{panel.stateLabel}</span>
        </div>
        <p className={styles.detailSource}>{panel.meta}</p>
        {panel.rows.length > 0 ? (
          <>
            {summaryRows.map((row) => (
              <p
                className={styles.structureSummaryLine}
                data-testid="module-home-portfolio-yield-summary"
                key={row.key}
                title={`字段 ${row.source}（${row.label}）`}
              >
                <span>加权到期收益率</span>
                <strong className={toneClass(row.tone)}>{row.value}</strong>
              </p>
            ))}
            <div
              className={styles.compactListHeader}
              aria-hidden="true"
              data-cols={layout.headers.length}
            >
              {layout.headers.map((header) => (
                <span key={header.key} title={header.title}>
                  {header.label}
                </span>
              ))}
            </div>
            <ul className={styles.compactList}>
              {tableRows.map((row) => {
                const cells = layout.rowCells(row);
                return (
                  <li
                    className={styles.compactRow}
                    data-cols={layout.headers.length}
                    key={row.key}
                  >
                    <div className={styles.compactRowMain}>
                      <span className={styles.compactLabel}>{row.label}</span>
                    </div>
                    {cells.map((cell, index) => {
                      const isValueCell = index === cells.length - 1;
                      return (
                        <span
                          className={
                            isValueCell
                              ? `${cellClasses[index]} ${toneClass(row.tone)}`
                              : cellClasses[index]
                          }
                          key={layout.headers[index + 1]?.key ?? index}
                        >
                          {cell}
                        </span>
                      );
                    })}
                  </li>
                );
              })}
            </ul>
          </>
        ) : (
          <p className={`${styles.detailSource} ${toneClass(panel.tone)}`}>{panel.stateDetail}</p>
        )}
      </div>
      {hasChart && panel.chart ? (
        <div className={`${dhStyles.dhInsetSurface} ${styles.structureChartCol}`}>
          <PortfolioStructureChart chart={panel.chart} />
        </div>
      ) : null}
    </div>
  );
}
