import {
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
} from "@ant-design/icons";
import { Collapse } from "antd";

import type { LivermoreUnsupportedOutput } from "../../../api/contracts";
import type { StockRiskExitRow } from "../lib/stockAnalysisPageModel";
import {
  SA_CARD_TITLE,
  SA_FIRST_CARD,
  SA_SECTION_DESC,
  SA_SECTION_HEAD,
} from "../lib/stockAnalysisPageChrome";
import {
  riskExitBlockedDetail,
  riskExitBlockedSummary,
  riskStatusLabel,
  toneTextClass,
} from "../lib/stockAnalysisPageCopy";

export function StockAnalysisRiskExitRows({
  rows,
  unsupported,
  onOpenRiskDetail,
}: {
  rows: StockRiskExitRow[];
  unsupported: boolean;
  onOpenRiskDetail: (row: StockRiskExitRow) => void;
}) {
  if (rows.length === 0) {
    return (
      <p className="stock-analysis-page__rail-empty">
        {unsupported ? "持仓快照待补" : "风险 0"}
      </p>
    );
  }

  return (
    <div className="stock-analysis-page__rail-risk-list">
      {rows.slice(0, 5).map((row) => {
        const tone = row.status === "triggered" ? "negative" : "warning";
        const openRiskDetail = () => onOpenRiskDetail(row);

        return (
          <div
            className="stock-analysis-page__rail-risk-row"
            data-testid={`stock-risk-row-${row.stockCode}`}
            data-tone={tone}
            key={`${row.stockCode}:${row.status}:${row.reason}`}
            role="button"
            tabIndex={0}
            onClick={openRiskDetail}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openRiskDetail();
              }
            }}
          >
            <div className="stock-analysis-page__rail-risk-main">
              <span>
                <strong>{row.stockName}</strong>
                <small title={row.stockCode}>{row.stockCode}</small>
              </span>
              <em className={toneTextClass(tone)}>
                {riskStatusLabel(row.status)}
              </em>
            </div>
            <div className="stock-analysis-page__rail-risk-meta">
              <span className="stock-analysis-page__tabular">收 {row.latestClose}</span>
              <span className="stock-analysis-page__tabular">距 {row.distanceToExitPct}</span>
              <span className="stock-analysis-page__tabular">线 {row.exitWatchPrice}</span>
            </div>
            <Collapse
              ghost
              bordered={false}
              destroyOnHidden
              className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
              items={[
                {
                  key: `${row.stockCode}-risk-reason`,
                  label: "供数原因",
                  children: (
                    <div className="stock-analysis-page__collapse-detail">
                      <p>{row.reason}</p>
                      <p className="stock-analysis-page__collapse-detail--muted">退出观察价 {row.exitWatchPrice}</p>
                    </div>
                  ),
                },
              ]}
            />
          </div>
        );
      })}
    </div>
  );
}

export function StockAnalysisRiskExitSection({
  rows,
  riskTriggeredCount,
  riskWatchCount,
  confluenceError,
  unsupportedOutput,
  onOpenRiskDetail,
}: {
  rows: StockRiskExitRow[];
  riskTriggeredCount: number;
  riskWatchCount: number;
  confluenceError: boolean;
  unsupportedOutput?: LivermoreUnsupportedOutput | null;
  onOpenRiskDetail: (row: StockRiskExitRow) => void;
}) {
  return (
    <section className={SA_FIRST_CARD} data-testid="stock-analysis-risk-section">
      <div className={SA_SECTION_HEAD}>
        <div className="stock-analysis-page__min-w-0">
          <h2 className={SA_CARD_TITLE}>风险退出观察</h2>
          <p className={SA_SECTION_DESC}>
            {riskTriggeredCount} 触发 · {riskWatchCount} 观察
          </p>
        </div>
      </div>
      <div
        className="stock-analysis-page__rail-risk-strip"
        aria-label="风险退出统计"
        data-testid="stock-analysis-risk-strip"
      >
        <div data-tone={riskTriggeredCount > 0 ? "negative" : "positive"}>
          <FireOutlined aria-hidden="true" />
          <span>触发</span>
          <strong>{riskTriggeredCount}</strong>
        </div>
        <div data-tone={riskWatchCount > 0 ? "warning" : "positive"}>
          <LineChartOutlined aria-hidden="true" />
          <span>观察</span>
          <strong>{riskWatchCount}</strong>
        </div>
        <div data-tone={unsupportedOutput ? "warning" : "positive"}>
          <DatabaseOutlined aria-hidden="true" />
          <span>供数</span>
          <strong>{unsupportedOutput ? "待补" : "接通"}</strong>
        </div>
      </div>
      {confluenceError ? (
        <p className="stock-analysis-page__rail-error-copy">联动观察暂不可用。</p>
      ) : null}
      {unsupportedOutput ? (
        <div className="stock-analysis-page__rail-warning">
          <div className="stock-analysis-page__rail-warning-head">
            <span aria-hidden="true">
              <DatabaseOutlined />
            </span>
            <span>
              <strong>风险退出待补</strong>
              <p>{riskExitBlockedSummary(unsupportedOutput.reason)}</p>
            </span>
          </div>
          {unsupportedOutput.reason ? (
            <Collapse
              ghost
              bordered={false}
              destroyOnHidden
              className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
              items={[
                {
                  key: "risk-exit-unsupported-reason",
                  label: "供数原因",
                  children: (
                    <p className="stock-analysis-page__collapse-detail stock-analysis-page__collapse-detail--compact">
                      {riskExitBlockedDetail(unsupportedOutput.reason, unsupportedOutput.key)}
                    </p>
                  ),
                },
              ]}
            />
          ) : null}
        </div>
      ) : null}
      <StockAnalysisRiskExitRows
        rows={rows}
        unsupported={Boolean(unsupportedOutput)}
        onOpenRiskDetail={onOpenRiskDetail}
      />
    </section>
  );
}
