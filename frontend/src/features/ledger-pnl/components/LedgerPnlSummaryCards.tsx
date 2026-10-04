import type { LedgerMoneyValue, LedgerPnlAnalysisPayload, LedgerPnlSummaryPayload } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import { findPeriodComparisonRow, formatMoney, moneyTone } from "../models/ledgerPnlDisplay";
import { LedgerMoneyDisplay } from "./LedgerPnlSectionPresentation";

const ledgerCandidateSummaryMetrics = {
  ledger_monthly_pnl_core: {
    metricId: "MTR-LPN-001",
    note: "候选指标，pending_confirmation=true；不能替代正式 PnL 或产品分类 PnL。",
  },
  ledger_monthly_pnl_all: {
    metricId: "MTR-LPN-002",
    note: "候选指标，pending_confirmation=true；仅用于总账对账分析。",
  },
  ledger_net_assets: {
    metricId: "MTR-LPN-003",
    note: "候选指标，pending_confirmation=true；不是正式净资产财务指标。",
  },
} as const;

type LedgerCandidateSummaryMetricKey = keyof typeof ledgerCandidateSummaryMetrics;

/** 环比变化小字：文案 + tone（正负号展示逻辑，不做金额计算）。 */
type LedgerSummaryCardChange = { text: string; tone: "positive" | "negative" | "neutral" };

type LedgerSummaryCardModel = {
  key: string;
  title: string;
  value: string;
  candidateMetricKey?: LedgerCandidateSummaryMetricKey;
  /** 仅在 analysis 对比字段能对上本卡口径（同 CNX、同报告日链）时才提供。 */
  change?: LedgerSummaryCardChange;
};

function LedgerSummaryCard({ card }: { card: LedgerSummaryCardModel }) {
  const candidateMetric = card.candidateMetricKey
    ? ledgerCandidateSummaryMetrics[card.candidateMetricKey]
    : null;
  return (
    <div className="ledger-pnl-summary-card-frame">
      <div className="ledger-pnl-summary-card__header">
        <div className="ledger-pnl-summary-card__title">{card.title}</div>
        {candidateMetric ? (
          <span className="ledger-pnl-summary-card__badge">
            候选
          </span>
        ) : null}
      </div>
      <div className="ledger-pnl-summary-card__value">
        <LedgerMoneyDisplay text={card.value} />
      </div>
      {card.change ? (
        <div className="ledger-pnl-summary-card__change" data-tone={card.change.tone}>
          {card.change.text}
        </div>
      ) : null}
      {candidateMetric ? (
        <div
          className="ledger-pnl-summary-card__note"
          title={`${candidateMetric.metricId} ${candidateMetric.note}`}
        >
          {candidateMetric.metricId} {candidateMetric.note}
        </div>
      ) : null}
    </div>
  );
}

export function LedgerPnlSummaryCards({
  summary,
  analysisPayload,
}: {
  summary: LedgerPnlSummaryPayload | undefined;
  analysisPayload: LedgerPnlAnalysisPayload | undefined;
}) {
  /*
   * B2：环比变化小字只在 analysis 对比字段能对上本卡口径时才加——/summary 与 /analysis
   * 在同一 report_date + currency 下对 core_pnl/all_pnl 走同一后端聚合前缀
   * （ledger_pnl_service.py 的 LEDGER_PNL_ACCOUNT_PREFIXES 与 ledger_pnl_analysis.py 的
   * CORE_PNL_PREFIXES 共用同一常量），因此可直接消费 period_comparison 的 change 字段；
   * 总资产/总负债/净资产在 period_comparison.rows 里没有对应 metric_key，不加变化小字。
   */
  const summaryCardPeriodRows = analysisPayload?.period_comparison.rows;
  const summaryCardCorePnlChange = findPeriodComparisonRow(summaryCardPeriodRows, "core_pnl")?.change;
  const summaryCardAllPnlChange = findPeriodComparisonRow(summaryCardPeriodRows, "all_pnl")?.change;
  const buildSummaryCardChange = (
    change: LedgerMoneyValue | undefined,
  ): LedgerSummaryCardChange | undefined => {
    if (summary?.data_status === "no_data") return undefined;
    const text = formatMoney(change);
    if (text === EM_DASH) return undefined;
    return { text: `较上一可用报告期 ${text}`, tone: moneyTone(change) };
  };
  const summaryCards: LedgerSummaryCardModel[] = [
    {
      key: "ledger_monthly_pnl_core",
      title: "核心损益",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_monthly_pnl_core),
      candidateMetricKey: "ledger_monthly_pnl_core",
      change: buildSummaryCardChange(summaryCardCorePnlChange),
    },
    {
      key: "ledger_monthly_pnl_all",
      title: "全量损益",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_monthly_pnl_all),
      candidateMetricKey: "ledger_monthly_pnl_all",
      change: buildSummaryCardChange(summaryCardAllPnlChange),
    },
    {
      key: "ledger_total_assets",
      title: "总资产",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_total_assets),
    },
    {
      key: "ledger_total_liabilities",
      title: "总负债",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_total_liabilities),
    },
    {
      key: "ledger_net_assets",
      title: "净资产",
      value: summary?.data_status === "no_data" ? EM_DASH : formatMoney(summary?.ledger_net_assets),
      candidateMetricKey: "ledger_net_assets",
    },
  ];

  return <>{summaryCards.map((card) => <LedgerSummaryCard key={card.key} card={card} />)}</>;
}
