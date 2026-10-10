import { useMemo } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { TONE_DH_CSS_VAR } from "../../../utils/tone";
import type {
  MarketDataMoneyMarketRow,
  MarketDataMoneyMarketSection,
  MarketSourceFilter,
} from "../lib/marketDataTerminalModel";
import { filterMoneyMarketRows, formatTerminalSourceSummary } from "../lib/marketDataTerminalModel";
import { MarketDataSeriesTimeChart } from "./MarketDataSeriesTimeChart";
import { MarketTerminalSparkline } from "./MarketTerminalSparkline";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

// 资金利率下行=偏多（positive）、上行=偏空（negative）；着色走 Nocturne 主题链
// （TONE_CSS_VAR 的 --ib-* 在本页 scope 内解析为边界钢蓝值，须用 --dh-api-* 入口）。
function deltaTextColor(value: string) {
  if (value.startsWith("-")) {
    return TONE_DH_CSS_VAR.positive;
  }
  if (value.startsWith("+")) {
    return TONE_DH_CSS_VAR.negative;
  }
  return TONE_DH_CSS_VAR.neutral;
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

function sourceSummary(model: MarketDataMoneyMarketSection) {
  return formatTerminalSourceSummary(model.source);
}

function compactSourceModeLabel(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "source-pending";
  }
  if (trimmed === "latest_snapshot") {
    return "latest";
  }
  if (trimmed.length <= 12) {
    return trimmed;
  }
  return `${trimmed.slice(0, 9)}...`;
}

function resolveHighlightSeries(
  rows: readonly MarketDataMoneyMarketRow[],
  seriesById: ReadonlyMap<string, ChoiceMacroLatestPoint> | undefined,
): ChoiceMacroLatestPoint | null {
  if (!seriesById || rows.length === 0) {
    return null;
  }
  const dr007 = rows.find((row) => row.name === "DR007" || row.seriesId.includes("DR007"));
  const target = dr007 ?? rows[0];
  return seriesById.get(target.seriesId) ?? null;
}

export function MoneyMarketTable({
  model,
  sourceFilter = "all",
  catalogVendorNames,
  highlightSeriesById,
  embedded = false,
}: {
  model: MarketDataMoneyMarketSection;
  sourceFilter?: MarketSourceFilter;
  catalogVendorNames?: ReadonlyMap<string, string>;
  highlightSeriesById?: ReadonlyMap<string, ChoiceMacroLatestPoint>;
  embedded?: boolean;
}) {
  const dataSource = filterMoneyMarketRows(model.rows, sourceFilter, catalogVendorNames);
  const highlightSeries = useMemo(
    () => resolveHighlightSeries(dataSource, highlightSeriesById),
    [dataSource, highlightSeriesById],
  );

  const columns: ColumnsType<MarketDataMoneyMarketRow> = useMemo(
    () => [
      { title: "品种", dataIndex: "name", key: "name", width: 96 },
      { title: "指标", dataIndex: "seriesName", key: "seriesName", ellipsis: true },
      { title: "利率", dataIndex: "rateText", key: "rateText", align: "right", width: 64 },
      {
        title: "变动",
        dataIndex: "deltaText",
        key: "deltaText",
        align: "right",
        width: 66,
        render: (v: string) => (
          <span style={{ color: deltaTextColor(v), fontVariantNumeric: "tabular-nums" }}>
            {v}
          </span>
        ),
      },
      {
        title: "走势",
        key: "sparkline",
        width: 56,
        render: (_value, row) =>
          row.sparklineValues.length >= 2 ? (
            <MarketTerminalSparkline
              values={row.sparklineValues}
              tone={sparkToneFromDelta(row.deltaText)}
              variant="ticker"
            />
          ) : (
            EM_DASH
          ),
      },
      { title: "交易日", dataIndex: "tradeDate", key: "tradeDate", width: 86 },
      {
        title: "抓取",
        dataIndex: "sourceMode",
        key: "sourceMode",
        width: 58,
        render: (value: string, row) => (
          <span
            className="market-data-source-chip market-data-source-chip--mode"
            data-testid={`market-data-money-source-mode-chip-${row.key}`}
            title={value}
          >
            {compactSourceModeLabel(value)}
          </span>
        ),
      },
      {
        title: "序列",
        dataIndex: "seriesId",
        key: "seriesId",
        width: 78,
        render: (value: string, row) => (
          <span
            className="market-data-series-id-chip"
            data-testid={`market-data-money-series-chip-${row.key}`}
            title={`${row.seriesName} · ${value}`}
          >
            {value}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <section
      data-testid="market-data-money-market-table"
      className={embedded ? "market-data-terminal-embedded" : "market-data-terminal-panel"}
      style={embedded ? undefined : marketDataPanelStyle}
    >
      {!embedded ? <h2 style={marketDataBlockTitleStyle}>资金市场</h2> : null}
      <p className="market-data-terminal-source">{sourceSummary(model)}</p>
      {model.status === "ready" && dataSource.length > 0 ? (
        <>
          <Table<MarketDataMoneyMarketRow>
            size="small"
            pagination={false}
            columns={columns}
            dataSource={dataSource}
            rowKey="key"
            scroll={{ x: true }}
          />
          {highlightSeries ? (
            <div
              className="market-data-money-market-mini-chart"
              data-testid="market-data-money-market-mini-chart"
            >
              <MarketDataSeriesTimeChart series={highlightSeries} height={160} />
            </div>
          ) : null}
        </>
      ) : model.status === "ready" ? (
        <div data-testid="market-data-money-market-filter-empty" className="market-data-terminal-empty">
          当前来源筛选下无资金利率序列。
        </div>
      ) : (
        <div data-testid="market-data-money-market-empty" className="market-data-terminal-empty">
          {model.emptyReason}
        </div>
      )}
    </section>
  );
}
