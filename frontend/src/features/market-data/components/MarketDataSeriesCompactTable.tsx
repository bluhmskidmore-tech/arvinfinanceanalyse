import { useEffect, useMemo, useState, type HTMLAttributes } from "react";
import { Table, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens } from "../../../theme/designSystem";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValueParts,
} from "../../../utils/choiceMacroFormat";
import type { ChoiceMacroRecentPoint } from "../../../api/contracts";
import {
  marketSeriesRefreshTier,
  type MarketObservationPoint,
} from "../lib/marketDataCategoryStore";
import { MarketDataSeriesTimeChart } from "./MarketDataSeriesTimeChart";
import { MarketTerminalSparkline } from "./MarketTerminalSparkline";

export type MarketDataSeriesCompactRow = MarketObservationPoint & {
  tierLabel?: string;
};

const PLACEHOLDER = "—";

function deltaColor(value: string) {
  if (value.startsWith("-")) {
    return designTokens.color.semantic.profit;
  }
  if (value.startsWith("+")) {
    return designTokens.color.semantic.loss;
  }
  return designTokens.color.neutral[700];
}

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
  return [...(points ?? [])]
    .sort((left, right) => left.trade_date.localeCompare(right.trade_date))
    .map((point) => point.value_numeric);
}

function sortedRecentPoints(points: ChoiceMacroRecentPoint[] | undefined) {
  return [...(points ?? [])].sort((left, right) => left.trade_date.localeCompare(right.trade_date));
}

function formatRecentTrailTooltip(points: ChoiceMacroRecentPoint[] | undefined) {
  const trail = sortedRecentPoints(points).slice(-5);
  if (trail.length === 0) {
    return null;
  }
  return trail.map((point) => `${point.trade_date}  ${point.value_numeric.toFixed(2)}`).join("\n");
}

function formatPriorPointHint(
  points: ChoiceMacroRecentPoint[] | undefined,
  currentTradeDate: string,
): string | null {
  const sorted = sortedRecentPoints(points);
  if (sorted.length < 2) {
    return null;
  }
  const prior =
    sorted.filter((point) => point.trade_date < currentTradeDate).at(-1) ??
    sorted[sorted.length - 2];
  if (!prior) {
    return null;
  }
  return `${prior.trade_date.slice(5)} ${prior.value_numeric.toFixed(2)}`;
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
}: {
  series: readonly MarketDataSeriesCompactRow[];
  testIdPrefix?: string;
  showTier?: boolean;
  initialVisibleCount?: number;
  compactSparseColumns?: boolean;
}) {
  const [expandedSeriesId, setExpandedSeriesId] = useState<string | null>(null);
  const [showAllRows, setShowAllRows] = useState(false);

  const visibleSeries = useMemo(() => {
    if (!initialVisibleCount || showAllRows || series.length <= initialVisibleCount) {
      return series;
    }
    return series.slice(0, initialVisibleCount);
  }, [initialVisibleCount, series, showAllRows]);

  const hiddenRowCount =
    initialVisibleCount && !showAllRows && series.length > initialVisibleCount
      ? series.length - initialVisibleCount
      : 0;

  useEffect(() => {
    if (!expandedSeriesId) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setExpandedSeriesId(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expandedSeriesId]);

  const showDeltaColumn = useMemo(() => {
    if (!compactSparseColumns) {
      return true;
    }
    return series.some((row) => formatChoiceMacroDelta(row, { emptyDisplay: PLACEHOLDER }) !== PLACEHOLDER);
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
        render: (name: string, row) => (
          <span title={`${name} (${row.series_id})`}>{name}</span>
        ),
      },
      {
        title: "最新",
        key: "value",
        align: "right",
        width: 84,
        className: "market-data-series-compact-col-value",
        render: (_value, row) => {
          const { value, unit } = formatChoiceMacroValueParts(row);
          return (
            <div className="market-data-series-compact-value-stack">
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
          const delta = formatChoiceMacroDelta(row, { emptyDisplay: PLACEHOLDER });
          if (delta === PLACEHOLDER) {
            return <CompactPlaceholder />;
          }
          return (
            <span className="market-data-tabular market-data-series-compact-delta" style={{ color: deltaColor(delta) }}>
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
          const delta = formatChoiceMacroDelta(row, { emptyDisplay: PLACEHOLDER });
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
              ) : compactSparseColumns ? (
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
                  setExpandedSeriesId((current) => (current === row.series_id ? null : row.series_id))
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
  }, [compactSparseColumns, expandedSeriesId, showDeltaColumn, showTier, testIdPrefix]);

  if (series.length === 0) {
    return (
      <div className="market-data-series-compact-empty" data-testid={`${testIdPrefix}-compact-empty`}>
        当前无可展示序列。
      </div>
    );
  }

  return (
    <div className="market-data-series-compact-wrap">
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
        onRow={(row) =>
          ({
            "data-testid": `${testIdPrefix}-${row.series_id}`,
          }) as HTMLAttributes<HTMLElement>
        }
      />
      {expandedSeriesId ? (() => {
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
            展开全部 {series.length} 条
          </button>
        </div>
      ) : null}
      {initialVisibleCount && showAllRows && series.length > initialVisibleCount ? (
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
    </div>
  );
}
