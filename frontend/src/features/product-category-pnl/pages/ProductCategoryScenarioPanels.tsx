import { type ReactNode, useState } from "react";

import { PageStateSurface } from "../../../components/page/PagePrimitives";
import { EM_DASH } from "../../../utils/format";
import {
  type ProductCategoryDecisionFocusSurface,
  type ProductCategoryScenarioExplanation,
  type ProductCategoryScenarioSensitivitySurface,
} from "./productCategoryPnlPageModel";

export type ScenarioReviewActionStatus = "pending" | "confirmed" | "issue";
export type ScenarioReviewIssueReason =
  "basis" | "ftp" | "attribution" | "data";
type ScenarioComparisonFilter = "all" | "pressure" | "improvement";
export type ScenarioActionClosureStatus =
  "todo" | "reviewing" | "closed" | "issue";

const SCENARIO_REVIEW_ACTION_STATUS_OPTIONS: ReadonlyArray<
  readonly [ScenarioReviewActionStatus, string]
> = [
  ["pending", "待核对"],
  ["confirmed", "已确认"],
  ["issue", "有差异"],
];

const SCENARIO_REVIEW_ISSUE_REASON_OPTIONS: ReadonlyArray<
  readonly [ScenarioReviewIssueReason, string]
> = [
  ["basis", "口径不一致"],
  ["ftp", "FTP 驱动异常"],
  ["attribution", "正式归因未覆盖"],
  ["data", "数据待复核"],
];

const SCENARIO_COMPARISON_FILTER_OPTIONS: ReadonlyArray<
  readonly [ScenarioComparisonFilter, string]
> = [
  ["all", "全部"],
  ["pressure", "仅承压"],
  ["improvement", "仅改善"],
];

const SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS: ReadonlyArray<
  readonly [ScenarioActionClosureStatus, string]
> = [
  ["todo", "待处理"],
  ["reviewing", "复核中"],
  ["closed", "已关闭"],
  ["issue", "有差异"],
];

