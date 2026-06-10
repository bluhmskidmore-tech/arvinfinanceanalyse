import { useMemo, useState } from "react";
import { Collapse, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { PageSectionLead } from "../../../components/page/PagePrimitives";
import type { FxFormalStatusPayload, FxFormalStatusRow, ResultMeta } from "../../../api/contracts";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { LiveResultMetaStrip } from "./LiveResultMetaStrip";
import { buildFxFormalStatusCollapseLabel } from "../pages/marketDataPageModel";

type MarketDataFxFormalSectionProps = {
  payload: FxFormalStatusPayload | null | undefined;
  meta: ResultMeta | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

function formatMidRate(value: number | null) {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(4);
}

export function MarketDataFxFormalSection({
  payload,
  meta,
  isLoading,
  isError,
  onRetry,
}: MarketDataFxFormalSectionProps) {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const expanded = activeKeys.includes("fx-formal");

  const columns: ColumnsType<FxFormalStatusRow> = useMemo(
    () => [
      { title: "货币对", dataIndex: "pair_label", key: "pair_label", width: 96 },
      { title: "中间价", dataIndex: "mid_rate", key: "mid_rate", align: "right", width: 88,
        render: (value: number | null) => (
          <span style={tabularNumsStyle}>{formatMidRate(value)}</span>
        ),
      },
      { title: "交易日", dataIndex: "trade_date", key: "trade_date", width: 104 },
      { title: "观测日", dataIndex: "observed_trade_date", key: "observed_trade_date", width: 104 },
      {
        title: "沿用",
        dataIndex: "is_carry_forward",
        key: "is_carry_forward",
        width: 56,
        render: (value: boolean | null) => (value ? "是" : "否"),
      },
      { title: "供应商", dataIndex: "vendor_name", key: "vendor_name", width: 72 },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 72,
        render: (value: FxFormalStatusRow["status"]) => (value === "missing" ? "缺失" : "就绪"),
      },
    ],
    [],
  );

  return (
    <section className="market-data-section-block" data-testid="market-data-fx-formal-section">
      <PageSectionLead
        eyebrow="正式外汇"
        title="中间价物化状态"
        description="来自 GET /ui/market-data/fx/formal-status；仅展示后端返回的 formal 行，不与分析口径外汇观察混用。"
      />
      <Collapse
        className="market-data-fx-formal-collapse"
        data-testid="market-data-fx-formal-collapse"
        bordered={false}
        activeKey={activeKeys}
        onChange={(keys) => {
          const nextKeys = Array.isArray(keys) ? keys : [keys];
          setActiveKeys(nextKeys);
        }}
        items={[
          {
            key: "fx-formal",
            label: buildFxFormalStatusCollapseLabel({ payload, isLoading, isError }),
            children: expanded ? (
              <div data-testid="market-data-fx-formal-panel" className="market-data-fx-formal-panel">
                <AsyncSection
                  title="正式外汇中间价"
                  isLoading={isLoading}
                  isError={isError}
                  isEmpty={!isLoading && !isError && (payload?.rows.length ?? 0) === 0}
                  onRetry={() => void onRetry()}
                >
                  {!isLoading && !isError && meta ? (
                    <LiveResultMetaStrip
                      lead="本区块·正式外汇"
                      meta={meta}
                      testId="market-data-fx-formal-meta"
                    />
                  ) : null}
                  <Table<FxFormalStatusRow>
                    data-testid="market-data-fx-formal-table"
                    size="small"
                    pagination={false}
                    rowKey={(row) => row.series_id}
                    columns={columns}
                    dataSource={payload?.rows ?? []}
                  />
                </AsyncSection>
              </div>
            ) : null,
          },
        ]}
      />
    </section>
  );
}
