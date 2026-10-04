import { useMemo, useState } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { PageAsyncSection } from "../../../components/page/PageAsyncSection";
import { SkeletonBarStack } from "../../../components/SkeletonBars";
import type { FxFormalStatusPayload, FxFormalStatusRow, ResultMeta } from "../../../api/contracts";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { buildFxFormalStatusCollapseLabel } from "../pages/marketDataPageModel";

/** 简表行数上界：按后端返回顺序取前 N 行，不自定重要性排序（2026-08-27 IA 裁决 #6）。 */
const FX_FORMAL_SUMMARY_ROW_LIMIT = 5;

type MarketDataFxFormalSectionProps = {
  payload: FxFormalStatusPayload | null | undefined;
  meta: ResultMeta | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
};

function formatMidRate(value: number | null) {
  if (value == null || Number.isNaN(value)) {
    return EM_DASH;
  }
  return value.toFixed(4);
}

function renderStatusBadge(status: FxFormalStatusRow["status"]) {
  return status === "missing" ? (
    <span className="market-data-fx-formal-status market-data-fx-formal-status--missing">
      缺失
    </span>
  ) : (
    <span className="market-data-fx-formal-status">就绪</span>
  );
}

export function MarketDataFxFormalSection({
  payload,
  meta,
  isLoading,
  isError,
  onRetry,
}: MarketDataFxFormalSectionProps) {
  // 明细面板首开挂载：摘要简表常驻，重表格（全列 antd Table）在首次展开后才进 DOM。
  const [detailMounted, setDetailMounted] = useState(false);

  const rows = payload?.rows ?? [];
  // 只消费 formal payload；缺行缺值显式空态，绝不以 FX analytical 序列回填。
  const summaryRows = rows.slice(0, FX_FORMAL_SUMMARY_ROW_LIMIT);
  const formalUseBlocked = meta?.formal_use_allowed === false;

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
        render: (value: FxFormalStatusRow["status"]) => renderStatusBadge(value),
      },
    ],
    [],
  );

  return (
    <section className="market-data-section-block" data-testid="market-data-fx-formal-section">
      <header className="market-data-fx-formal-head">
        <span className="market-data-fx-formal-label">
          <span className="market-data-fx-formal-label__badge">正式口径</span>
          {buildFxFormalStatusCollapseLabel({ payload, isLoading, isError })}
          {formalUseBlocked ? (
            <span
              className="market-data-fx-formal-status market-data-fx-formal-status--missing"
              data-testid="market-data-fx-formal-blocked"
            >
              暂不可正式使用
            </span>
          ) : null}
        </span>
      </header>
      <div className="market-data-fx-formal-body">
        <section
          className="market-data-formal-rate-panel market-data-fx-formal-summary"
          data-testid="market-data-fx-formal-summary-table"
        >
          {isLoading ? (
            <SkeletonBarStack className="moss-skeleton-bar-stack--spaced" />
          ) : isError ? (
            <div className="market-data-terminal-empty">
              数据载入失败。
              <button
                type="button"
                className="market-data-fx-formal-retry"
                onClick={() => void onRetry()}
              >
                重试
              </button>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>货币对</th>
                  <th>中间价</th>
                  <th>交易日</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {summaryRows.length > 0 ? (
                  summaryRows.map((row) => (
                    <tr key={row.series_id}>
                      <td>
                        <strong>{row.pair_label}</strong>
                      </td>
                      <td>{formatMidRate(row.mid_rate)}</td>
                      <td>{row.trade_date ?? EM_DASH}</td>
                      <td>{renderStatusBadge(row.status)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4}>
                      <div
                        className="market-data-terminal-empty"
                        data-testid="market-data-fx-formal-summary-empty"
                      >
                        正式外汇中间价暂无已落地行；缺失即缺失，不以外汇分析口径回填。
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </section>
        <details
          className="market-data-tushare-details market-data-fx-formal-details"
          data-testid="market-data-fx-formal-collapse"
          onToggle={(event) => {
            if (event.currentTarget.open) {
              setDetailMounted(true);
            }
          }}
        >
          <summary data-testid="market-data-fx-formal-details-summary">展开完整明细</summary>
          {detailMounted ? (
            <div data-testid="market-data-fx-formal-panel" className="market-data-fx-formal-panel">
              <PageAsyncSection
                title="正式外汇中间价"
                isLoading={isLoading}
                isError={isError}
                isEmpty={!isLoading && !isError && rows.length === 0}
                onRetry={() => void onRetry()}
              >
                <div data-testid="market-data-fx-formal-table">
                  <Table<FxFormalStatusRow>
                    size="small"
                    pagination={false}
                    rowKey={(row) => row.series_id}
                    columns={columns}
                    dataSource={rows}
                  />
                </div>
              </PageAsyncSection>
            </div>
          ) : null}
        </details>
      </div>
    </section>
  );
}
