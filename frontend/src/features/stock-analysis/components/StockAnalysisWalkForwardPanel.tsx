import { useEffect, useMemo, useState } from "react";

import {
  fetchWalkForwardReport,
  type WalkForwardReportPayload,
  type WalkForwardScheduleSummary,
  type WalkForwardStrategyRow,
} from "../../../api/strategyReportsClient";
import { EM_DASH, formatPercent } from "../../../utils/format";
import "./StockAnalysisWalkForwardPanel.css";

/**
 * 回测诊断区「样本外验证」预制面板(walk-forward)。
 *
 * 自包含加载：挂载即拉 GET /api/strategy-reports/walk-forward；
 * 报告缺失(404)、请求失败或无可展示策略时整面隐藏(render null)，
 * 不在现有页面上留下空壳。数据契约全 optional，缺失字段一律 EM_DASH。
 */

type PanelPhase =
  | { status: "loading" }
  | { status: "hidden" }
  | { status: "ready"; payload: WalkForwardReportPayload };

export type StockAnalysisWalkForwardPanelProps = {
  /** 测试/接线注入的加载函数；缺省直连真实端点(同源相对路径)。 */
  loadReport?: () => Promise<WalkForwardReportPayload | null>;
};

/** 与 stockAnalysisPageLabels.outputKeyLabel 保持一致的最小映射(接线时可替换为共享映射)。 */
const STRATEGY_LABELS: Record<string, string> = {
  uptrend_momentum: "上升趋势",
  mean_reversion: "超跌池",
  factor_screen: "多因子",
  theme_breakout: "题材观察",
  hybrid_fusion: "融合池",
  fresh_trend_watchlist: "新趋势观察",
  stock_candidate: "趋势候选",
};

type VerdictTone = "positive" | "caution" | "neutral";

const VERDICT_PRESENTATION: Record<string, { label: string; tone: VerdictTone; order: number }> = {
  oos_supported: { label: "样本外支持", tone: "positive", order: 0 },
  oos_weakened: { label: "样本外衰减", tone: "caution", order: 1 },
  oos_inconclusive: { label: "方向不定", tone: "caution", order: 2 },
  insufficient_windows: { label: "样本不足", tone: "neutral", order: 9 },
};

function strategyLabel(row: WalkForwardStrategyRow): string {
  const key = row.strategy ?? "";
  return STRATEGY_LABELS[key] ?? (key || EM_DASH);
}

function verdictPresentation(verdict: string | null | undefined) {
  if (!verdict) return { label: "结论待补", tone: "neutral" as VerdictTone, order: 5 };
  return VERDICT_PRESENTATION[verdict] ?? { label: verdict, tone: "neutral" as VerdictTone, order: 5 };
}

function scheduleHasRows(schedule: WalkForwardScheduleSummary | null | undefined): boolean {
  return Boolean(schedule?.strategies?.length);
}

function renderableSchedules(payload: WalkForwardReportPayload | null): WalkForwardScheduleSummary[] {
  return (payload?.schedules ?? []).filter(scheduleHasRows);
}

function scheduleShortLabel(schedule: WalkForwardScheduleSummary): string {
  const train = schedule.train_months;
  const valid = schedule.valid_months;
  const step = schedule.step_months;
  if (train == null || valid == null || step == null) return schedule.label ?? EM_DASH;
  return `训${train} 验${valid} 步${step}(月)`;
}

function toneOfValue(value: number | null | undefined): string | undefined {
  if (value == null || Number.isNaN(value)) return undefined;
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return undefined;
}

/** 行内双条：样本内 vs 样本外中位超额，按行内绝对值最大者归一。 */
function ExcessBar({ value, max }: { value: number | null | undefined; max: number }) {
  const ratio = value != null && max > 0 ? Math.min(Math.abs(value) / max, 1) : 0;
  return (
    <svg className="stock-analysis-walk-forward__bar" aria-hidden="true">
      <rect className="stock-analysis-walk-forward__bar-track" width="100%" height="100%" rx="2" />
      {ratio > 0 ? (
        <rect
          className="stock-analysis-walk-forward__bar-fill"
          width={`${(ratio * 100).toFixed(1)}%`}
          height="100%"
          rx="2"
          data-negative={value != null && value < 0 ? "true" : undefined}
        />
      ) : null}
    </svg>
  );
}

function positiveWindowText(row: WalkForwardStrategyRow): string {
  const sign = row.excess_sign_consistency;
  const positive = sign?.positive_windows;
  const observed = sign?.observed_windows;
  if (positive == null || observed == null || observed === 0) return EM_DASH;
  const ratio = sign?.positive_ratio;
  const ratioText = ratio == null ? "" : ` (${formatPercent(ratio, false)})`;
  return `${positive}/${observed}${ratioText}`;
}

function riskBudgetDriftText(row: WalkForwardStrategyRow): string {
  const riskBudget = row.risk_budget;
  const switchRate = riskBudget?.switch_rate;
  const modeValue = riskBudget?.mode_value;
  if (switchRate == null && modeValue == null) return EM_DASH;
  const parts: string[] = [];
  if (switchRate != null) parts.push(`切换率 ${formatPercent(switchRate, false)}`);
  if (modeValue != null) parts.push(`众数 ${modeValue}`);
  return parts.join(" · ");
}

function riskBudgetSequenceTitle(row: WalkForwardStrategyRow): string | undefined {
  const params = row.risk_budget?.window_params;
  if (!params?.length) return undefined;
  const sequence = params
    .map((entry) => (entry.selected == null ? EM_DASH : String(entry.selected)))
    .join(" → ");
  return `rpt 逐窗最优(训练集选出): ${sequence}`;
}

