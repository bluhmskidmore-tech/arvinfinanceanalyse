import { useMemo, useState } from "react";
import { Table, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import type {
  MarketDataRateQuoteRow,
  MarketDataRateQuoteSection,
} from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

type CurveKind = "treasury" | "cdb";

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

export function RateQuoteTable({ model }: { model: MarketDataRateQuoteSection }) {
  const [curve, setCurve] = useState<CurveKind>("treasury");
  const dataSource = model.rows.filter((row) =>
    curve === "treasury" ? row.variety === "国债" : row.variety === "国开",
  );

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
      <Tabs
        size="small"
        activeKey={curve}
        onChange={(k) => setCurve(k as CurveKind)}
        items={[
          { key: "treasury", label: "国债" },
          { key: "cdb", label: "国开" },
        ]}
      />
      {model.status === "ready" && dataSource.length > 0 ? (
        <Table<MarketDataRateQuoteRow>
          size="small"
          pagination={false}
          columns={columns}
          dataSource={dataSource}
          rowKey="key"
          scroll={{ x: true }}
        />
      ) : (
        <div data-testid="market-data-rate-quotes-empty" className="market-data-terminal-empty">
          {model.emptyReason}
        </div>
      )}
    </section>
  );
}
