import { useEffect, useState } from "react";

import {
  fetchPretradeChecklist,
  type PretradeChecklistFetchResult,
  type PretradeChecklistItem,
  type PretradeChecklistPayload,
} from "../../../api/pretradeChecklistClient";
import { EM_DASH, formatPercent } from "../../../utils/format";
import "./StockAnalysisPretradeChecklist.css";

/**
 * 决策首屏「盘前操作清单」卡：回答"今天开盘我该做什么"。
 *
 * 自包含加载：挂载即拉 GET /api/pretrade-checklist。
 * 五态：loading 骨架占位(防重排) / 后端明确空或能力不存在(404) → 整面收缩隐藏 /
 * 请求失败 → 一行错误+重试 / stale → 区头警示且可买徽标降权 / ready 正常呈现。
 * 契约全 optional，缺失字段一律 EM_DASH。
 * 观察面输出：仅供盘前复核参考，不构成交易指令。
 */

type PanelPhase =
  | { status: "loading" }
  | { status: "hidden" }
  | { status: "error"; reason: string }
  | { status: "ready"; payload: PretradeChecklistPayload };

export type StockAnalysisPretradeChecklistProps = {
  /** 测试/接线注入的加载函数；缺省直连真实端点(同源相对路径)。 */
  loadChecklist?: () => Promise<PretradeChecklistFetchResult>;
};

type StatusTone = "positive" | "negative" | "caution" | "neutral";

const STATUS_PRESENTATION: Record<string, { label: string; tone: StatusTone }> = {
  buyable: { label: "可买", tone: "positive" },
  blocked_suspended: { label: "停牌拦", tone: "negative" },
  blocked_limit: { label: "涨跌停拦", tone: "negative" },
  review: { label: "复核", tone: "caution" },
  data_missing: { label: "数据缺", tone: "neutral" },
};

const BLOCK_REASON_LABELS: Record<string, string> = {
  missing_daily_observation: "缺当日观测",
  suspended: "停牌",
  limit_up: "涨停",
  limit_down: "跌停",
  missing_amount: "金额无法定标",
  non_positive_amount: "金额异常",
  low_liquidity: "流动性不足",
};

const DATA_FLAG_LABELS: Record<string, string> = {
  adj_factor_missing: "复权缺口",
  limit_price_missing: "涨跌停价缺",
};

const GATE_STATE_LABELS: Record<string, string> = {
  HOT: "热",
  WARM: "暖",
  COLD: "冷",
  OVERHEAT: "过热",
};

function statusPresentation(status: string | null | undefined, stale: boolean) {
  if (!status) return { label: "状态待补", tone: "neutral" as StatusTone };
  const base = STATUS_PRESENTATION[status] ?? { label: status, tone: "neutral" as StatusTone };
  // 信号过期时绿色"可买"降权为中性描边：绿色仅在信号有效期内使用。
  if (stale && status === "buyable") {
    return { label: "可买(已过期)", tone: "neutral" as StatusTone };
  }
  return base;
}

function blockReasonText(item: PretradeChecklistItem): string {
  const reasons = (item.block_reasons ?? [])
    .filter((reason): reason is string => Boolean(reason))
    .map((reason) => BLOCK_REASON_LABELS[reason] ?? reason);
  return reasons.length > 0 ? reasons.join("、") : EM_DASH;
}

function itemFlags(item: PretradeChecklistItem): string[] {
  return (item.data_flags ?? [])
    .filter((flag): flag is string => Boolean(flag))
    .map((flag) => DATA_FLAG_LABELS[flag] ?? flag);
}

function positionHintText(item: PretradeChecklistItem): string {
  // 等权为主口径(门控敞口/候选数)；门控缺省时回退 risk_budget 上限建议。
  const equalWeight = item.position_hint?.equal_weight;
  if (equalWeight != null && !Number.isNaN(equalWeight)) {
    return formatPercent(equalWeight, false);
  }
  const rawWeight = item.position_hint?.raw_weight;
  if (rawWeight == null || Number.isNaN(rawWeight)) return EM_DASH;
  const capped = item.position_hint?.capped ? "(封顶)" : "";
  return `≤${formatPercent(rawWeight, false)}${capped}`;
}

