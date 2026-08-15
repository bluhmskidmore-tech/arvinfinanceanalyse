import type {
  MacroToolkitHasonStrategy,
  MacroToolkitModelReadiness,
} from "../../../api/macroToolkitClient";
import { EM_DASH, type MetricTone } from "../../../pageModel";
import { hasonFrameworkDisplayName } from "../../macro-toolkit/lib/macroToolkitDisplayFormat";
import { statusColor, statusLabel } from "../../macro-toolkit/lib/macroToolkitPanelShared";
import {
  hasonBoundaryText,
  modelDegradedReasonText,
  type MacroObservationStrategyEvidenceView,
} from "../model/macroObservationPageModel";
import "./MacroObservationModelCrisis.css";

/**
 * 03 模型与策略证据：三段式布局——模型就绪简表（左）/ Hason 摘要卡 +
 * 策略数据状态（右）/ 策略供数表 + 影子组合 / ETF 摘要（下满宽）。
 * 全部 analytical only：本区不出现任何刷新 / 修复操作按钮。
 */

/**
 * model_readiness 枚举中文化 + tone（枚举见 MacroToolkitModelReadiness.readiness）。
 * 未知 token 兜底原样展示 + neutral（muted 徽标），不虚构业务含义。
 */
const MODEL_READINESS_DISPLAY: Record<string, { label: string; tone: MetricTone }> = {
  artifact_backed: { label: "工件支撑", tone: "positive" },
  missing_output: { label: "产物缺失", tone: "negative" },
  stale: { label: "陈旧", tone: "warning" },
  registered_only: { label: "仅注册", tone: "warning" },
  degraded: { label: "降级", tone: "warning" },
  unknown: { label: "待确认", tone: "neutral" },
};

function modelReadinessDisplay(readiness: string): { label: string; tone: MetricTone } {
  return MODEL_READINESS_DISPLAY[readiness] ?? { label: readiness, tone: "neutral" };
}

/** statusColor 的 green/gold/red/default → MetricTone（Hason display_status 徽标）。 */
const STATUS_COLOR_TO_TONE: Record<string, MetricTone> = {
  green: "positive",
  gold: "warning",
  red: "negative",
};

function hasonStatusTone(status: string): MetricTone {
  return STATUS_COLOR_TO_TONE[statusColor(status)] ?? "neutral";
}

