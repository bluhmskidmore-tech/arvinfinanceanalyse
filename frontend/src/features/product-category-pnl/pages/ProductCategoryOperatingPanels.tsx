import { type ReactNode, useEffect, useState } from "react";

import {
  selectProductCategoryManagementMonitoringSurface,
  selectProductCategoryOperatingActionBacktestSurface,
  selectProductCategoryOperatingAnalysisSurface,
} from "./productCategoryPnlPageModel";
import { EM_DASH } from "../../../utils/format";

type ProductCategoryManagementMonitoringSurface = ReturnType<
  typeof selectProductCategoryManagementMonitoringSurface
>;

export function ProductCategoryManagementMonitoring(props: {
  surface: ProductCategoryManagementMonitoringSurface;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const { surface } = props;
  const monitoring =
    surface.state === "ready" &&
    surface.tpl &&
    surface.liability &&
    surface.derivatives &&
    surface.runRate
      ? {
          tpl: surface.tpl,
          liability: surface.liability,
          derivatives: surface.derivatives,
          runRate: surface.runRate,
        }
      : null;
  return (
    <section
      id="product-category-management-monitor"
      className="product-category-management-monitor"
      data-testid="product-category-management-monitor"
      aria-labelledby="product-category-management-monitor-title"
    >
      <div className="product-category-management-monitor__header">
        <div>
          <span className="product-category-management-monitor__eyebrow">
            候选管理视图
          </span>
          <h3 id="product-category-management-monitor-title">经营修复监控</h3>
          <p>
            把 1—6
            月正式数据压缩为恢复阈值、改善质量、稳定性和经营节奏；不新增正式指标。
          </p>
        </div>
        <span
          className="product-category-management-monitor__status"
          title={surface.metricStatus.disclaimer}
        >
          <strong>{surface.metricStatus.label}</strong>
          <small>{surface.coverageLabel}</small>
        </span>
      </div>

      {surface.state === "scenario_blocked" && !monitoring ? (
        <div
          className="product-category-management-monitor__empty"
          role="status"
        >
          {surface.emptyCopy}
        </div>
      ) : props.isError && !monitoring ? (
        <div
          className="product-category-management-monitor__empty product-category-management-monitor__empty--error"
          role="alert"
        >
          <span>经营修复监控加载失败，未将失败月份解释为数据缺失。</span>
          <button type="button" onClick={props.onRetry}>
            重试经营监控
          </button>
        </div>
      ) : props.isLoading && !monitoring ? (
        <div
          className="product-category-management-monitor__empty"
          role="status"
        >
          正在加载 1—6 月正式月度数据与归因证据。
        </div>
      ) : !monitoring ? (
        <div
          className="product-category-management-monitor__empty"
          role="status"
        >
          {surface.emptyCopy}
        </div>
      ) : (
        <>
          <div
            className="product-category-management-monitor__summary"
            aria-label="经营修复监控摘要"
          >
            <div>
              <span>TPL 本期净营收</span>
              <strong>{monitoring.tpl.currentPnlLabel}</strong>
              <small>收益率 {monitoring.tpl.currentYieldLabel}</small>
            </div>
            <div>
              <span>负债 H1 净贡献</span>
              <strong>{monitoring.liability.h1NetLabel}</strong>
              <small>负拖累抵消 {monitoring.liability.offsetRatioLabel}</small>
            </div>
            <div>
              <span>衍生品 H1 净营收</span>
              <strong>{monitoring.derivatives.h1TotalLabel}</strong>
              <small>
                Top3 月份 {monitoring.derivatives.topThreeConcentrationLabel}
              </small>
            </div>
            <div>
              <span>Q2 月均净营收</span>
              <strong>{monitoring.runRate.q2MonthlyAverageLabel}</strong>
              <small>
                回到 H1 月均需 {monitoring.runRate.recoveryLiftLabel}
              </small>
            </div>
          </div>

          <div className="product-category-management-monitor__body">
            <article className="product-category-management-monitor__tpl">
              <div className="product-category-management-monitor__subhead">
                <div>
                  <h4>TPL 恢复阈值</h4>
                  <p>
                    固定 6 月规模 {monitoring.tpl.currentScaleLabel} 亿元、FTP
                    与归因天数，静态反推收益率。
                  </p>
                </div>
                <span>{surface.periodLabel}</span>
              </div>
              <div className="product-category-management-monitor__table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>管理情景</th>
                      <th>目标净营收（亿元）</th>
                      <th>所需收益率</th>
                      <th>较本期提升</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monitoring.tpl.thresholds.map((threshold) => (
                      <tr key={threshold.key}>
                        <td>{threshold.label}</td>
                        <td>{threshold.targetPnlLabel}</td>
                        <td>{threshold.requiredYieldLabel}</td>
                        <td>{threshold.liftBpLabel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>

            <section
              className="product-category-management-monitor__signals"
              aria-labelledby="product-category-management-monitor-signals-title"
            >
              <div className="product-category-management-monitor__signals-title">
                <h4 id="product-category-management-monitor-signals-title">
                  风险与节奏信号
                </h4>
                <span>负债、衍生品、经营节奏</span>
              </div>
              <article>
                <div className="product-category-management-monitor__signal-head">
                  <h4>负债改善质量</h4>
                  <b className="is-negative">
                    6 月 {monitoring.liability.currentMonthDeltaLabel}
                  </b>
                </div>
                <p>
                  H1 正贡献 {monitoring.liability.positivePoolLabel}{" "}
                  亿元，负拖累 {monitoring.liability.negativePoolLabel} 亿元，
                  抵消比例 {monitoring.liability.offsetRatioLabel}。
                </p>
                <small>
                  主要回落：{monitoring.liability.leadingMovementLabel}；主导{" "}
                  {monitoring.liability.leadingDriverLabel}
                </small>
              </article>
              <article>
                <div className="product-category-management-monitor__signal-head">
                  <h4>衍生品稳定性代理</h4>
                  <b className="is-warning">
                    Top3 {monitoring.derivatives.topThreeConcentrationLabel}
                  </b>
                </div>
                <p>
                  月均 {monitoring.derivatives.monthlyAverageLabel}{" "}
                  亿元，月度波动 {monitoring.derivatives.volatilityLabel} 亿元，
                  负值月份 {monitoring.derivatives.negativeMonthCountLabel}。
                </p>
                <small>
                  集中度仅反映月份分布，不识别一次性收益或交易级驱动。
                </small>
              </article>
              <article>
                <div className="product-category-management-monitor__signal-head">
                  <h4>经营节奏</h4>
                  <b className="is-negative">
                    差额 {monitoring.runRate.gapToH1Label}
                  </b>
                </div>
                <p>
                  Q1 月均 {monitoring.runRate.q1MonthlyAverageLabel} 亿元，H1
                  月均 {monitoring.runRate.h1MonthlyAverageLabel} 亿元； 若按 Q2
                  月均静态延展，H2 为 {monitoring.runRate.h2AtQ2PaceLabel}{" "}
                  亿元。
                </p>
                <small>静态节奏不等同于预测，也不接入预算或计财目标。</small>
              </article>
            </section>
          </div>
        </>
      )}

      {monitoring ? (
        <details className="product-category-management-monitor__methods">
          <summary>
            <span>方法与证据边界</span>
            <small>查看 {surface.methodNotes.length} 条口径说明</small>
          </summary>
          <ul>
            {surface.methodNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

type ProductCategoryOperatingAnalysisSurface = ReturnType<
  typeof selectProductCategoryOperatingAnalysisSurface
>;

type ProductCategoryOperatingActionBacktestSurface = ReturnType<
  typeof selectProductCategoryOperatingActionBacktestSurface
>;

type ProductCategoryOperatingActionQueueRow =
  ProductCategoryOperatingAnalysisSurface["actionQueue"]["rows"][number];

function productCategoryOperatingActionRowKey(
  row: ProductCategoryOperatingActionQueueRow,
) {
  return `${row.priorityLabel}-${row.categoryId}`;
}

export function ProductCategoryOperatingAnalysisPanel(props: {
  surface: ProductCategoryOperatingAnalysisSurface;
  candidateNotice?: ReactNode;
}) {
  const [selectedActionRowKey, setSelectedActionRowKey] = useState<
    string | null
  >(null);
  const selectedActionRow =
    props.surface.actionQueue.rows.find(
      (row) =>
        productCategoryOperatingActionRowKey(row) === selectedActionRowKey,
    ) ?? null;
  const quadrantGroups = [
    "core_profit_pool",
    "selective_growth",
    "scale_efficiency_watch",
    "shrink_or_reprice",
  ] as const;
  useEffect(() => {
    if (selectedActionRowKey && !selectedActionRow) {
      setSelectedActionRowKey(null);
    }
  }, [selectedActionRow, selectedActionRowKey]);

  return (
    <section
      className="product-category-operating-analysis"
      data-testid="product-category-operating-analysis"
    >
      <div className="product-category-operating-analysis__header">
        <div>
          <span className="product-category-operating-analysis__eyebrow">
            经营分析
          </span>
          <h2 className="product-category-operating-analysis__title">
            产品类别利润结构与经营动作
          </h2>
          <p className="product-category-operating-analysis__description">
            基于当前正式表和已有月环比归因，优先识别利润池、压力项、主要变动驱动和可优化产品。
          </p>
        </div>
        <span className="product-category-operating-analysis__badge">
          全表净营收 {props.surface.contribution.grandTotalLabel ?? EM_DASH} 亿元
        </span>
      </div>
      {props.candidateNotice}
      <div className="product-category-operating-analysis__grid">
        <article
          className="product-category-operating-analysis__panel"
          data-testid="product-category-operating-profit-rank"
        >
          <h3 className="product-category-operating-analysis__panel-title">
            利润贡献排行
          </h3>
          <p className="product-category-operating-analysis__panel-note">
            按当前净营收排序，贡献率相对全表净营收计算。
          </p>
          {props.surface.contribution.emptyCopy ? (
            <div className="product-category-operating-analysis__empty">
              {props.surface.contribution.emptyCopy}
            </div>
          ) : (
            <div className="product-category-operating-analysis__rank-groups">
              <ProductCategoryOperatingContributionList
                label="利润池"
                rows={props.surface.contribution.profitRows}
              />
              <ProductCategoryOperatingContributionList
                label="压力项"
                rows={props.surface.contribution.pressureRows}
              />
            </div>
          )}
        </article>
        <article
          className="product-category-operating-analysis__panel"
          data-testid="product-category-operating-movement"
        >
          <h3 className="product-category-operating-analysis__panel-title">
            月环比变动驱动
          </h3>
          <p className="product-category-operating-analysis__panel-note">
            直接复用正式经营差异归因，按变动绝对值排序。
          </p>
          {props.surface.movement.emptyCopy ? (
            <div className="product-category-operating-analysis__empty">
              {props.surface.movement.emptyCopy}
            </div>
          ) : (
            <div className="product-category-operating-analysis__movement-list">
              {props.surface.movement.rows.map((row) => (
                <div
                  className="product-category-operating-analysis__movement-row"
                  key={row.categoryId}
                >
                  <div>
                    <strong>{row.categoryLabel}</strong>
                    <span>
                      {row.leadingDriverLabel} {row.leadingDriverValueLabel}
                    </span>
                  </div>
                  <b className={row.delta > 0 ? "is-positive" : "is-negative"}>
                    {row.deltaLabel}
                  </b>
                </div>
              ))}
            </div>
          )}
        </article>
      </div>
      <article
        className="product-category-operating-analysis__panel product-category-operating-analysis__panel--wide"
        data-testid="product-category-operating-quadrant"
      >
        <div className="product-category-operating-analysis__quadrant-header">
          <div>
            <h3 className="product-category-operating-analysis__panel-title">
              规模-收益率象限
            </h3>
            <p className="product-category-operating-analysis__panel-note">
              以可用产品的中位数为基准：规模{" "}
              {props.surface.quadrant.scaleBenchmarkLabel} 亿元，收益率{" "}
              {props.surface.quadrant.yieldBenchmarkLabel}%。
            </p>
          </div>
        </div>
        {props.surface.quadrant.emptyCopy ? (
          <div className="product-category-operating-analysis__empty">
            {props.surface.quadrant.emptyCopy}
          </div>
        ) : (
          <div className="product-category-operating-analysis__quadrant-grid">
            {quadrantGroups.map((quadrant) => {
              const rows = props.surface.quadrant.rows.filter(
                (row) => row.quadrant === quadrant,
              );
              if (rows.length === 0) {
                return null;
              }
              return (
                <section
                  className={`product-category-operating-analysis__quadrant is-${quadrant}`}
                  key={quadrant}
                >
                  <h4>{rows[0]?.quadrantLabel}</h4>
                  <div className="product-category-operating-analysis__quadrant-items">
                    {rows.map((row) => (
                      <div
                        className="product-category-operating-analysis__quadrant-item"
                        key={row.categoryId}
                      >
                        <strong>{row.categoryLabel}</strong>
                        <span>
                          {row.scaleLabel} 亿元 · {row.yieldLabel}% · 净营收{" "}
                          {row.netIncomeLabel}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </article>
      <article
        className="product-category-operating-analysis__panel product-category-operating-analysis__panel--wide"
        data-testid="product-category-operating-action-queue"
      >
        <div className="product-category-operating-analysis__quadrant-header">
          <div>
            <h3 className="product-category-operating-analysis__panel-title">
              动作优先级队列
            </h3>
            <p className="product-category-operating-analysis__panel-note">
              从盈利、规模、收益率和正式归因中抽取需要进入经营闭环的产品类别。
            </p>
          </div>
        </div>
        {props.surface.actionQueue.emptyCopy ? (
          <div className="product-category-operating-analysis__empty">
            {props.surface.actionQueue.emptyCopy}
          </div>
        ) : (
          <div className="product-category-operating-analysis__action-list">
            {props.surface.actionQueue.rows.map((row) => {
              const rowKey = productCategoryOperatingActionRowKey(row);
              return (
                <div
                  className="product-category-operating-analysis__action-row"
                  key={rowKey}
                >
                  <div className="product-category-operating-analysis__action-main">
                    <span className="product-category-operating-analysis__action-priority">
                      {row.priorityLabel}
                    </span>
                    <div>
                      <strong>{row.categoryLabel}</strong>
                      <span>
                        {row.actionLabel} · {row.triggerLabel}
                      </span>
                    </div>
                  </div>
                  <b className={`is-${row.tone}`}>{row.primaryMetricLabel}</b>
                  <button
                    aria-expanded={selectedActionRowKey === rowKey}
                    type="button"
                    className="product-category-operating-analysis__action-detail-button"
                    onClick={() => setSelectedActionRowKey(rowKey)}
                  >
                    查看 {row.categoryLabel} 动作详情
                  </button>
                  <div className="product-category-operating-analysis__action-evidence">
                    {row.evidenceItems.map((item) => (
                      <small key={item}>{item}</small>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {selectedActionRow ? (
          <aside
            className="product-category-operating-analysis__action-drawer"
            data-testid="product-category-operating-action-drawer"
          >
            <div className="product-category-operating-analysis__action-drawer-head">
              <div>
                <span>动作闭环详情</span>
                <h4>{selectedActionRow.categoryLabel}</h4>
              </div>
              <button
                type="button"
                onClick={() => setSelectedActionRowKey(null)}
              >
                关闭动作详情
              </button>
            </div>
            <div className="product-category-operating-analysis__action-drawer-body">
              <p>
                {selectedActionRow.actionLabel} ·{" "}
                {selectedActionRow.triggerLabel}
              </p>
              <p>核对正式表净营收、规模、收益率与归因变动。</p>
              <div className="product-category-operating-analysis__action-drawer-evidence">
                {selectedActionRow.evidenceItems.map((item) => (
                  <small key={item}>{item}</small>
                ))}
              </div>
            </div>
          </aside>
        ) : null}
      </article>
    </section>
  );
}

export function ProductCategoryOperatingActionBacktestPanel(props: {
  surface: ProductCategoryOperatingActionBacktestSurface;
  isHistoryLoaded: boolean;
  historyLoading: boolean;
  candidateNotice?: ReactNode;
}) {
  return (
    <section
      className="product-category-action-backtest"
      data-testid="product-category-operating-action-backtest"
    >
      <div className="product-category-action-backtest__header">
        <div>
          <span className="product-category-operating-analysis__eyebrow">
            信号回测
          </span>
          <h2 className="product-category-action-backtest__title">
            动作队列次月命中率
          </h2>
          <p className="product-category-action-backtest__description">
            用历史月度正式 payload
            复放动作队列，观察下一期净营收、收益率和规模是否沿建议方向改善。
          </p>
        </div>
        <span className="product-category-action-backtest__badge">
          待观察 {props.surface.summary.latestPendingCount} 条
        </span>
      </div>
      {props.candidateNotice}
      {!props.isHistoryLoaded ? (
        <div className="product-category-action-backtest__empty">
          选择报表日期后，可用历史月度快照回测动作信号。
        </div>
      ) : props.historyLoading ? (
        <div className="product-category-action-backtest__empty">
          正在加载历史月度快照。
        </div>
      ) : props.surface.emptyCopy ? (
        <div className="product-category-action-backtest__empty">
          {props.surface.emptyCopy}
        </div>
      ) : (
        <>
          <div className="product-category-action-backtest__summary">
            <div className="product-category-action-backtest__metric">
              <span>覆盖月份</span>
              <strong>{props.surface.summary.evaluatedMonthCount}</strong>
              <small>{props.surface.summary.coverageLabel}</small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>可评价信号</span>
              <strong>{props.surface.summary.signalCount}</strong>
              <small>{props.surface.summary.evidenceLabel}</small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>归因覆盖</span>
              <strong>{props.surface.summary.attributionCoverageLabel}</strong>
              <small>
                {props.surface.summary.attributionCoverageDetailLabel}
              </small>
            </div>
            <div
              className={`product-category-action-backtest__metric is-${props.surface.summary.backtestGateTone}`}
            >
              <span>回测闸口</span>
              <strong>{props.surface.summary.backtestGateLabel}</strong>
              <small>{props.surface.summary.backtestGateDetailLabel}</small>
            </div>
            <div
              className={`product-category-action-backtest__metric is-${props.surface.summary.backtestGateTone}`}
            >
              <span>补样本任务</span>
              <strong>{props.surface.summary.sampleRepairLabel}</strong>
              <small>
                {props.surface.summary.sampleRepairDetailLabel} ·{" "}
                {props.surface.summary.sampleRepairDateLabel} ·{" "}
                {props.surface.summary.sampleRepairReviewLabel}
              </small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>复核工作量</span>
              <strong>{props.surface.summary.reviewWorkloadLabel}</strong>
              <small>{props.surface.summary.reviewWorkloadDetailLabel}</small>
            </div>
            <div className="product-category-action-backtest__metric">
              <span>规则处置</span>
              <strong>{props.surface.summary.dispositionLabel}</strong>
              <small>{props.surface.summary.dispositionDetailLabel}</small>
            </div>
            {props.surface.actionRows.map((row) => (
              <div
                className={`product-category-action-backtest__metric is-${row.tone}`}
                key={row.actionKind}
              >
                <span>{row.actionLabel}</span>
                <strong>{row.hitRateLabel}</strong>
                <small>
                  {row.signalCount} 条 · {row.evidenceLabel}
                </small>
              </div>
            ))}
          </div>
          <article className="product-category-action-backtest__coverage">
            <h3>样本覆盖</h3>
            <div className="product-category-action-backtest__coverage-list">
              {props.surface.coverageRows.slice(-6).map((row) => (
                <div
                  className={`product-category-action-backtest__coverage-row is-${row.tone}`}
                  key={`${row.reportDate}-${row.nextReportDate ?? "pending"}`}
                >
                  <span>
                    {row.reportDate}
                    {row.nextReportDate ? ` → ${row.nextReportDate}` : ""}
                  </span>
                  <strong>{row.statusLabel}</strong>
                  <small>
                    {row.signalCount} 条信号 · {row.detailLabel}
                  </small>
                </div>
              ))}
            </div>
          </article>
          {props.surface.missReasonRows.length > 0 ? (
            <article className="product-category-action-backtest__panel product-category-action-backtest__miss-panel">
              <h3>未命中诊断</h3>
              <div className="product-category-action-backtest__miss-list">
                {props.surface.missReasonRows.map((row) => (
                  <div
                    className={`product-category-action-backtest__miss-row is-${row.tone}`}
                    key={row.actionKind}
                  >
                    <div>
                      <strong>{row.actionLabel}</strong>
                      <span>
                        未命中 {row.missCount}/{row.comparableCount} · 主因{" "}
                        {row.primaryReasonLabel}
                      </span>
                    </div>
                    <b>{row.missRateLabel}</b>
                    <small>
                      {row.reasonRows
                        .map(
                          (reason) =>
                            `${reason.reasonLabel} ${reason.sampleShareLabel}`,
                        )
                        .join(" · ")}
                    </small>
                  </div>
                ))}
              </div>
            </article>
          ) : null}
          {props.surface.calibrationRows.length > 0 ? (
            <article className="product-category-action-backtest__panel product-category-action-backtest__miss-panel">
              <h3>回测校准建议</h3>
              <div className="product-category-action-backtest__miss-list">
                {props.surface.calibrationRows.map((row) => (
                  <div
                    className={`product-category-action-backtest__miss-row is-${row.tone}`}
                    key={row.actionKind}
                  >
                    <div>
                      <strong>{row.actionLabel}</strong>
                      <span>{row.reasonLabel}</span>
                    </div>
                    <b>{row.recommendationLabel}</b>
                    <small>
                      {row.confidenceLabel} · {row.confidenceDetailLabel} ·{" "}
                      {row.evidenceLabel}
                    </small>
                  </div>
                ))}
              </div>
            </article>
          ) : null}
          {props.surface.latestReviewRows.length > 0 ? (
            <article className="product-category-action-backtest__panel product-category-action-backtest__miss-panel">
              <h3>最新信号校准复核</h3>
              <div className="product-category-action-backtest__miss-list">
                {props.surface.latestReviewRows.map((row) => (
                  <div
                    className={`product-category-action-backtest__miss-row is-${row.tone}`}
                    key={`${row.priorityLabel}-${row.categoryId}-${row.actionKind}`}
                  >
                    <div>
                      <strong>{row.categoryLabel}</strong>
                      <span>
                        {row.actionLabel} · {row.reasonLabel}
                      </span>
                    </div>
                    <b>
                      {row.reviewLabel} · {row.riskRankLabel}
                    </b>
                    <small>
                      {row.riskReasonLabel} · {row.impactLabel} ·{" "}
                      {row.evidenceLabel}
                    </small>
                    <small>
                      当前证据：{row.currentEvidenceItems.join(" · ")}
                    </small>
                    <small>{row.watchReportDateLabel}</small>
                    <small>{row.observationLabel}</small>
                    <small>{row.gapLabel}</small>
                    <small>{row.releaseConditionLabel}</small>
                    <small>{row.checkItems.join(" · ")}</small>
                  </div>
                ))}
              </div>
            </article>
          ) : null}
          <div className="product-category-action-backtest__grid">
            <article className="product-category-action-backtest__panel">
              <h3>动作类型表现</h3>
              <div className="product-category-action-backtest__table-wrap">
                <table className="product-category-action-backtest__table">
                  <thead>
                    <tr>
                      <th>动作</th>
                      <th>信号</th>
                      <th>命中率</th>
                      <th>净营收变化</th>
                      <th>收益率变化</th>
                      <th>规模变化</th>
                    </tr>
                  </thead>
                  <tbody>
                    {props.surface.actionRows.map((row) => (
                      <tr key={row.actionKind}>
                        <td>{row.actionLabel}</td>
                        <td>{row.signalCount}</td>
                        <td>{row.hitRateLabel}</td>
                        <td>{row.averageNetIncomeDeltaLabel}</td>
                        <td>{row.averageYieldDeltaBpLabel}</td>
                        <td>{row.averageScaleDeltaLabel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
            <article className="product-category-action-backtest__panel">
              <h3>典型样本</h3>
              <div className="product-category-action-backtest__examples">
                {props.surface.examples.map((example) => (
                  <div
                    className={`product-category-action-backtest__example is-${example.tone}`}
                    key={`${example.reportDate}-${example.categoryId}-${example.actionKind}`}
                  >
                    <div>
                      <strong>{example.categoryLabel}</strong>
                      <span>
                        {example.reportDate} → {example.nextReportDate} ·{" "}
                        {example.actionLabel}
                      </span>
                    </div>
                    <b>{example.outcomeLabel}</b>
                    <small>
                      净营收 {example.netIncomeDeltaLabel} 亿元 · 收益率{" "}
                      {example.yieldDeltaBpLabel} · 规模{" "}
                      {example.scaleDeltaLabel} 亿元
                    </small>
                  </div>
                ))}
              </div>
            </article>
          </div>
        </>
      )}
    </section>
  );
}

function ProductCategoryOperatingContributionList(props: {
  label: string;
  rows: ProductCategoryOperatingAnalysisSurface["contribution"]["profitRows"];
}) {
  if (props.rows.length === 0) {
    return null;
  }
  return (
    <div className="product-category-operating-analysis__rank-group">
      <span className="product-category-operating-analysis__rank-label">
        {props.label}
      </span>
      {props.rows.map((row) => (
        <div
          className="product-category-operating-analysis__rank-row"
          key={row.categoryId}
        >
          <div>
            <strong>{row.categoryLabel}</strong>
            <span>
              {row.sideLabel} · {row.contributionLabel}
            </span>
          </div>
          <b
            className={row.tone === "positive" ? "is-positive" : "is-negative"}
          >
            {row.netIncomeLabel}
          </b>
        </div>
      ))}
    </div>
  );
}