function positionHintTitle(item: PretradeChecklistItem): string | undefined {
  const equalWeight = item.position_hint?.equal_weight;
  if (equalWeight != null && !Number.isNaN(equalWeight)) {
    return "等权主口径：当日门控敞口 / 候选数(敞口已进入权重)";
  }
  const basis = item.position_hint?.stop_basis;
  if (!basis) return undefined;
  return basis === "fallback"
    ? "risk_budget 上限建议(实验参考)：止损距离取政策 fallback(ema10 缺失)，实盘仍受门控敞口截断"
    : "risk_budget 上限建议(实验参考)：止损距离取 close 对 ema10 的距离，实盘仍受门控敞口截断";
}

function gateText(payload: PretradeChecklistPayload): string {
  const gate = payload.gate;
  if (!gate || gate.status !== "available") return "门控数据缺失";
  const state = gate.state ? (GATE_STATE_LABELS[gate.state] ?? gate.state) : EM_DASH;
  const exposure = gate.exposure == null ? EM_DASH : formatPercent(gate.exposure, false);
  return `门控 ${state} · 敞口 ${exposure}`;
}

/** 整列同值收敛(§6)：所有行的仓位建议一致时收进区头，明细列不再重复。 */
function uniformPositionHint(items: PretradeChecklistItem[]): { text: string; title?: string } | null {
  if (items.length < 2) return null;
  const first = positionHintText(items[0]);
  if (first === EM_DASH) return null;
  if (!items.every((item) => positionHintText(item) === first)) return null;
  return { text: first, title: positionHintTitle(items[0]) };
}

/** 整列同值收敛(§6)：出现在每一行的数据缺口标记只在区头说明一次。 */
function wholeColumnFlags(items: PretradeChecklistItem[]): string[] {
  if (items.length < 2) return [];
  const [first, ...rest] = items.map((item) => new Set(itemFlags(item)));
  return [...first].filter((flag) => rest.every((flags) => flags.has(flag)));
}

function ChecklistRow({
  item,
  stale,
  hiddenFlags,
  showWeightCell,
}: {
  item: PretradeChecklistItem;
  stale: boolean;
  hiddenFlags: string[];
  showWeightCell: boolean;
}) {
  const status = statusPresentation(item.buyable_status, stale);
  const flags = itemFlags(item).filter((flag) => !hiddenFlags.includes(flag));
  return (
    <li
      className="stock-analysis-pretrade__row"
      data-testid={`stock-analysis-pretrade-row-${item.stock_code ?? "unknown"}`}
      data-status={item.buyable_status ?? undefined}
      data-stale={stale ? "true" : undefined}
    >
      <div className="stock-analysis-pretrade__identity" title={item.sector_name ?? undefined}>
        <span className="stock-analysis-pretrade__code">{item.stock_code ?? EM_DASH}</span>
        <span className="stock-analysis-pretrade__name">{item.stock_name ?? EM_DASH}</span>
      </div>
      <span
        className="stock-analysis-pretrade__status"
        data-tone={status.tone}
        title={item.trade_status ?? (stale && item.buyable_status === "buyable" ? "信号已过期，可买判定仅供参考" : undefined)}
      >
        {status.label}
      </span>
      {showWeightCell ? (
        <span className="stock-analysis-pretrade__weight" title={positionHintTitle(item)}>
          {positionHintText(item)}
        </span>
      ) : null}
      <span className="stock-analysis-pretrade__reason">
        {blockReasonText(item)}
        {flags.length > 0 ? (
          <span className="stock-analysis-pretrade__flags">{flags.join("、")}</span>
        ) : null}
      </span>
    </li>
  );
}

