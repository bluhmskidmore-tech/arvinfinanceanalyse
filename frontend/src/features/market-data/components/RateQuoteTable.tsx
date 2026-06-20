import { useMemo, useState } from "react";
import { Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import type {
  MarketCurveFilter,
  MarketDataRateQuoteRow,
  MarketDataRateQuoteSection,
  MarketSourceFilter,
} from "../lib/marketDataTerminalModel";
import { filterRateQuoteRows } from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

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
  if (!model.source) {
    return "来源待确认";
  }
  return `口径 ${model.source.basis} · 质量 ${model.source.qualityFlag} · 降级 ${model.source.fallbackMode} · ${model.source.sourceVersion}`;
}

export function RateQuoteTable({
  model,
  curveFilter = "both",
  sourceFilter = "all",
  catalogVendorNames,
}: {
  model: MarketDataRateQuoteSection;
  curveFilter?: MarketCurveFilter;
  sourceFilter?: MarketSourceFilter;
  catalogVendorNames?: ReadonlyMap<string, string>;
}) {
  const [localCurve, setLocalCurve] = useState<"treasury" | "cdb">("treasury");
  const showCurveTabs = curveFilter === "both";
  const activeCurve: "treasury" | "cdb" =
    curveFilter === "both" ? localCurve : curveFilter === "cdb" ? "cdb" : "treasury";
  const dataSource = filterRateQuoteRows(model.rows, activeCurve, sourceFilter, catalogVendorNames);

  const columns: ColumnsType<MarketDataRateQuoteRow> = useMemo(
    () => [
      { title: "品种", dataIndex: "variety", key: "variety", width: 64 },
      { title: "期限", dataIndex: "tenor", key: "tenor", width: 56 },
      { title: "指标", dataIndex: "seriesName", key: "seriesName", ellipsis: true },
      {
        title: "利率",
        dataIndex: "rateText",
        key: "rateText",
        align: "right",
        width: 76,
        render: (v: string) => <span style={tabularNumsStyle}>{v}</span>,
      },
      {
        title: "变动",
        dataIndex: "deltaText",
        key: "deltaText",
        align: "right",
        width: 80,
        render: (v: string) => (
          <span style={{ color: deltaTextColor(v), ...tabularNumsStyle }}>
            {v}
          </span>
        ),
      },
      { title: "交易日", dataIndex: "tradeDate", key: "tradeDate", width: 104 },
      { title: "来源", dataIndex: "sourceVersion", key: "sourceVersion", ellipsis: true },
      { title: "序列", dataIndex: "seriesId", key: "seriesId", ellipsis: true },
    ],
    [],
  );

  return (
    <section data-testid="market-data-rate-quote-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>利率行情</h2>
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
      {model.status === "ready" && dataSource.length > 0 ? (
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
      )}
    </section>
  );
}