function ModelReadinessPanel({ models }: { models: MacroToolkitModelReadiness[] }) {
  // 只读边界声明保留在页头徽标与只读细注；卡级「仅观察」脚注按 §6 去重删除。
  return (
    <section className="macro-observation-modelstrategy-panel" aria-label="模型就绪简表">
      <div className="macro-observation-view__panel-head">
        <h3 className="macro-observation-view__panel-title">模型就绪</h3>
        <span className="macro-observation-view__panel-hint">
          {models.length ? `${models.length} 个模型` : EM_DASH}
        </span>
      </div>
      {models.length ? (
        <table className="macro-observation-view__table">
          <thead>
            <tr>
              <th>模型</th>
              <th>状态</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => {
              const display = modelReadinessDisplay(model.readiness);
              return (
                <tr key={model.id}>
                  <td>{model.label}</td>
                  <td>
                    <span
                      className="macro-observation-modelstrategy-badge"
                      data-tone={display.tone}
                    >
                      {display.label}
                    </span>
                  </td>
                  <td
                    className="macro-observation-modelstrategy-note-cell"
                    title={model.degraded_reason ?? undefined}
                  >
                    {modelDegradedReasonText(model.degraded_reason)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="macro-observation-modelstrategy-empty">模型就绪清单待完整分析确认。</p>
      )}
    </section>
  );
}

function HasonSummaryCard({ hason }: { hason: MacroToolkitHasonStrategy | null }) {
  return (
    <section className="macro-observation-modelstrategy-panel" aria-label="Hason 框架摘要">
      {hason ? (
        <>
          <div className="macro-observation-modelstrategy-hason-head">
            <h3 className="macro-observation-modelstrategy-hason-name" title={hason.framework_name}>
              {hasonFrameworkDisplayName(hason.framework_name)}
            </h3>
            <span
              className="macro-observation-modelstrategy-badge"
              data-tone={hasonStatusTone(hason.display_status)}
            >
              {statusLabel(hason.display_status)}
            </span>
          </div>
          <div
            className="macro-observation-modelstrategy-readiness-row"
            aria-label="Hason 模块就绪读数"
          >
            <span className="macro-observation-modelstrategy-readiness-item">
              <span
                className="macro-observation-modelstrategy-dot"
                data-kind="ready"
                aria-hidden="true"
              />
              就绪 <strong>{hason.readiness.ready_modules}</strong>
            </span>
            <span className="macro-observation-modelstrategy-readiness-item">
              <span
                className="macro-observation-modelstrategy-dot"
                data-kind="partial"
                aria-hidden="true"
              />
              部分 <strong>{hason.readiness.partial_modules}</strong>
            </span>
            <span className="macro-observation-modelstrategy-readiness-item">
              <span
                className="macro-observation-modelstrategy-dot"
                data-kind="missing"
                aria-hidden="true"
              />
              缺失 <strong>{hason.readiness.missing_modules}</strong>
            </span>
            <span className="macro-observation-modelstrategy-readiness-item">
              共 <strong>{hason.readiness.total_modules}</strong> 模块
            </span>
          </div>
          <p className="macro-observation-modelstrategy-boundary" title={hason.boundary}>
            {hasonBoundaryText(hason.boundary)}
          </p>
        </>
      ) : (
        <p className="macro-observation-modelstrategy-empty">Hason 框架摘要待完整分析确认。</p>
      )}
    </section>
  );
}

export default function MacroObservationModelStrategySection({
  modelReadiness,
  hasonStrategy,
  strategy,
}: {
  modelReadiness: MacroToolkitModelReadiness[];
  hasonStrategy: MacroToolkitHasonStrategy | null;
  strategy: MacroObservationStrategyEvidenceView;
}) {
  const { counts, dataStatus } = strategy;
  // 区头 meta 只列非零项，`·` 不超单行配额（DESIGN §7）；全部为零时只报全链路。
  const countsHint = [
    `全链路 ${counts.full}`,
    counts.partial ? `部分 ${counts.partial}` : "",
    counts.degraded ? `降级 ${counts.degraded}` : "",
    counts.sample ? `样例 ${counts.sample}` : "",
  ]
    .filter(Boolean)
    .join(" / ");
  const showChainColumn = strategy.rows.some((row) => row.chainNote);
  return (
    <div className="macro-observation-modelstrategy-stack">
      <div className="macro-observation-modelstrategy-layout">
        <ModelReadinessPanel models={modelReadiness} />
        <div className="macro-observation-modelstrategy-side">
          <HasonSummaryCard hason={hasonStrategy} />
          {dataStatus ? (
            <section className="macro-observation-modelstrategy-panel" aria-label="策略数据状态">
              <span className="macro-observation-modelstrategy-stat-label">策略数据状态</span>
              <span className="macro-observation-modelstrategy-stat-value">
                {dataStatus.statusText}
              </span>
              {dataStatus.summaryCount != null ? (
                <span className="macro-observation-modelstrategy-stat-note">
                  摘要 {dataStatus.summaryCount} 条
                </span>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>

      <section className="macro-observation-modelstrategy-panel" aria-label="策略供数">
        <div className="macro-observation-view__panel-head">
          <h3 className="macro-observation-view__panel-title">策略供数</h3>
          <span className="macro-observation-view__panel-hint">
            {strategy.rows.length ? countsHint : EM_DASH}
          </span>
        </div>
        {/* 来源链全表同句时收敛区头一次（§6 去重）；列内只留行间差异，无差异整列删。 */}
        {strategy.commonChainNote ? (
          <p className="macro-observation-modelstrategy-chain-note">{strategy.commonChainNote}</p>
        ) : null}
        {strategy.rows.length ? (
          <table className="macro-observation-view__table">
            <thead>
              <tr>
                <th>策略</th>
                <th>状态</th>
                {showChainColumn ? <th>来源链</th> : null}
              </tr>
            </thead>
            <tbody>
              {strategy.rows.map((row) => (
                <tr key={row.key}>
                  <td>{row.label}</td>
                  <td>
                    <span className="macro-observation-modelstrategy-badge" data-tone={row.tone}>
                      {row.statusText}
                    </span>
                  </td>
                  {showChainColumn ? (
                    <td className="macro-observation-modelstrategy-note-cell">
                      {row.chainNote ?? EM_DASH}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="macro-observation-modelstrategy-empty">策略供数明细待完整分析确认。</p>
        )}
        {dataStatus?.reason ? (
          <p className="macro-observation-modelstrategy-reason">
            <strong>策略不可用原因</strong>
            {dataStatus.reason}
          </p>
        ) : null}
        <div className="macro-observation-modelstrategy-summaries">
          <div className="macro-observation-modelstrategy-summary-card" aria-label="影子组合摘要">
            <span className="macro-observation-modelstrategy-stat-label">
              {strategy.shadowPortfolio.label}
            </span>
            <span className="macro-observation-modelstrategy-stat-value">
              {strategy.shadowPortfolio.value}
            </span>
            <span className="macro-observation-modelstrategy-stat-note">
              {strategy.shadowPortfolio.detail}
            </span>
          </div>
          <div className="macro-observation-modelstrategy-summary-card" aria-label="宏观 ETF 策略摘要">
            <span className="macro-observation-modelstrategy-stat-label">宏观 ETF 策略</span>
            {strategy.etfStrategy ? (
              // 「仅观察」边界句已由页头徽标与只读细注声明，卡级脚注按 §6 去重；
              // 原始 boundary 收 title 供溯源。
              <span
                className="macro-observation-modelstrategy-stat-value"
                title={strategy.etfStrategy.boundary}
              >
                双频 {strategy.etfStrategy.dualFrequencyStatusText}
              </span>
            ) : (
              <>
                <span className="macro-observation-modelstrategy-stat-value">{EM_DASH}</span>
                <span className="macro-observation-modelstrategy-stat-note">
                  策略摘要未携带 ETF 快照，完整分析后再确认。
                </span>
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
