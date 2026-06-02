import type { BalanceAnalysisOverviewPayload, BalanceAnalysisWorkbookPayload } from "../../../api/contracts";
import { KpiCard } from "../../workbench/components/KpiCard";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";
import {
  summaryGridStyle,
  firstScreenGridStyle,
  formalHeroStyle,
  heroMetaRowStyle,
  heroDetailGridStyle,
  heroDetailCardStyle,
  priorityBoardStyle,
  priorityCardStyle,
} from "../pages/BalanceAnalysisPage.styles";
import { signalAccentStyle, heroMetaChipStyle } from "../pages/BalanceAnalysisPage.helpers";
import type { PrioritySignal } from "../pages/BalanceAnalysisPage.helpers";
import {
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
} from "../pages/balanceAnalysisPageModel";

interface Props {
  overview: BalanceAnalysisOverviewPayload | undefined;
  overviewMeta: ReturnType<typeof import("../hooks/useBalanceAnalysisData").useBalanceAnalysisData>["overviewMeta"];
  workbook: BalanceAnalysisWorkbookPayload | undefined;
  prioritySignals: PrioritySignal[];
  selectedReportDate: string;
  positionScope: string;
  currencyBasis: string;
}

function formatBalanceScopeLabel(scope: string | undefined): string {
  if (scope === "asset") return "资产端";
  if (scope === "liability") return "负债端";
  if (scope === "all") return "全头寸";
  return "未设定";
}

function formatCurrencyBasisLabel(basis: string | undefined): string {
  if (basis === "native") return "原币";
  if (basis === "CNY") return "CNY";
  return "未设定";
}

function formatMetaBasisLabel(basis: string | undefined): string {
  if (basis === "formal") return "正式口径";
  if (basis === "analytical") return "分析口径";
  return "—";
}

function formatMetaQualityLabel(quality: string | undefined): string {
  if (quality === "ok") return "正常";
  if (quality === "warning") return "预警";
  if (quality === "error") return "错误";
  if (quality === "stale") return "陈旧";
  return "—";
}

function formatFallbackModeLabel(mode: string | undefined): string {
  if (mode === "none") return "未降级";
  if (mode === "latest_snapshot") return "最新快照降级";
  return mode ?? "—";
}

