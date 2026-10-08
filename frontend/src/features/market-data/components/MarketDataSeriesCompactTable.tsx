import { useCallback, useEffect, useMemo, useState, type HTMLAttributes } from "react";
import { Table, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";

import { EM_DASH } from "../../../utils/format";
import {
  formatMarketSeriesDelta,
  formatMarketSeriesValueParts,
  seriesDisplayName,
} from "../lib/marketDataFormat";
import type { ChoiceMacroRecentPoint } from "../../../api/contracts";
import {
  marketSeriesRefreshTier,
  seriesAgeTier,
  type MarketObservationPoint,
} from "../lib/marketDataCategoryStore";
import { MarketDataSeriesTimeChart } from "./MarketDataSeriesTimeChart";
import { MarketTerminalSparkline } from "./MarketTerminalSparkline";

export type MarketDataSeriesCompactRow = MarketObservationPoint & {
  tierLabel?: string;
};

const PLACEHOLDER = EM_DASH;

// 时效分档 seriesAgeTier（>365 天历史存量折叠小节、90~365 天淡化）见 lib/marketDataCategoryStore。

// 序列上行=偏空、下行=偏多；着色复用页面 ticker 的 data-tone 语义类
// （MarketDataPage.css：up=红、down=绿、flat=muted），不再使用内联色值。
function sparkToneFromDelta(delta: string): "up" | "down" | "flat" {
  if (delta.startsWith("-")) {
    return "down";
  }
  if (delta.startsWith("+")) {
    return "up";
  }
  return "flat";
}

function tierLabelFor(point: MarketObservationPoint) {
  return marketSeriesRefreshTier(point) === "fallback" ? "降级" : "稳定";
}

function sparklineValuesFromRecent(points: ChoiceMacroRecentPoint[] | undefined): number[] {
  // A compact sparkline cannot show dated gaps. Suppress it rather than join
  // across missing observations or turn SQL/wire null into a zero.
  if (points?.some((point) => point.value_numeric == null || !Number.isFinite(point.value_numeric))) {
    return [];
  }
  return [...(points ?? [])]
    .sort((left, right) => left.trade_date.localeCompare(right.trade_date))
    .map((point) => point.value_numeric)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

function sortedRecentPoints(points: ChoiceMacroRecentPoint[] | undefined) {
  return [...(points ?? [])].sort((left, right) => left.trade_date.localeCompare(right.trade_date));
}

function formatRecentTrailTooltip(points: ChoiceMacroRecentPoint[] | undefined) {
  const trail = sortedRecentPoints(points).slice(-5);
  if (trail.length === 0) {
    return null;
  }
  return trail.map((point) => `${point.trade_date}  ${point.value_numeric == null || !Number.isFinite(point.value_numeric) ? EM_DASH : point.value_numeric.toFixed(2)}`).join("\n");
}

function formatPriorPointHint(
  points: ChoiceMacroRecentPoint[] | undefined,
  currentTradeDate: string,
): string | null {
  const sorted = sortedRecentPoints(points);
  // A fallback headline must not describe itself (or a same-date revision)
  // as a previous-date observation when there is no earlier date.
  const prior = sorted.filter((point) => point.trade_date < currentTradeDate).at(-1);
  if (!prior) {
    return null;
  }
  return `${prior.trade_date.slice(5)} ${prior.value_numeric == null || !Number.isFinite(prior.value_numeric) ? EM_DASH : prior.value_numeric.toFixed(2)}`;
}

function CompactPlaceholder() {
  return <span className="market-data-series-compact-placeholder">{PLACEHOLDER}</span>;
}

export function MarketDataSeriesCompactTable({
  series,
  testIdPrefix = "market-data-series",
  showTier = false,
  initialVisibleCount,
  compactSparseColumns = false,
  observationDate,
  selectedSeriesId,
  onSelectedSeriesChange,
}: {
  series: readonly MarketDataSeriesCompactRow[];
  testIdPrefix?: string;
  showTier?: boolean;
  initialVisibleCount?: number;
  compactSparseColumns?: boolean;
  /** 时效分档的观察日（YYYY-MM-DD）；缺省取当天。 */
  observationDate?: string;
  /** 受控选中序列（序列浏览器钻取）；与 onSelectedSeriesChange 成对使用。 */
  selectedSeriesId?: string | null;
  /** 提供后表格进入受控模式：不再内联渲染走势图，选中态交由调用方（如 URL query）承载。 */
  onSelectedSeriesChange?: (seriesId: string | null) => void;
}) {
  const [internalExpandedSeriesId, setInternalExpandedSeriesId] = useState<string | null>(null);
  const isSelectionControlled = onSelectedSeriesChange !== undefined;
  const expandedSeriesId = isSelectionControlled
    ? (selectedSeriesId ?? null)
    : internalExpandedSeriesId;
  const changeExpandedSeriesId = useCallback(
    (next: string | null) => {
      if (onSelectedSeriesChange) {
        onSelectedSeriesChange(next);
      } else {
        setInternalExpandedSeriesId(next);
      }
    },
    [onSelectedSeriesChange],
  );
  const [showAllRows, setShowAllRows] = useState(false);
  const resolvedObservationDate = observationDate ?? dayjs().format("YYYY-MM-DD");

  // 行分组：>365 天的行归入"历史存量"折叠小节；其余走主表（90-365 天仅淡化）。
  const currentSeries = useMemo(
    () =>
      series.filter(
        (row) => seriesAgeTier(row.trade_date, resolvedObservationDate) !== "historical",
      ),
    [resolvedObservationDate, series],
  );
  const historicalSeries = useMemo(
    () =>
      series.filter(
        (row) => seriesAgeTier(row.trade_date, resolvedObservationDate) === "historical",
      ),
    [resolvedObservationDate, series],
  );

  const visibleSeries = useMemo(() => {
    if (!initialVisibleCount || showAllRows || currentSeries.length <= initialVisibleCount) {
      return currentSeries;
    }
    return currentSeries.slice(0, initialVisibleCount);
  }, [currentSeries, initialVisibleCount, showAllRows]);

  const hiddenRowCount =
    initialVisibleCount && !showAllRows && currentSeries.length > initialVisibleCount
      ? currentSeries.length - initialVisibleCount
      : 0;

  useEffect(() => {
    if (!expandedSeriesId) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        changeExpandedSeriesId(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expandedSeriesId, changeExpandedSeriesId]);

  const showDeltaColumn = useMemo(() => {
    if (!compactSparseColumns) {
      return true;
    }
    return series.some((row) => formatMarketSeriesDelta(row, { emptyDisplay: PLACEHOLDER }) !== PLACEHOLDER);
  }, [compactSparseColumns, series]);

  const columns: ColumnsType<MarketDataSeriesCompactRow> = useMemo(() => {
    const cols: ColumnsType<MarketDataSeriesCompactRow> = [];

    if (showTier) {
      cols.push({
        title: "链路",
        dataIndex: "tierLabel",
        key: "tierLabel",
        width: 56,
        render: (_value, row) => row.tierLabel ?? tierLabelFor(row),
      });
    }

    cols.push(
      {
        title: "指标",
        dataIndex: "series_name",
        key: "series_name",
        ellipsis: true,
        // 展示清洗短名（display_name 回退 series_name），title 保留原始名+编号便于溯源。
        render: (_name: string, row) => {
          const isHistorical =
            seriesAgeTier(row.trade_date, resolvedObservationDate) === "historical";
          return (
            <span title={`${row.series_name} (${row.series_id})`}>
              {seriesDisplayName(row)}
              {isHistorical ? (
                <span className="market-data-series-compact-cutoff">
                  数据截至 {row.trade_date}
                </span>
              ) : null}
            </span>
          );
        },
      },
      {
        title: "最新",
        key: "value",
        align: "right",
        width: 84,
        className: "market-data-series-compact-col-value",
        render: (_value, row) => {
          const { value, unit } = formatMarketSeriesValueParts(row);
          const rawValue = row.value_numeric != null && Number.isFinite(row.value_numeric) ? row.value_numeric : EM_DASH;
          const rawTitle = `${rawValue}${row.unit?.trim() ? ` ${row.unit.trim()}` : ""}`;
          return (
            <div className="market-data-series-compact-value-stack" title={rawTitle}>
              <span className="market-data-series-compact-value">{value}</span>
              {unit ? <span className="market-data-series-compact-unit">{unit}</span> : null}
            </div>
          );
        },
      },
      {
        title: "变动",
        key: "delta",
        align: "right",
        width: 76,
        className: "market-data-series-compact-col-delta",
        render: (_value, row) => {
          const delta = formatMarketSeriesDelta(row, { emptyDisplay: PLACEHOLDER });
          if (delta === PLACEHOLDER) {
            return <CompactPlaceholder />;
          }
          return (
            <span
              className="market-data-terminal-ticker-delta market-data-series-compact-delta"
              data-tone={sparkToneFromDelta(delta)}
            >
              {delta}
            </span>
          );
        },
      },
      {
        title: "交易日",
        dataIndex: "trade_date",
        key: "trade_date",
        width: 96,
        responsive: ["md"],
        className: "market-data-series-compact-col-date",
        render: (tradeDate: string) => (
          <span className="market-data-tabular market-data-series-compact-date">{tradeDate}</span>
        ),
      },
      {
        title: "近期",
        key: "recent",
        width: 148,
        className: "market-data-series-compact-col-recent",
        render: (_value, row) => {
          const sparkValues = sparklineValuesFromRecent(row.recent_points);
          const delta = formatMarketSeriesDelta(row, { emptyDisplay: PLACEHOLDER });
          const priorHint = formatPriorPointHint(row.recent_points, row.trade_date);
          const tooltipTitle = formatRecentTrailTooltip(row.recent_points);
          const isExpanded = expandedSeriesId === row.series_id;
          const recentVisual = (
            <div className="market-data-series-compact-recent-visual">
              {sparkValues.length >= 2 ? (
                <MarketTerminalSparkline
                  values={sparkValues}
                  tone={sparkToneFromDelta(delta)}
                  variant="ticker"
                />
              ) : compactSparseColumns && !row.recent_points?.some((point) => point.value_numeric == null || !Number.isFinite(point.value_numeric)) ? (
                <span className="market-data-series-compact-sparse-label">低频</span>
              ) : (
                <CompactPlaceholder />
              )}
              {priorHint ? (
                <span className="market-data-series-compact-prior">{priorHint}</span>
              ) : null}
            </div>
          );

          return (
            <div className="market-data-series-compact-recent-cell">
              {tooltipTitle ? (
                <Tooltip title={tooltipTitle} placement="topLeft" mouseEnterDelay={0.35} destroyOnHidden>
                  {recentVisual}
                </Tooltip>
              ) : (
                recentVisual
              )}
              <button
                type="button"
                className="market-data-series-chart-toggle"
                data-testid={`${testIdPrefix}-chart-toggle-${row.series_id}`}
                aria-expanded={isExpanded}
                onClick={() =>
                  changeExpandedSeriesId(expandedSeriesId === row.series_id ? null : row.series_id)
                }
              >
                {isExpanded ? "收起" : "走势"}
              </button>
            </div>
          );
        },
      },
    );

    if (!showDeltaColumn) {
      return cols.filter((column) => column.key !== "delta");
    }

    return cols;
  }, [
    changeExpandedSeriesId,
    compactSparseColumns,
    expandedSeriesId,
    resolvedObservationDate,
    showDeltaColumn,
    showTier,
    testIdPrefix,
  ]);

  if (series.length === 0) {
    return (
      <div className="market-data-series-compact-empty" data-testid={`${testIdPrefix}-compact-empty`}>
        当前无可展示序列。
      </div>
    );
  }

  const rowProps = (row: MarketDataSeriesCompactRow) =>
    ({
      "data-testid": `${testIdPrefix}-${row.series_id}`,
      "data-age": seriesAgeTier(row.trade_date, resolvedObservationDate),
    }) as HTMLAttributes<HTMLElement>;

  return (
    <div className="market-data-series-compact-wrap">
      {currentSeries.length > 0 ? (
        <Table<MarketDataSeriesCompactRow>
          className="market-data-series-compact-table"
          data-testid={`${testIdPrefix}-compact-table`}
          size="small"
          pagination={false}
          rowKey="series_id"
          columns={columns}
          dataSource={[...visibleSeries]}
          scroll={{ x: 520 }}
          tableLayout="fixed"
          onRow={rowProps}
        />
      ) : null}
      {/* 受控模式下选中走势由调用方（浏览器视图钻取区）渲染，表内不再重复内联图。 */}
      {expandedSeriesId && !isSelectionControlled ? (() => {
        const expandedRow = series.find((row) => row.series_id === expandedSeriesId);
        if (!expandedRow) {
          return null;
        }
        return (
          <div
            className="market-data-series-inline-chart"
            data-testid={`${testIdPrefix}-inline-chart-${expandedSeriesId}`}
          >
            <MarketDataSeriesTimeChart
              series={expandedRow}
              testId={`${testIdPrefix}-time-chart-${expandedSeriesId}`}
            />
          </div>
        );
      })() : null}
      {hiddenRowCount > 0 ? (
        <div className="market-data-series-compact-expand">
          <button
            type="button"
            className="market-data-series-compact-expand-btn"
            data-testid={`${testIdPrefix}-expand-all`}
            onClick={() => setShowAllRows(true)}
          >
            展开全部 {currentSeries.length} 条
          </button>
        </div>
      ) : null}
      {initialVisibleCount && showAllRows && currentSeries.length > initialVisibleCount ? (
        <div className="market-data-series-compact-expand">
          <button
            type="button"
            className="market-data-series-compact-expand-btn"
            data-testid={`${testIdPrefix}-collapse`}
            onClick={() => setShowAllRows(false)}
          >
            收起列表
          </button>
        </div>
      ) : null}
      {historicalSeries.length > 0 ? (
        /* 原生 details：历史存量默认折叠但 DOM 常驻（折叠可及，不是隐藏删除）。 */
        <details
          className="market-data-series-compact-historical"
          data-testid={`${testIdPrefix}-historical-section`}
        >
          <summary data-testid={`${testIdPrefix}-historical-summary`}>
            历史存量（{historicalSeries.length} 条）
          </summary>
          <Table<MarketDataSeriesCompactRow>
            className="market-data-series-compact-table"
            data-testid={`${testIdPrefix}-historical-table`}
            size="small"
            pagination={false}
            rowKey="series_id"
            columns={columns}
            dataSource={[...historicalSeries]}
            scroll={{ x: 520 }}
            tableLayout="fixed"
            onRow={rowProps}
          />
        </details>
      ) : null}
    </div>
  );
}