function StrategyRow({ row }: { row: WalkForwardStrategyRow }) {
  const verdict = verdictPresentation(row.verdict);
  const inSample = row.in_sample_excess;
  const oosMedian = row.oos_excess_median;
  const barMax = Math.max(
    inSample != null ? Math.abs(inSample) : 0,
    oosMedian != null ? Math.abs(oosMedian) : 0,
  );
  return (
    <li
      className="stock-analysis-walk-forward__row"
      data-testid={`stock-analysis-walk-forward-row-${row.strategy ?? "unknown"}`}
      data-verdict={row.verdict ?? undefined}
    >
      <div className="stock-analysis-walk-forward__row-head">
        <span className="stock-analysis-walk-forward__strategy">{strategyLabel(row)}</span>
        <span
          className="stock-analysis-walk-forward__verdict"
          data-tone={verdict.tone}
          title={row.verdict_reason ?? undefined}
        >
          {verdict.label}
        </span>
      </div>
      <div className="stock-analysis-walk-forward__excess" role="group" aria-label="样本内外超额对比">
        <span className="stock-analysis-walk-forward__excess-label">样本内</span>
        <ExcessBar value={inSample} max={barMax} />
        <span className="stock-analysis-walk-forward__excess-value" data-tone={toneOfValue(inSample)}>
          {formatPercent(inSample, true)}
        </span>
        <span className="stock-analysis-walk-forward__excess-label">样本外中位</span>
        <ExcessBar value={oosMedian} max={barMax} />
        <span className="stock-analysis-walk-forward__excess-value" data-tone={toneOfValue(oosMedian)}>
          {formatPercent(oosMedian, true)}
        </span>
      </div>
      <dl className="stock-analysis-walk-forward__facts">
        <div>
          <dt>正超额窗口</dt>
          <dd>{positiveWindowText(row)}</dd>
        </div>
        <div>
          <dt>rpt 漂移</dt>
          <dd title={riskBudgetSequenceTitle(row)}>{riskBudgetDriftText(row)}</dd>
        </div>
      </dl>
    </li>
  );
}

export function StockAnalysisWalkForwardPanel({ loadReport }: StockAnalysisWalkForwardPanelProps) {
  const [phase, setPhase] = useState<PanelPhase>({ status: "loading" });
  const [activeScheduleIndex, setActiveScheduleIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = loadReport ?? (() => fetchWalkForwardReport());
    load()
      .then((payload) => {
        if (cancelled) return;
        if (renderableSchedules(payload).length > 0 && payload) {
          setActiveScheduleIndex(0);
          setPhase({ status: "ready", payload });
        } else {
          setPhase({ status: "hidden" });
        }
      })
      .catch(() => {
        if (!cancelled) setPhase({ status: "hidden" });
      });
    return () => {
      cancelled = true;
    };
  }, [loadReport]);

  const schedules = useMemo(
    () => (phase.status === "ready" ? renderableSchedules(phase.payload) : []),
    [phase],
  );
  const activeSchedule = schedules[activeScheduleIndex] ?? schedules[0] ?? null;
  const sortedRows = useMemo(() => {
    const rows = activeSchedule?.strategies ?? [];
    return [...rows].sort((a, b) => {
      const orderDelta = verdictPresentation(a.verdict).order - verdictPresentation(b.verdict).order;
      if (orderDelta !== 0) return orderDelta;
      return (a.strategy ?? "").localeCompare(b.strategy ?? "");
    });
  }, [activeSchedule]);

  // 报告缺失 / 请求失败 / 无可展示策略 → 整面隐藏；加载中也不占位。
  if (phase.status !== "ready" || !activeSchedule) return null;

  const { payload } = phase;
  const generatedDate = payload.generated_at?.slice(0, 10) ?? null;
  const issueCount = payload.issue_count ?? 0;

  return (
    <section
      className="stock-analysis-walk-forward"
      data-testid="stock-analysis-walk-forward"
      aria-label="样本外验证"
    >
      <header className="stock-analysis-walk-forward__head">
        <h3>样本外验证 · walk-forward</h3>
        {schedules.length > 1 ? (
          <div className="stock-analysis-walk-forward__schedules" role="tablist" aria-label="验证窗口配置">
            {schedules.map((schedule, index) => (
              <button
                key={schedule.label ?? index}
                type="button"
                role="tab"
                aria-selected={index === activeScheduleIndex}
                title={schedule.label ?? undefined}
                onClick={() => setActiveScheduleIndex(index)}
              >
                {scheduleShortLabel(schedule)}
              </button>
            ))}
          </div>
        ) : (
          <span className="stock-analysis-walk-forward__schedule-pill" title={activeSchedule.label ?? undefined}>
            {scheduleShortLabel(activeSchedule)}
          </span>
        )}
      </header>
      <ul className="stock-analysis-walk-forward__rows">
        {sortedRows.map((row, index) => (
          <StrategyRow key={row.strategy ?? index} row={row} />
        ))}
      </ul>
      <footer className="stock-analysis-walk-forward__foot">
        <span>
          {activeSchedule.window_count != null ? `${activeSchedule.window_count} 个验证窗` : EM_DASH}
          {activeSchedule.min_windows_for_verdict != null
            ? ` · 定论门槛 ${activeSchedule.min_windows_for_verdict} 窗`
            : ""}
        </span>
        <span>
          {generatedDate ? `报告 ${generatedDate}` : ""}
          {issueCount > 0 ? ` · ${issueCount} 条数据披露` : ""}
        </span>
      </footer>
    </section>
  );
}
