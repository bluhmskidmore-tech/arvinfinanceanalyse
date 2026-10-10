import { Link } from "react-router-dom";

import type { StockAnalysisWorkbenchPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import {
  pretradeQualificationReasonLabel,
  stockSupplyQualityLabel,
  stockStatusLabel,
  stockSupplyVendorLabel,
} from "../lib/stockAnalysisPageCopy";
import type {
  StockMarketStateCard,
  StockSectorRow,
} from "../lib/stockAnalysisPageModel";
import styles from "./StockAnalysisQualificationState.module.css";

export type StockAnalysisQualificationStateProps = {
  workbench: StockAnalysisWorkbenchPayload;
  researchReviewReady: boolean;
  researchDateAligned: boolean;
  reviewQueueCount: number;
  marketState: StockMarketStateCard | null;
  marketAsOf: string | null;
  sectorRows: StockSectorRow[];
  sectorAsOf: string | null;
  onRetry: () => void;
  isRetrying: boolean;
};

function displayValue(value: string | null | undefined): string {
  const normalized = value?.trim();
  return normalized ? normalized : EM_DASH;
}

function compactValue(value: string | null | undefined, maxLength = 24): string {
  const display = displayValue(value);
  return display.length > maxLength ? `${display.slice(0, maxLength - 1)}…` : display;
}

function labeledMetadata(
  value: string | null | undefined,
  labeler: (raw: string | null | undefined) => string,
): string {
  const normalized = value?.trim();
  return normalized ? `${labeler(normalized)}（${normalized}）` : EM_DASH;
}

function SectorObservationTable({ rows }: { rows: StockSectorRow[] }) {
  return (
    <div className={styles.sectorTableWrap}>
      <table className={styles.sectorTable}>
        <thead>
          <tr>
            <th scope="col">排名</th>
            <th scope="col">行业</th>
            <th scope="col">涨跌幅</th>
            <th scope="col">成分数</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.sectorCode}>
              <td>#{row.rank}</td>
              <td>{row.sectorName}</td>
              <td>{row.pctChange}</td>
              <td>{row.constituentCount ?? EM_DASH}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StockAnalysisQualificationState({
  workbench,
  researchReviewReady,
  researchDateAligned,
  reviewQueueCount,
  marketState,
  marketAsOf,
  sectorRows,
  sectorAsOf,
  onRetry,
  isRetrying,
}: StockAnalysisQualificationStateProps) {
  const qualification = workbench.pretrade_qualification ?? null;
  const status = qualification?.status ?? "unavailable";
  const isReady = status === "ready";
  const isReadyEmpty = status === "ready_empty";
  const reasonLabel = pretradeQualificationReasonLabel(qualification?.reason);
  const targetDate = displayValue(qualification?.target_date);

  const marketDateMismatch = Boolean(
    marketAsOf && workbench.as_of_date && marketAsOf !== workbench.as_of_date,
  );
  const marketUnavailableReason = !workbench.as_of_date
    ? "工作台未返回实际数据日，无法确认市场门控观察属于同一日期。"
    : marketDateMismatch
      ? `市场观察日期 ${marketAsOf} 与工作台实际数据日 ${workbench.as_of_date} 不一致，当前不展示跨日市场信息。`
      : !marketAsOf
        ? "市场门控未返回实际日期，无法确认与当前工作台同日。"
        : !marketState
          ? "市场门控观察未返回，当前没有可展示内容。"
          : null;
  const sectorDateMismatch = Boolean(
    sectorAsOf && workbench.as_of_date && sectorAsOf !== workbench.as_of_date,
  );
  const sectorUnavailableReason = !workbench.as_of_date
    ? "工作台未返回实际数据日，无法确认行业快照属于同一日期。"
    : sectorDateMismatch
      ? `行业快照日期 ${sectorAsOf} 与工作台实际数据日 ${workbench.as_of_date} 不一致，当前不展示跨日行业行。`
      : !sectorAsOf
        ? "行业快照未返回实际日期，无法确认与当前工作台同日。"
        : sectorRows.length === 0
          ? `行业快照在 ${sectorAsOf} 未返回可展示记录。`
          : null;

  return (
    <section
      role="status"
      aria-label="盘前来源资格"
      data-testid="stock-analysis-pretrade-qualification-boundary"
      className={`moss-page-v2-data-status ${styles.qualificationStrip}`}
    >
      <div className={styles.statusLine}>
        <span
          className="stock-analysis-page__compact-status-chip"
          data-tone={isReady ? "positive" : isReadyEmpty ? "neutral" : "warning"}
        >
          {researchReviewReady && !isReady
            ? "当日研究数据可用；盘前资格尚未闭合"
            : isReady
            ? "来源资格已闭合"
            : isReadyEmpty
              ? "来源资格已闭合，本次无候选"
              : "来源资格未就绪"}
        </span>
        <span className="stock-analysis-page__compact-status-chip" data-tone="neutral">
          {researchReviewReady && !isReady
            ? `权威研究候选 ${reviewQueueCount} 个；${reasonLabel}，风险与执行结论保持关闭。`
            : !researchDateAligned && workbench.decision_summary.can_review_candidates
              ? `工作台实际日 ${displayValue(workbench.as_of_date)} 与研究主包日期未对齐，不展示跨日候选或详情。`
              : isReady
            ? "候选仅供复核，策略门禁仍独立生效"
            : isReadyEmpty
              ? `观察日 ${targetDate}，权威候选数为 0，不回填旧候选。`
              : `${reasonLabel}；权威研究候选数为 ${reviewQueueCount}，研究投影未闭合。`}
        </span>
      </div>

      {!isReady ? (
        <>
          <div className={styles.compactBoundaryRow}>
            <dl className={styles.metadataGrid} aria-label="观察日与供数状态">
              <div>
                <dt>请求日</dt>
                <dd>{workbench.requested_as_of_date?.trim() || "未指定"}</dd>
              </div>
              <div>
                <dt>实际日</dt>
                <dd>{displayValue(workbench.as_of_date)}</dd>
              </div>
              <div>
                <dt>回退日</dt>
                <dd>{displayValue(workbench.fallback_date)}</dd>
              </div>
              <div>
                <dt>资格目标日</dt>
                <dd>{targetDate}</dd>
              </div>
              <div>
                <dt>来源版本</dt>
                <dd title={displayValue(workbench.data_status.source_version)}>
                  {compactValue(workbench.data_status.source_version)}
                </dd>
              </div>
              <div>
                <dt>回退方式</dt>
                <dd>{displayValue(workbench.data_status.fallback_mode)}</dd>
              </div>
            </dl>
            <div className={styles.actions}>
              <button
                type="button"
                onClick={onRetry}
                disabled={isRetrying}
                aria-busy={isRetrying}
                data-testid="stock-analysis-qualification-retry"
              >
                重新检查
              </button>
              <Link to="/reports">数据状态</Link>
            </div>
          </div>

          <details className={styles.details}>
            <summary>来源与同日观察</summary>
            <section
              className={styles.observations}
              data-testid="stock-analysis-available-observations"
              aria-labelledby="stock-analysis-available-observations-title"
            >
              <header className={styles.observationsHeader}>
                <h3 id="stock-analysis-available-observations-title">仍可查看的同日观察</h3>
                <p>市场与行业信息仅在实际数据日一致时显示。</p>
              </header>
              <div className={styles.observationGrid}>
            <section className={styles.observationPanel} aria-labelledby="stock-analysis-market-observation-title">
              <header className={styles.observationPanelHeader}>
                <div>
                  <h4 id="stock-analysis-market-observation-title">市场门控观察</h4>
                  <span>实际日期 {displayValue(marketAsOf)}，仅供观察</span>
                </div>
              </header>
              {marketUnavailableReason ? (
                <p className={styles.emptyObservation}>{marketUnavailableReason}</p>
              ) : marketState ? (
                <>
                  <dl className={styles.observationSummary}>
                    <div>
                      <dt>市场状态</dt>
                      <dd>{marketState.state}</dd>
                    </div>
                    <div>
                      <dt>条件通过</dt>
                      <dd>{marketState.passedLabel}</dd>
                    </div>
                  </dl>
                  {marketState.conditions.length > 0 ? (
                    <ul className={styles.conditionList}>
                      {marketState.conditions.map((condition) => (
                        <li key={condition.key}>
                          <div>
                            <strong>{condition.label}</strong>
                            <span data-status={condition.status}>
                              {stockStatusLabel(condition.status)}
                            </span>
                          </div>
                          <p>{condition.evidence || EM_DASH}</p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className={styles.emptyObservation}>市场门控未返回条件明细。</p>
                  )}
                  {marketState.warnings.length > 0 ? (
                    <details className={styles.observationWarnings}>
                      <summary>市场观察说明（{marketState.warnings.length}）</summary>
                      <ul>
                        {marketState.warnings.map((warning, index) => (
                          <li key={`${index}-${warning}`}>{warning}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </>
              ) : (
                <p className={styles.emptyObservation}>市场门控观察未返回，当前没有可展示内容。</p>
              )}
            </section>

            <section className={styles.observationPanel} aria-labelledby="stock-analysis-sector-observation-title">
              <header className={styles.observationPanelHeader}>
                <div>
                  <h4 id="stock-analysis-sector-observation-title">行业快照观察</h4>
                  <span>实际日期 {displayValue(sectorAsOf)}，仅供观察</span>
                </div>
              </header>
              {sectorUnavailableReason ? (
                <p className={styles.emptyObservation}>{sectorUnavailableReason}</p>
              ) : (
                <>
                  <SectorObservationTable rows={sectorRows.slice(0, 10)} />
                  {sectorRows.length > 10 ? (
                    <details className={styles.details}>
                      <summary>查看其余 {sectorRows.length - 10} 个行业</summary>
                      <SectorObservationTable rows={sectorRows.slice(10)} />
                    </details>
                  ) : null}
                </>
              )}
            </section>
              </div>
              <dl className={styles.sourceDetails}>
                <div><dt>资格状态</dt><dd>{status}</dd></div>
                <div><dt>实际原因</dt><dd>{displayValue(qualification?.reason)}</dd></div>
                <div><dt>数据陈旧</dt><dd>{typeof workbench.stale === "boolean" ? (workbench.stale ? "是" : "否") : EM_DASH}</dd></div>
                <div><dt>质量</dt><dd>{labeledMetadata(workbench.data_status.quality_flag, stockSupplyQualityLabel)}</dd></div>
                <div><dt>供数</dt><dd>{labeledMetadata(workbench.data_status.vendor_status, stockSupplyVendorLabel)}</dd></div>
                <div>
                  <dt>来源版本</dt>
                  <dd className={styles.sourceVersionDetail}>
                    {displayValue(workbench.data_status.source_version)}
                  </dd>
                </div>
                <div><dt>规则版本</dt><dd>{displayValue(workbench.data_status.rule_version)}</dd></div>
              </dl>
            </section>
          </details>
        </>
      ) : null}
    </section>
  );
}
