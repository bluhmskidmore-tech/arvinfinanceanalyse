import {
  DatabaseOutlined,
  FireOutlined,
  LineChartOutlined,
} from "@ant-design/icons";
import {
  StockAnalysisAccordion as Accordion,
  StockAnalysisAccordionItem as AccordionItem,
} from "./StockAnalysisAccordion";

import type { LivermoreUnsupportedOutput } from "../../../api/contracts";
import type { StockRiskExitRow } from "../lib/stockAnalysisPageModel";
import {
  SA_CARD_TITLE,
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
            {!row.entryCostAvailable ? (
              <p
                className="stock-analysis-page__rail-risk-flag"
                data-testid={`stock-risk-row-${row.stockCode}-cost-missing`}
              >
                成本价缺失
              </p>
            ) : null}
            <div className="stock-analysis-page__rail-risk-meta">
              <span className="stock-analysis-page__tabular">收 {row.latestClose}</span>
              <span className="stock-analysis-page__tabular">距 {row.distanceToExitPct}</span>
              <span className="stock-analysis-page__tabular">线 {row.exitWatchPrice}</span>
            </div>
            <Accordion
              className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
            >
              <AccordionItem
                key={`${row.stockCode}-risk-reason`}
                aria-label="供数原因"
                title="供数原因"
              >
                <div className="stock-analysis-page__collapse-detail">
                  <p>{row.reason}</p>
                  <p className="stock-analysis-page__collapse-detail--muted">退出观察价 {row.exitWatchPrice}</p>
                </div>
              </AccordionItem>
            </Accordion>
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
  const blockedSummary = unsupportedOutput ? riskExitBlockedSummary(unsupportedOutput.reason) : null;

  return (
    <section data-testid="stock-analysis-risk-section">
      <div className={SA_SECTION_HEAD}>
        <div className="stock-analysis-page__min-w-0">
          <h2 className={SA_CARD_TITLE}>风险退出观察</h2>
          <p className={SA_SECTION_DESC}>
            {blockedSummary ? `风险退出不可用 · ${blockedSummary}` : `${riskTriggeredCount} 触发 · ${riskWatchCount} 观察`}
          </p>
        </div>
      </div>
      <div
        className="stock-analysis-page__rail-risk-strip"
        aria-label="风险退出统计"
        data-testid="stock-analysis-risk-strip"
      >
        {blockedSummary ? (
          <div data-tone="negative">
            <DatabaseOutlined aria-hidden="true" />
            <span>风险退出</span>
            <strong>阻断 · {blockedSummary}</strong>
          </div>
        ) : (
          <>
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
            <div data-tone="positive">
              <DatabaseOutlined aria-hidden="true" />
              <span>供数</span>
              <strong>接通</strong>
            </div>
          </>
        )}
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
              <strong>风险退出不可用</strong>
              <p>{blockedSummary}</p>
            </span>
          </div>
          {unsupportedOutput.reason ? (
            <Accordion
              className="stock-analysis-page__candidate-collapse stock-analysis-page__rail-collapse"
            >
              <AccordionItem
                key="risk-exit-unsupported-reason"
                aria-label="供数原因"
                title="供数原因"
              >
                <p className="stock-analysis-page__collapse-detail stock-analysis-page__collapse-detail--compact">
                  {riskExitBlockedDetail(unsupportedOutput.reason, unsupportedOutput.key)}
                </p>
              </AccordionItem>
            </Accordion>
          ) : null}
        </div>
      ) : null}
      <StockAnalysisRiskExitRows
        rows={unsupportedOutput ? [] : rows}
        unsupported={Boolean(unsupportedOutput)}
        onOpenRiskDetail={onOpenRiskDetail}
      />
    </section>
  );
}
