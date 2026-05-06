import { useMemo } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { designTokens } from "../../../theme/designSystem";
import type {
  MarketDataMoneyMarketRow,
  MarketDataMoneyMarketSection,
} from "../lib/marketDataTerminalModel";
import { marketDataBlockTitleStyle, marketDataPanelStyle } from "./marketDataPanelStyle";

function deltaTextColor(value: string) {
  if (value.startsWith("-")) {
    return designTokens.color.semantic.profit;
  }
  if (value.startsWith("+")) {
    return designTokens.color.semantic.loss;
  }
  return designTokens.color.neutral[700];
}

function sourceSummary(model: MarketDataMoneyMarketSection) {
  if (!model.source) {
    return "来源待确认";
  }
  return `口径 ${model.source.basis} · 质量 ${model.source.qualityFlag} · 降级 ${model.source.fallbackMode} · ${model.source.sourceVersion}`;
}

export function MoneyMarketTable({ model }: { model: MarketDataMoneyMarketSection }) {
  const columns: ColumnsType<MarketDataMoneyMarketRow> = useMemo(
    () => [
      { title: "品种", dataIndex: "name", key: "name", width: 128 },
      { title: "指标", dataIndex: "seriesName", key: "seriesName", ellipsis: true },
      { title: "利率", dataIndex: "rateText", key: "rateText", align: "right", width: 80 },
      {
        title: "变动",
        dataIndex: "deltaText",
        key: "deltaText",
        align: "right",
        width: 88,
        render: (v: string) => (
          <span style={{ color: deltaTextColor(v), fontVariantNumeric: "tabular-nums" }}>
            {v}
          </span>
        ),
      },
      { title: "交易日", dataIndex: "tradeDate", key: "tradeDate", width: 104 },
      { title: "抓取", dataIndex: "sourceMode", key: "sourceMode", width: 72 },
      { title: "序列", dataIndex: "seriesId", key: "seriesId", ellipsis: true },
    ],
    [],
  );

  return (
    <section data-testid="market-data-money-market-table" style={marketDataPanelStyle}>
      <h2 style={marketDataBlockTitleStyle}>资金市场</h2>
      <p className="market-data-terminal-source">{sourceSummary(model)}</p>
      {model.status === "ready" ? (
        <Table<MarketDataMoneyMarketRow>
          size="small"
          pagination={false}
          columns={columns}
          dataSource={model.rows}
          rowKey="key"
          scroll={{ x: true }}
        />
      ) : (
        <div data-testid="market-data-money-market-empty" className="market-data-terminal-empty">
          {model.emptyReason}
        </div>
      )}
    </section>
  );
}