export function ProductCategoryScenarioExplanationCard(props: {
  explanation: ProductCategoryScenarioExplanation;
  actionStatuses: Record<string, ScenarioReviewActionStatus>;
  issueReasons: Record<string, ScenarioReviewIssueReason>;
  onSetActionStatus: (
    categoryId: string,
    actionIndex: number,
    status: ScenarioReviewActionStatus,
  ) => void;
  onSetIssueReason: (
    categoryId: string,
    actionIndex: number,
    reason: ScenarioReviewIssueReason,
  ) => void;
  onBulkActionStatus: (
    categoryId: string,
    actionCount: number,
    status: ScenarioReviewActionStatus,
  ) => void;
  onResetActions: (categoryId: string, actionCount: number) => void;
}) {
  const explanation = props.explanation;
  const actionStatusEntries = explanation.reviewActionItems.map((_, index) => {
    const key = `${explanation.categoryId}:${index}`;
    return props.actionStatuses[key] ?? "pending";
  });
  const pendingCount = actionStatusEntries.filter(
    (status) => status === "pending",
  ).length;
  const confirmedCount = actionStatusEntries.filter(
    (status) => status === "confirmed",
  ).length;
  const issueCount = actionStatusEntries.filter(
    (status) => status === "issue",
  ).length;
  const selectedIssueReasonEntries = explanation.reviewActionItems
    .map((_, index) => props.issueReasons[`${explanation.categoryId}:${index}`])
    .filter((reason): reason is ScenarioReviewIssueReason => Boolean(reason));
  const selectedIssueReasonLabels = SCENARIO_REVIEW_ISSUE_REASON_OPTIONS.filter(
    ([reason]) => selectedIssueReasonEntries.includes(reason),
  ).map(([, label]) => label);
  const conclusionLabel =
    issueCount > 0
      ? `复核结论：${explanation.categoryLabel}仍有 ${issueCount} 项差异，需补充原因和证据后归档。`
      : pendingCount > 0
        ? `复核结论：${explanation.categoryLabel}还有 ${pendingCount} 项待核对，暂不建议归档。`
        : `复核结论：${explanation.categoryLabel}动作已全部确认，可进入留痕归档。`;

  return (
    <div
      className="product-category-financial-analysis__explanation"
      data-testid="product-category-scenario-explanation"
    >
      <div className="product-category-financial-analysis__scenario-kicker">
        复核解释包
      </div>
      <strong>{explanation.categoryLabel}</strong>
      <p>{explanation.summaryLabel}</p>
      <div className="product-category-financial-analysis__bridge">
        <span className="product-category-financial-analysis__scenario-kicker">
          口径桥
        </span>
        <b className={`is-${explanation.bridgeTone}`}>
          {explanation.bridgeLabel}
        </b>
        <small>{explanation.bridgeConclusionLabel}</small>
      </div>
      <div className="product-category-financial-analysis__review-actions">
        <span className="product-category-financial-analysis__scenario-kicker">
          复核动作
        </span>
        {explanation.reviewActionItems.map((item, index) => {
          const categoryId = explanation.categoryId;
          const actionStatusKey = `${categoryId}:${index}`;
          const currentStatus =
            props.actionStatuses[actionStatusKey] ?? "pending";
          const currentReason = props.issueReasons[actionStatusKey];
          return (
            <div
              className="product-category-financial-analysis__review-action-item"
              key={actionStatusKey}
            >
              <small>{item}</small>
              <div className="product-category-financial-analysis__review-status-group">
                {SCENARIO_REVIEW_ACTION_STATUS_OPTIONS.map(
                  ([status, label]) => (
                    <button
                      aria-pressed={currentStatus === status}
                      className={`product-category-financial-analysis__review-status-button is-${status}`}
                      key={status}
                      onClick={() =>
                        props.onSetActionStatus(categoryId, index, status)
                      }
                      type="button"
                    >
                      {label}
                    </button>
                  ),
                )}
              </div>
              {currentStatus === "issue" ? (
                <div className="product-category-financial-analysis__reason-group">
                  {SCENARIO_REVIEW_ISSUE_REASON_OPTIONS.map(
                    ([reason, label]) => (
                      <button
                        aria-pressed={currentReason === reason}
                        className="product-category-financial-analysis__reason-button"
                        key={reason}
                        onClick={() =>
                          props.onSetIssueReason(categoryId, index, reason)
                        }
                        type="button"
                      >
                        {label}
                      </button>
                    ),
                  )}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      <div className="product-category-financial-analysis__review-console">
        <div className="product-category-financial-analysis__review-console-head">
          <span className="product-category-financial-analysis__scenario-kicker">
            复核结论台
          </span>
          <div className="product-category-financial-analysis__review-console-actions">
            <button
              onClick={() =>
                props.onBulkActionStatus(
                  explanation.categoryId,
                  explanation.reviewActionItems.length,
                  "confirmed",
                )
              }
              type="button"
            >
              全部确认
            </button>
            <button
              onClick={() =>
                props.onResetActions(
                  explanation.categoryId,
                  explanation.reviewActionItems.length,
                )
              }
              type="button"
            >
              重置复核
            </button>
          </div>
        </div>
        <div className="product-category-financial-analysis__review-totals">
          <b>待核对 {pendingCount}</b>
          <b>已确认 {confirmedCount}</b>
          <b>有差异 {issueCount}</b>
        </div>
        <strong>{conclusionLabel}</strong>
        <small>
          差异原因：
          {selectedIssueReasonLabels.length > 0
            ? selectedIssueReasonLabels.join("、")
            : "未选择"}
        </small>
        <div className="product-category-financial-analysis__review-memo">
          <span>复核备忘</span>
          <p>
            当前产品：{explanation.categoryLabel}；情景：
            {explanation.triggerRateLabel}；差额：
            {explanation.scenarioDeltaLabel}；状态：待核对 {pendingCount}
            、已确认 {confirmedCount}、有差异 {issueCount}。
          </p>
        </div>
      </div>
      <div className="product-category-financial-analysis__explanation-grid">
        <span>{explanation.sideLabel}</span>
        <span>基线 {explanation.baselineNetIncomeLabel}</span>
        <span>
          {explanation.triggerRateLabel} {explanation.scenarioNetIncomeLabel}
        </span>
        <span>{explanation.scenarioDeltaLabel}</span>
      </div>
      {explanation.driverRows.length === 0 ? (
        <small>
          {explanation.emptyCopy ?? "当前正式归因未返回可排序的驱动项。"}
        </small>
      ) : (
        <div className="product-category-financial-analysis__driver-list">
          <span>正式归因</span>
          {explanation.driverRows.map((row) => (
            <b className={`is-${row.tone}`} key={row.key}>
              {row.label} {row.valueLabel}
            </b>
          ))}
        </div>
      )}
    </div>
  );
}

export function ProductCategoryScenarioComparisonPanel(props: {
  rows: ProductCategoryScenarioSensitivitySurface["comparisonRows"];
  filter: ScenarioComparisonFilter;
  selectedCategoryId: string | null;
  onFilterChange: (filter: ScenarioComparisonFilter) => void;
  onSelectCategory: (categoryId: string) => void;
}) {
  const visibleRows = props.rows.filter((row) => {
    if (props.filter === "pressure") {
      return row.worstDelta !== null && row.worstDelta < 0;
    }
    if (props.filter === "improvement") {
      return row.bestDelta !== null && row.bestDelta > 0;
    }
    return true;
  });
  const rateColumns = props.rows[0]?.cells ?? [];

  return (
    <div
      className="product-category-financial-analysis__comparison"
      data-testid="product-category-scenario-comparison"
    >
      <div className="product-category-financial-analysis__comparison-head">
        <div>
          <div className="product-category-financial-analysis__scenario-kicker">
            多情景对比
          </div>
          <p>横向比较各产品行在不同 FTP 情景下的净营收和较基线差额。</p>
        </div>
        <div className="product-category-financial-analysis__comparison-filters">
          {SCENARIO_COMPARISON_FILTER_OPTIONS.map(([filter, label]) => (
            <button
              aria-pressed={props.filter === filter}
              key={filter}
              onClick={() => props.onFilterChange(filter)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {visibleRows.length === 0 ? (
        <div className="product-category-financial-analysis__empty">
          当前筛选下暂无可比较产品行。
        </div>
      ) : (
        <div className="product-category-financial-analysis__comparison-table-wrap">
          <table className="product-category-financial-analysis__comparison-table">
            <thead>
              <tr>
                <th>产品</th>
                <th>侧别</th>
                <th>基线</th>
                {rateColumns.map((cell) => (
                  <th key={cell.rate}>{cell.rateLabel}</th>
                ))}
                <th>最差情景</th>
                <th>区间</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <tr
                  className={
                    props.selectedCategoryId === row.categoryId
                      ? "is-selected"
                      : undefined
                  }
                  key={row.categoryId}
                >
                  <td>
                    <button
                      className="product-category-financial-analysis__comparison-row-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        props.onSelectCategory(row.categoryId);
                      }}
                      type="button"
                    >
                      {row.categoryLabel} 多情景对比
                    </button>
                  </td>
                  <td>{row.sideLabel}</td>
                  <td>{row.baselineNetIncomeLabel}</td>
                  {row.cells.map((cell) => (
                    <td className={`is-${cell.tone}`} key={cell.rate}>
                      {cell.netIncomeLabel} / {cell.deltaLabel}
                    </td>
                  ))}
                  <td className={`is-${row.tone}`}>
                    {row.worstRateLabel} / {row.worstDeltaLabel}
                  </td>
                  <td>{row.rangeLabel}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function ProductCategoryScenarioActionClosurePanel(props: {
  rows: ProductCategoryScenarioSensitivitySurface["actionClosureRows"];
  statuses: Record<string, ScenarioActionClosureStatus>;
  memoCategoryId: string | null;
  onSetStatus: (
    categoryId: string,
    status: ScenarioActionClosureStatus,
  ) => void;
  onSelectMemo: (categoryId: string) => void;
}) {
  const statusCounts = SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS.map(
    ([status, label]) => ({
      status,
      label,
      count: props.rows.filter(
        (row) => (props.statuses[row.categoryId] ?? "todo") === status,
      ).length,
    }),
  );
  const memoRow = props.memoCategoryId
    ? (props.rows.find((row) => row.categoryId === props.memoCategoryId) ??
      null)
    : null;
  const memoStatusLabel = memoRow
    ? (SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS.find(
        ([status]) => status === (props.statuses[memoRow.categoryId] ?? "todo"),
      )?.[1] ?? "待处理")
    : "待处理";

  return (
    <div
      className="product-category-financial-analysis__closure"
      data-testid="product-category-scenario-action-closure"
    >
      <div className="product-category-financial-analysis__closure-head">
        <div>
          <div className="product-category-financial-analysis__scenario-kicker">
            情景动作闭环
          </div>
          <h4>本期经营动作清单</h4>
          <p>自动挑出承压产品，给出建议动作、复核证据和当前处理状态。</p>
        </div>
        <div className="product-category-financial-analysis__closure-totals">
          {statusCounts.map((item) => (
            <b key={item.status}>
              {item.label} {item.count}
            </b>
          ))}
        </div>
      </div>
      {props.rows.length === 0 ? (
        <div className="product-category-financial-analysis__empty">
          当前情景暂无需要闭环的承压动作。
        </div>
      ) : (
        <>
          <div className="product-category-financial-analysis__closure-list">
            {props.rows.map((row) => {
              const currentStatus = props.statuses[row.categoryId] ?? "todo";
              return (
                <article
                  className="product-category-financial-analysis__closure-card"
                  key={row.categoryId}
                >
                  <div className="product-category-financial-analysis__closure-card-head">
                    <span>{row.priorityLabel}</span>
                    <strong>{row.categoryLabel}</strong>
                    <b className={`is-${row.tone}`}>{row.exposureLabel}</b>
                  </div>
                  <p>
                    {row.sideLabel} · {row.triggerRateLabel} 情景净营收{" "}
                    {row.scenarioNetIncomeLabel} 亿元
                  </p>
                  <div className="product-category-financial-analysis__closure-action">
                    <span>建议动作</span>
                    <b>{row.recommendationLabel}</b>
                  </div>
                  <div className="product-category-financial-analysis__closure-evidence">
                    {row.evidenceItems.map((item) => (
                      <small key={item}>{item}</small>
                    ))}
                  </div>
                  <div className="product-category-financial-analysis__closure-status">
                    {SCENARIO_ACTION_CLOSURE_STATUS_OPTIONS.map(
                      ([status, label]) => (
                        <button
                          aria-pressed={currentStatus === status}
                          key={status}
                          onClick={() =>
                            props.onSetStatus(row.categoryId, status)
                          }
                          type="button"
                        >
                          {label}
                        </button>
                      ),
                    )}
                  </div>
                  <button
                    className="product-category-financial-analysis__closure-memo-button"
                    onClick={() => props.onSelectMemo(row.categoryId)}
                    type="button"
                  >
                    生成复核备忘
                  </button>
                </article>
              );
            })}
          </div>
          {memoRow ? (
            <div
              className="product-category-financial-analysis__closure-memo"
              data-testid="product-category-scenario-action-memo"
            >
              <span>复核备忘</span>
              <p>
                {memoRow.memoLabel} 状态：{memoStatusLabel}。
              </p>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

export function ProductCategoryFinancialAnalysisPanel(props: {
  scenarioSensitivity: ProductCategoryScenarioSensitivitySurface;
  scenarioExplanation: ProductCategoryScenarioExplanation | null;
  selectedScenarioReviewCategoryId: string | null;
  scenarioReviewActionStatuses: Record<string, ScenarioReviewActionStatus>;
  scenarioReviewIssueReasons: Record<string, ScenarioReviewIssueReason>;
  scenarioActionClosureStatuses: Record<string, ScenarioActionClosureStatus>;
  scenarioActionClosureMemoCategoryId: string | null;
  scenarioSensitivityRequested: boolean;
  scenarioSensitivityLoading: boolean;
  scenarioSensitivityError: boolean;
  candidateNotice?: ReactNode;
  onLoadScenarioSensitivity: () => void;
  onSelectScenarioReview: (categoryId: string) => void;
  onSetScenarioReviewActionStatus: (
    categoryId: string,
    actionIndex: number,
    status: ScenarioReviewActionStatus,
  ) => void;
  onSetScenarioReviewIssueReason: (
    categoryId: string,
    actionIndex: number,
    reason: ScenarioReviewIssueReason,
  ) => void;
  onBulkScenarioReviewActionStatus: (
    categoryId: string,
    actionCount: number,
    status: ScenarioReviewActionStatus,
  ) => void;
  onResetScenarioReviewActions: (
    categoryId: string,
    actionCount: number,
  ) => void;
  onSetScenarioActionClosureStatus: (
    categoryId: string,
    status: ScenarioActionClosureStatus,
  ) => void;
  onSelectScenarioActionClosureMemo: (categoryId: string) => void;
  decisionFocus: ProductCategoryDecisionFocusSurface;
}) {
  const scenarioExplanation = props.scenarioExplanation;
  const [scenarioComparisonFilter, setScenarioComparisonFilter] =
    useState<ScenarioComparisonFilter>("all");

  return (
    <section
      className="product-category-financial-analysis"
      data-testid="product-category-financial-analysis"
    >
      <div className="product-category-financial-analysis__header">
        <div>
          <span className="product-category-operating-analysis__eyebrow">
            财务分析增强
          </span>
          <h2 className="product-category-operating-analysis__title">
            情景弹性与决策焦点
          </h2>
          <p className="product-category-operating-analysis__description">
            保留正式表为主口径；这里只把后端情景结果和当前产品表现整理成候选财务观察。
          </p>
        </div>
        <span className="product-category-operating-analysis__badge">
          基线总净营收{" "}
          {props.scenarioSensitivity.baselineGrandTotalLabel ?? EM_DASH} 亿元
        </span>
      </div>
      {props.candidateNotice}
      <div className="product-category-financial-analysis__grid">
        <article
          className="product-category-financial-analysis__panel product-category-financial-analysis__panel--scenario"
          data-testid="product-category-scenario-sensitivity"
        >
          <div className="product-category-financial-analysis__panel-head">
            <div>
              <h3 className="product-category-financial-analysis__title">
                FTP 情景敏感度
              </h3>
              <p className="product-category-financial-analysis__note">
                四档情景均来自后端 scenario
                payload，本地仅展示与正式基线的差额。
              </p>
            </div>
            <button
              type="button"
              className="product-category-financial-analysis__load-button"
              onClick={props.onLoadScenarioSensitivity}
              disabled={props.scenarioSensitivityLoading}
            >
              {props.scenarioSensitivityRequested ? "刷新矩阵" : "加载矩阵"}
            </button>
          </div>
          {props.scenarioSensitivityError ? (
            <PageStateSurface
              variant="error"
              testId="product-category-scenario-sensitivity-state"
              title="情景敏感度加载失败"
              description="四档 FTP 情景查询未返回结果，请重试加载矩阵。"
              actions={
                <button type="button" onClick={props.onLoadScenarioSensitivity}>
                  重试加载矩阵
                </button>
              }
            />
          ) : props.scenarioSensitivityLoading ? (
            <PageStateSurface
              variant="loading"
              testId="product-category-scenario-sensitivity-state"
              title="情景敏感度加载中"
              description="正在获取四档 FTP 情景结果。"
            />
          ) : props.scenarioSensitivity.emptyCopy ? (
            <PageStateSurface
              variant="empty"
              testId="product-category-scenario-sensitivity-state"
              title={
                props.scenarioSensitivityRequested
                  ? "暂无可比较的情景结果"
                  : "尚未加载情景敏感度矩阵"
              }
              description={
                props.scenarioSensitivityRequested
                  ? props.scenarioSensitivity.emptyCopy
                  : "点击上方「加载矩阵」获取四档 FTP 情景敏感度结果。"
              }
            />
          ) : (
            <>
              <div className="product-category-financial-analysis__pressure-pack">
                <div className="product-category-financial-analysis__pressure-head">
                  <div>
                    <div className="product-category-financial-analysis__scenario-kicker">
                      压力复核包
                    </div>
                    <p>
                      先看临界点、资产/负债冲抵，再决定复核顺序；以下均为情景辅助分析。
                    </p>
                  </div>
                  <div className="product-category-financial-analysis__pressure-chip">
                    {
                      props.scenarioSensitivity.pressureSummary.sideOffset
                        .rateLabel
                    }
                  </div>
                </div>
                <div className="product-category-financial-analysis__pressure-grid">
                  <div className="product-category-financial-analysis__pressure-metric">
                    <span>
                      {
                        props.scenarioSensitivity.pressureSummary.breakeven
                          .label
                      }
                    </span>
                    <b
                      className={`is-${props.scenarioSensitivity.pressureSummary.breakeven.tone}`}
                    >
                      {
                        props.scenarioSensitivity.pressureSummary.breakeven
                          .valueLabel
                      }
                    </b>
                    <small>
                      {
                        props.scenarioSensitivity.pressureSummary.breakeven
                          .detailLabel
                      }
                    </small>
                  </div>
                  <div className="product-category-financial-analysis__pressure-offset">
                    <div className="product-category-financial-analysis__pressure-offset-head">
                      <span>资产/负债冲抵</span>
                      <b
                        className={`is-${props.scenarioSensitivity.pressureSummary.sideOffset.tone}`}
                      >
                        {
                          props.scenarioSensitivity.pressureSummary.sideOffset
                            .totalDeltaLabel
                        }
                      </b>
                    </div>
                    <div className="product-category-financial-analysis__offset-bars">
                      <div className="product-category-financial-analysis__offset-bar-row">
                        <span>
                          资产端{" "}
                          {
                            props.scenarioSensitivity.pressureSummary.sideOffset
                              .assetDeltaLabel
                          }
                        </span>
                        <div className="product-category-financial-analysis__offset-track">
                          <i
                            className={`product-category-financial-analysis__offset-bar is-asset ${props.scenarioSensitivity.pressureSummary.sideOffset.assetWidthClassName}`}
                          />
                        </div>
                      </div>
                      <div className="product-category-financial-analysis__offset-bar-row">
                        <span>
                          负债端{" "}
                          {
                            props.scenarioSensitivity.pressureSummary.sideOffset
                              .liabilityDeltaLabel
                          }
                        </span>
                        <div className="product-category-financial-analysis__offset-track">
                          <i
                            className={`product-category-financial-analysis__offset-bar is-liability ${props.scenarioSensitivity.pressureSummary.sideOffset.liabilityWidthClassName}`}
                          />
                        </div>
                      </div>
                    </div>
                    <small>
                      冲抵{" "}
                      {
                        props.scenarioSensitivity.pressureSummary.sideOffset
                          .offsetLabel
                      }{" "}
                      亿元 ·{" "}
                      {
                        props.scenarioSensitivity.pressureSummary.sideOffset
                          .conclusionLabel
                      }
                    </small>
                  </div>
                </div>
                <div className="product-category-financial-analysis__review-board">
                  <div className="product-category-financial-analysis__scenario-kicker">
                    复核顺序
                  </div>
                  {props.scenarioSensitivity.pressureSummary.reviewRows
                    .length === 0 ? (
                    <div className="product-category-financial-analysis__empty">
                      暂无可排序的复核产品行。
                    </div>
                  ) : (
                    <div className="product-category-financial-analysis__review-list">
                      {props.scenarioSensitivity.pressureSummary.reviewRows.map(
                        (row) => (
                          <button
                            aria-pressed={
                              props.selectedScenarioReviewCategoryId ===
                              row.categoryId
                            }
                            className="product-category-financial-analysis__review-row"
                            key={row.categoryId}
                            onClick={() =>
                              props.onSelectScenarioReview(row.categoryId)
                            }
                            type="button"
                          >
                            <span>{row.priorityLabel}</span>
                            <strong>{row.categoryLabel}</strong>
                            <small>
                              {row.sideLabel} · {row.triggerRateLabel} ·{" "}
                              {row.actionLabel}
                            </small>
                            <b className={`is-${row.tone}`}>{row.deltaLabel}</b>
                          </button>
                        ),
                      )}
                    </div>
                  )}
                </div>
                {scenarioExplanation ? (
                  <ProductCategoryScenarioExplanationCard
                    actionStatuses={props.scenarioReviewActionStatuses}
                    explanation={scenarioExplanation}
                    issueReasons={props.scenarioReviewIssueReasons}
                    onBulkActionStatus={props.onBulkScenarioReviewActionStatus}
                    onResetActions={props.onResetScenarioReviewActions}
                    onSetActionStatus={props.onSetScenarioReviewActionStatus}
                    onSetIssueReason={props.onSetScenarioReviewIssueReason}
                  />
                ) : null}
              </div>
              <ProductCategoryScenarioActionClosurePanel
                memoCategoryId={props.scenarioActionClosureMemoCategoryId}
                onSelectMemo={props.onSelectScenarioActionClosureMemo}
                onSetStatus={props.onSetScenarioActionClosureStatus}
                rows={props.scenarioSensitivity.actionClosureRows}
                statuses={props.scenarioActionClosureStatuses}
              />
              <ProductCategoryScenarioComparisonPanel
                filter={scenarioComparisonFilter}
                onFilterChange={setScenarioComparisonFilter}
                onSelectCategory={props.onSelectScenarioReview}
                rows={props.scenarioSensitivity.comparisonRows}
                selectedCategoryId={props.selectedScenarioReviewCategoryId}
              />
              <div className="product-category-financial-analysis__table-wrap">
                <table className="product-category-financial-analysis__table">
                  <thead>
                    <tr>
                      <th>FTP</th>
                      <th>资产端</th>
                      <th>负债端</th>
                      <th>总净营收</th>
                      <th>最大变动行</th>
                    </tr>
                  </thead>
                  <tbody>
                    {props.scenarioSensitivity.rows.map((row) => (
                      <tr key={row.rate}>
                        <td>{row.rateLabel}</td>
                        <td>
                          {row.assetNetIncomeLabel} / {row.assetDeltaLabel}
                        </td>
                        <td>
                          {row.liabilityNetIncomeLabel} /{" "}
                          {row.liabilityDeltaLabel}
                        </td>
                        <td className={`is-${row.tone}`}>
                          {row.grandNetIncomeLabel} / {row.grandDeltaLabel}
                        </td>
                        <td>
                          {row.topMoverCategoryLabel} {row.topMoverDeltaLabel}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="product-category-financial-analysis__scenario-path">
                <div className="product-category-financial-analysis__scenario-kicker">
                  FTP 压力路径
                </div>
                <div className="product-category-financial-analysis__path-rail">
                  {props.scenarioSensitivity.pathPoints.map((point) => (
                    <div
                      className={`product-category-financial-analysis__path-point is-${point.tone} ${point.positionClassName}`}
                      key={point.rateLabel}
                    >
                      <span>{point.rateLabel}</span>
                      <strong>{point.grandNetIncomeLabel}</strong>
                      <small>{point.grandDeltaLabel}</small>
                    </div>
                  ))}
                </div>
              </div>
              <div className="product-category-financial-analysis__scenario-brief">
                <div className="product-category-financial-analysis__scenario-summary">
                  <div className="product-category-financial-analysis__scenario-kicker">
                    情景解读
                  </div>
                  <p>
                    {props.scenarioSensitivity.analysisCopy ??
                      "四档 FTP 情景已加载，可结合下方区间和变动行继续复核。"}
                  </p>
                  <div className="product-category-financial-analysis__insight-grid">
                    {props.scenarioSensitivity.insightCards.map((card) => (
                      <div
                        className="product-category-financial-analysis__insight-card"
                        key={card.key}
                      >
                        <span>{card.label}</span>
                        <b className={`is-${card.tone}`}>{card.valueLabel}</b>
                        <small>{card.detailLabel}</small>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="product-category-financial-analysis__scenario-actions">
                  <div className="product-category-financial-analysis__scenario-kicker">
                    管理动作
                  </div>
                  {props.scenarioSensitivity.actionItems.map((item) => (
                    <div
                      className="product-category-financial-analysis__action-row"
                      key={item.title}
                    >
                      <div>
                        <strong>{item.title}</strong>
                        <span>{item.detailLabel}</span>
                      </div>
                      <b className={`is-${item.tone}`}>{item.valueLabel}</b>
                    </div>
                  ))}
                </div>
                <div className="product-category-financial-analysis__scenario-risks">
                  <div className="product-category-financial-analysis__scenario-kicker">
                    关键变动行排行
                  </div>
                  {props.scenarioSensitivity.riskRows.length === 0 ? (
                    <div className="product-category-financial-analysis__empty">
                      暂无可排序的最大变动产品行。
                    </div>
                  ) : (
                    <div className="product-category-financial-analysis__risk-list">
                      {props.scenarioSensitivity.riskRows.map((row) => (
                        <div
                          className="product-category-financial-analysis__risk-row"
                          key={row.categoryLabel}
                        >
                          <div>
                            <strong>{row.categoryLabel}</strong>
                            <span>
                              {row.occurrenceLabel} · 最弱 FTP{" "}
                              {row.worstRateLabel}
                            </span>
                          </div>
                          <b className={`is-${row.tone}`}>
                            {row.worstDeltaLabel}
                          </b>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="product-category-financial-analysis__scenario-heat">
                  <div className="product-category-financial-analysis__scenario-kicker">
                    产品行热力条
                  </div>
                  {props.scenarioSensitivity.heatRows.map((row) => (
                    <div
                      className="product-category-financial-analysis__heat-row"
                      key={row.categoryLabel}
                    >
                      <div className="product-category-financial-analysis__heat-row-head">
                        <span>{row.categoryLabel}</span>
                        <b className={`is-${row.tone}`}>{row.exposureLabel}</b>
                      </div>
                      <div className="product-category-financial-analysis__heat-track">
                        <span
                          className={`product-category-financial-analysis__heat-bar is-${row.tone} ${row.widthClassName}`}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </article>
        <article
          className="product-category-financial-analysis__panel"
          data-testid="product-category-decision-focus"
        >
          <div className="product-category-financial-analysis__panel-head">
            <div>
              <h3 className="product-category-financial-analysis__title">
                本期决策焦点
              </h3>
              <p className="product-category-financial-analysis__note">
                只使用当前产品行和正式归因，按贡献、压力、恶化和未解释残差提取。
              </p>
            </div>
          </div>
          {props.decisionFocus.emptyCopy ? (
            <div className="product-category-financial-analysis__empty">
              {props.decisionFocus.emptyCopy}
            </div>
          ) : (
            <div className="product-category-financial-analysis__focus-list">
              {props.decisionFocus.items.map((item) => (
                <div
                  className="product-category-financial-analysis__focus-item"
                  key={item.key}
                >
                  <div>
                    <strong>{item.categoryLabel}</strong>
                    <span>
                      {item.reasonLabel} · {item.secondaryLabel}
                    </span>
                  </div>
                  <b className={`is-${item.tone}`}>{item.primaryLabel}</b>
                </div>
              ))}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
