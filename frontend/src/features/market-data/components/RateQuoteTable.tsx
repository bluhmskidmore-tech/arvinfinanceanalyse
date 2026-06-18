import { useEffect, useMemo, useState } from "react";
import { Segmented, Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import type {
  MarketCurveFilter,
  MarketDataRateQuoteRow,
  MarketDataRateQuoteSection,
  MarketSourceFilter,
} from "../lib/marketDataTerminalModel";
import { filterRateQuoteRows, formatTerminalSourceSummary } from "../lib/marketDataTerminalModel";
import { isMarketDataNarrowViewport } from "../lib/useMarketDataNarrowViewport";
import { MarketDataTermStructureChart } from "./MarketDataTermStructureChart";
import { MarketTerminalSparkline } from "./MarketTerminalSparkline";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type RateQuoteViewMode = "both" | "table" | "curve";

function deltaTextColor(value: string) {
  if (value.startsWith("-")) {
    return designTokens.color.semantic.up;
  }
  if (value.startsWith("+")) {
    return designTokens.color.semantic.loss;
  }
  return designTokens.color.neutral[800];
}

function sourceSummary(model: MarketDataRateQuoteSection) {
  return formatTerminalSourceSummary(model.source);
}

function readInitialViewMode(): RateQuoteViewMode {
  if (typeof window === "undefined") {
    return "both";
  }
  if (window.location.hash.includes("market-data-term-structure")) {
    return "curve";
  }
  if (isMarketDataNarrowViewport()) {
    return "table";
  }
  return "both";
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

function compactSourceLabel(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "source-pending";
  }

  const normalized = trimmed.replace(/_{2,}/g, "_");
  if (normalized.length <= 30) {
    return normalized;
  }

  const [lead] = normalized.split("_sv_");
  const prefix = lead && lead.length <= 18 ? lead : normalized.slice(0, 18);
  const suffix = normalized.slice(-7);
  return `${prefix}...${suffix}`;
}

export function RateQuoteTable({
  model,
  curveFilter = "both",
  sourceFilter = "all",
  catalogVendorNames,
  embedded = false,
}: {
  model: MarketDataRateQuoteSection;
  curveFilter?: MarketCurveFilter;
  sourceFilter?: MarketSourceFilter;
  catalogVendorNames?: ReadonlyMap<string, string>;
  embedded?: boolean;
}) {
  const [localCurve, setLocalCurve] = useState<"treasury" | "cdb">("treasury");
  const [viewMode, setViewMode] = useState<RateQuoteViewMode>(readInitialViewMode);
  const showCurveTabs = curveFilter === "both";
  const activeCurve: "treasury" | "cdb" =
    curveFilter === "both" ? localCurve : curveFilter === "cdb" ? "cdb" : "treasury";
  const dataSource = filterRateQuoteRows(model.rows, activeCurve, sourceFilter, catalogVendorNames);
  const showTable = viewMode === "both" || viewMode === "table";
  const showCurve = viewMode === "both" || viewMode === "curve";

  useEffect(() => {
    if (window.location.hash.includes("market-data-term-structure")) {
      document.getElementById("market-data-term-structure")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  const columns: ColumnsType<MarketDataRateQuoteRow> = useMemo(
    () => [
      { title: "品种", dataIndex: "variety", key: "variety", width: 54 },
      { title: "期限", dataIndex: "tenor", key: "tenor", width: 46 },
      { title: "指标", dataIndex: "seriesName", key: "seriesName", ellipsis: true },
      {
        title: "利率",
        dataIndex: "rateText",
        key: "rateText",
        align: "right",
        width: 64,
        render: (v: string) => <span style={tabularNumsStyle}>{v}</span>,
      },
      {
        title: "变动",
        dataIndex: "deltaText",
        key: "deltaText",
        align: "right",
        width: 66,
        render: (v: string) => (
          <span style={{ color: deltaTextColor(v), ...tabularNumsStyle }}>
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
            "—"
          ),
      },
      { title: "交易日", dataIndex: "tradeDate", key: "tradeDate", width: 86 },
      {
        title: "来源",
        dataIndex: "sourceVersion",
        key: "sourceVersion",
        width: 104,
        render: (value: string, row) => (
          <span
            className="market-data-source-chip"
            data-testid={`market-data-rate-source-chip-${row.key}`}
            title={value}
          >
            {compactSourceLabel(value)}
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
            data-testid={`market-data-rate-series-chip-${row.key}`}
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
      id={embedded ? undefined : "market-data-term-structure"}
      data-testid="market-data-rate-quote-table"
      className={embedded ? "market-data-terminal-embedded" : undefined}
      style={embedded ? undefined : marketDataPanelStyle}
    >
      <div className="market-data-rate-quote-head">
        {!embedded ? <h2 style={marketDataBlockTitleStyle}>利率行情</h2> : null}
        <Segmented
          size="small"
          value={viewMode}
          onChange={(value) => setViewMode(value as RateQuoteViewMode)}
          options={[
            { label: "并列", value: "both" },
            { label: "表格", value: "table" },
            { label: "曲线", value: "curve" },
          ]}
          data-testid="market-data-rate-quote-view-toggle"
        />
      </div>
      <p className="market-data-terminal-source">{sourceSummary(model)}</p>
      {showCurveTabs ? (
        <Tabs
          size="small"
          activeKey={activeCurve}
          onChange={(key) => setLocalCurve(key as "treasury" | "cdb")}
          items={[
            { key: "treasury", label: "国债" },
            { key: "cdb", label: "国开" },
          ]}
        />
      ) : (
        <div className="market-data-terminal-curve-lock" data-testid="market-data-rate-curve-lock">
          {curveFilter === "treasury" ? "国债曲线" : "国开曲线"}
        </div>
      )}
      {showTable ? (
        model.status === "ready" && dataSource.length > 0 ? (
          <Table<MarketDataRateQuoteRow>
            size="small"
            pagination={false}
            columns={columns}
            dataSource={dataSource}
            rowKey="key"
            scroll={{ x: true }}
          />
        ) : model.status === "ready" ? (
          <div data-testid="market-data-rate-quotes-filter-empty" className="market-data-terminal-empty">
            当前曲线/来源筛选下无利率序列。
          </div>
        ) : (
          <div data-testid="market-data-rate-quotes-empty" className="market-data-terminal-empty">
            {model.emptyReason}
          </div>
        )
      ) : null}
      {showCurve ? (
        <div className="market-data-rate-quote-chart-block">
          <h3 className="market-data-chart-block-title">期限结构</h3>
          <MarketDataTermStructureChart
            model={model}
            curveFilter={activeCurve}
            sourceFilter={sourceFilter}
            catalogVendorNames={catalogVendorNames}
            activeCurve={activeCurve}
          />
        </div>
      ) : null}
    </section>
  );
}