export function StockAnalysisPretradeChecklist({ loadChecklist }: StockAnalysisPretradeChecklistProps) {
  const [phase, setPhase] = useState<PanelPhase>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = loadChecklist ?? (() => fetchPretradeChecklist());
    setPhase({ status: "loading" });
    load()
      .then((result) => {
        if (cancelled) return;
        if (result.kind === "ok" && (result.payload.items?.length ?? 0) > 0) {
          setPhase({ status: "ready", payload: result.payload });
        } else if (result.kind === "error") {
          setPhase({ status: "error", reason: result.reason });
        } else {
          // missing(404/明确空) 或 items 为空 → 整面收缩隐藏。
          setPhase({ status: "hidden" });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setPhase({
            status: "error",
            reason: error instanceof Error ? error.message : String(error),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [loadChecklist, attempt]);

  // 仅后端明确空/能力不存在时收缩隐藏。
  if (phase.status === "hidden") return null;

  if (phase.status === "loading") {
    return (
      <section
        className="stock-analysis-pretrade stock-analysis-pretrade--placeholder"
        data-testid="stock-analysis-pretrade-loading"
        aria-label="盘前操作清单加载中"
      >
        <header className="stock-analysis-pretrade__head">
          <div className="stock-analysis-pretrade__title-group">
            <h3>盘前操作清单</h3>
            <span className="stock-analysis-pretrade__as-of">加载中…</span>
          </div>
        </header>
        <div className="stock-analysis-pretrade__skeleton" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  }

  if (phase.status === "error") {
    return (
      <section
        className="stock-analysis-pretrade stock-analysis-pretrade--placeholder"
        data-testid="stock-analysis-pretrade-error"
        aria-label="盘前操作清单加载失败"
      >
        <header className="stock-analysis-pretrade__head">
          <div className="stock-analysis-pretrade__title-group">
            <h3>盘前操作清单</h3>
          </div>
        </header>
        <p className="stock-analysis-pretrade__error-line" role="alert" title={phase.reason}>
          <span>清单加载失败，请重试。</span>
          <button
            type="button"
            data-testid="stock-analysis-pretrade-retry"
            onClick={() => setAttempt((current) => current + 1)}
          >
            重试
          </button>
        </p>
      </section>
    );
  }

  const { payload } = phase;
  const items = payload.items ?? [];
  const stale = payload.staleness?.status === "stale" || payload.checklist_status === "stale";
  const staleGap = payload.staleness?.calendar_gap_days;
  const summary = payload.summary;
  const summaryText = [
    `可买 ${summary?.buyable_count ?? 0}`,
    `拦截 ${summary?.blocked_count ?? 0}`,
    `复核 ${summary?.review_count ?? 0}`,
    `数据缺 ${summary?.data_missing_count ?? 0}`,
  ].join(" / ");
  const coverageWarning = payload.position_size_hint?.coverage_warning ?? null;
  const uniformHint = uniformPositionHint(items);
  const columnFlags = wholeColumnFlags(items);
  const uniformNotes: string[] = [];
  if (uniformHint) uniformNotes.push(`统一建议仓位 ${uniformHint.text}`);
  if (columnFlags.length > 0) uniformNotes.push(`全列缺口：${columnFlags.join("、")}`);

  return (
    <section
      className="stock-analysis-pretrade"
      data-testid="stock-analysis-pretrade-checklist"
      data-uniform-weight={uniformHint ? "true" : undefined}
      aria-label="盘前操作清单"
    >
      <header className="stock-analysis-pretrade__head">
        <div className="stock-analysis-pretrade__title-group">
          <h3>盘前操作清单</h3>
          <span className="stock-analysis-pretrade__as-of">
            信号日 {payload.as_of_date ?? EM_DASH}
          </span>
          {stale ? (
            <span
              className="stock-analysis-pretrade__stale"
              data-testid="stock-analysis-pretrade-stale"
            >
              {staleGap != null ? `信号已过期 ${staleGap} 天` : "信号已过期"}
            </span>
          ) : null}
        </div>
        <span
          className="stock-analysis-pretrade__gate"
          data-gate-status={payload.gate?.status ?? "missing"}
          title={payload.gate?.note ?? undefined}
        >
          {gateText(payload)}
        </span>
      </header>
      {uniformNotes.length > 0 ? (
        <p
          className="stock-analysis-pretrade__uniform-note"
          data-testid="stock-analysis-pretrade-uniform-note"
          title={uniformHint?.title}
        >
          {uniformNotes.join("；")}
        </p>
      ) : null}
      <ul className="stock-analysis-pretrade__rows">
        {items.map((item, index) => (
          <ChecklistRow
            key={item.stock_code ?? index}
            item={item}
            stale={stale}
            hiddenFlags={columnFlags}
            showWeightCell={!uniformHint}
          />
        ))}
      </ul>
      <footer className="stock-analysis-pretrade__foot">
        <span>{summaryText}</span>
        <span title={coverageWarning ?? undefined}>
          {coverageWarning ? "仓位提示已降级 · " : ""}
          观察面输出，不构成交易指令
        </span>
      </footer>
    </section>
  );
}