export function BalanceAnalysisCardsSection({
  overview,
  overviewMeta,
  workbook,
  prioritySignals,
  selectedReportDate,
  positionScope,
  currencyBasis,
}: Props) {
  const overviewCards = [
    {
      key: "total-market-value",
      label: "总市值合计",
      value: formatBalanceAmountToYiFromYuan(overview?.total_market_value_amount),
      unit: "亿元",
      detail: "正式总览 · 总市值字段",
      valueVariant: "text" as const,
    },
    {
      key: "total-amortized-cost",
      label: "摊余成本合计",
      value: formatBalanceAmountToYiFromYuan(overview?.total_amortized_cost_amount),
      unit: "亿元",
      detail: "正式总览 · 摊余成本字段",
      valueVariant: "text" as const,
    },
    {
      key: "total-accrued-interest",
      label: "应计利息合计",
      value: formatBalanceAmountToYiFromYuan(overview?.total_accrued_interest_amount),
      unit: "亿元",
      detail: "正式总览 · 应计利息字段",
      valueVariant: "text" as const,
    },
    {
      key: "summary-rows",
      label: "汇总行数",
      value: String(overview?.summary_row_count ?? "—"),
      detail: "正式总览 · 汇总行数",
      valueVariant: "text" as const,
    },
    {
      key: "detail-rows",
      label: "明细行数",
      value: String(overview?.detail_row_count ?? "—"),
      detail: "正式总览 · 明细行数",
      valueVariant: "text" as const,
    },
    ...(workbook?.cards ?? []).map((card) => ({
      key: `workbook-card-${card.key}`,
      label: card.label,
      value: formatBalanceAmountToYiFromWan(card.value),
      unit: "亿元",
      detail: `${card.note ?? "工作簿摘要"} · 工作簿`,
      valueVariant: "text" as const,
    })),
  ];

  return (
    <>
      <div style={firstScreenGridStyle}>
        <section style={formalHeroStyle}>
          <div style={{ display: "grid", gap: designTokens.space[2] }}>
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: designTokens.fontSize[12],
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              正式快照
            </span>
            <div
              style={{
                fontSize: `clamp(${designTokens.fontSize[24]}px, 3vw, ${designTokens.fontSize[24] + designTokens.space[2]}px)`,
                lineHeight: designTokens.lineHeight.tight,
                fontWeight: 700,
                letterSpacing: "-0.04em",
                color: shellTokens.colorTextPrimary,
                maxWidth: 720,
              }}
            >
              当前页先回答正式口径下的规模、口径和治理信号，不再把静态演示指标放进首屏结论。
            </div>
            <p
              style={{
                margin: 0,
                color: shellTokens.colorTextSecondary,
                fontSize: designTokens.fontSize[14],
                lineHeight: 1.8,
                maxWidth: 760,
              }}
            >
              报告日 {(overview?.report_date ?? selectedReportDate) || "—"}，范围{" "}
              {formatBalanceScopeLabel(overview?.position_scope ?? positionScope)}，币种口径{" "}
              {formatCurrencyBasisLabel(overview?.currency_basis ?? currencyBasis)}。如果降级、质量或
              治理信号异常，优先进入下方正式汇总驾驶舱和右侧治理栏核对，而不是依赖分析口径衍生结论。
            </p>
          </div>

          <div style={heroMetaRowStyle}>
            {(
              [
                {
                  label: `口径 ${formatMetaBasisLabel(overviewMeta?.basis)}`,
                  tone: overviewMeta?.basis === "formal" ? "positive" : "neutral",
                },
                {
                  label: `正式可用 ${String(overviewMeta?.formal_use_allowed ?? "—")}`,
                  tone: overviewMeta?.formal_use_allowed ? "positive" : "warning",
                },
                {
                  label: `质量 ${formatMetaQualityLabel(overviewMeta?.quality_flag)}`,
                  tone: overviewMeta?.quality_flag === "ok" ? "positive" : "warning",
                },
                {
                  label: `降级 ${formatFallbackModeLabel(overviewMeta?.fallback_mode)}`,
                  tone:
                    overviewMeta?.fallback_mode && overviewMeta.fallback_mode !== "none"
                      ? "warning"
                      : "accent",
                },
              ] as const
            ).map((chip) => (
              <span
                key={chip.label}
                style={{
                  ...heroMetaChipStyle(chip.tone),
                  display: "inline-flex",
                  alignItems: "center",
                  padding: `${designTokens.space[2] - designTokens.space[1]}px ${designTokens.space[3] - designTokens.space[1]}px`,
                  borderRadius: 999,
                  fontSize: designTokens.fontSize[12],
                  fontWeight: 700,
                }}
              >
                {chip.label}
              </span>
            ))}
          </div>

          <div style={heroDetailGridStyle}>
            <div style={heroDetailCardStyle}>
              <span style={{ color: shellTokens.colorTextMuted, fontSize: designTokens.fontSize[12] }}>正式汇总查询</span>
              <strong
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: designTokens.fontSize[24],
                  ...tabularNumsStyle,
                }}
              >
                {String(overview?.summary_row_count ?? "—")}
              </strong>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: designTokens.fontSize[12] }}>
                汇总行，决定首轮汇总阅读范围
              </span>
            </div>
            <div style={heroDetailCardStyle}>
              <span style={{ color: shellTokens.colorTextMuted, fontSize: designTokens.fontSize[12] }}>正式明细查询</span>
              <strong
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: designTokens.fontSize[24],
                  ...tabularNumsStyle,
                }}
              >
                {String(overview?.detail_row_count ?? "—")}
              </strong>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: designTokens.fontSize[12] }}>
                明细行，下钻时再进入明细接口
              </span>
            </div>
            <div style={heroDetailCardStyle}>
              <span style={{ color: shellTokens.colorTextMuted, fontSize: designTokens.fontSize[12] }}>工作簿摘要卡</span>
              <strong
                style={{
                  color: shellTokens.colorTextPrimary,
                  fontSize: designTokens.fontSize[24],
                  ...tabularNumsStyle,
                }}
              >
                {String(workbook?.cards.length ?? 0)}
              </strong>
              <span style={{ color: shellTokens.colorTextSecondary, fontSize: designTokens.fontSize[12] }}>
                工作簿摘要，保留业务语义更强的正式摘要
              </span>
            </div>
          </div>
        </section>

        <section data-testid="balance-analysis-priority-board" style={priorityBoardStyle}>
          <div style={{ display: "grid", gap: designTokens.space[2] }}>
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: designTokens.fontSize[12],
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              治理信号
            </span>
            <h2
              style={{
                margin: 0,
                fontSize: designTokens.fontSize[20],
                fontWeight: 700,
                color: shellTokens.colorTextPrimary,
              }}
            >
              当前行动信号
            </h2>
            <p
              style={{
                margin: 0,
                color: shellTokens.colorTextSecondary,
                fontSize: designTokens.fontSize[13],
                lineHeight: 1.7,
              }}
            >
              这里不重算风险和利差，只把决策事项、风险预警、事件日历的现有治理信号提到前面。
            </p>
          </div>

          <div style={{ display: "grid", gap: designTokens.space[3] }}>
            {prioritySignals.map((signal) => (
              <article key={signal.key} style={priorityCardStyle}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: designTokens.space[3],
                  }}
                >
                  <span
                    style={{
                      color: shellTokens.colorTextMuted,
                      fontSize: designTokens.fontSize[12],
                      fontWeight: 700,
                    }}
                  >
                    {signal.title}
                  </span>
                  <span
                    style={{
                      ...signalAccentStyle(signal.tone),
                      display: "inline-flex",
                      alignItems: "center",
                      padding: `${designTokens.space[1]}px ${designTokens.space[2]}px`,
                      borderRadius: 999,
                      fontSize: designTokens.fontSize[11],
                      fontWeight: 700,
                      ...tabularNumsStyle,
                    }}
                  >
                    {signal.eyebrow}
                  </span>
                </div>
                <div
                  style={{
                    color: shellTokens.colorTextPrimary,
                    fontSize: designTokens.fontSize[16],
                    fontWeight: 700,
                    lineHeight: 1.4,
                  }}
                >
                  {signal.highlight}
                </div>
                <div
                  style={{
                    color: shellTokens.colorTextSecondary,
                    fontSize: designTokens.fontSize[12],
                    lineHeight: 1.6,
                  }}
                >
                  {signal.detail}
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <div
        data-testid="balance-analysis-overview-cards"
        style={{ ...summaryGridStyle, marginTop: designTokens.space[5] }}
      >
        {overviewCards.map((card) => (
          <KpiCard
            key={card.key}
            label={card.label}
            value={card.value}
            unit={card.unit}
            detail={card.detail}
            valueVariant={card.valueVariant}
          />
        ))}
      </div>
    </>
  );
}
