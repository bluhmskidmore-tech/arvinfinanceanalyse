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

function formatOverviewNumber(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined || raw === "") return "—";
  const n = Number.parseFloat(String(raw).replace(/,/g, ""));
  if (!Number.isFinite(n)) return String(raw);
  return n.toLocaleString("zh-CN");
}

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
      value: formatOverviewNumber(overview?.total_market_value_amount),
      detail: "overview.total_market_value_amount · formal",
      valueVariant: "text" as const,
    },
    {
      key: "total-amortized-cost",
      label: "摊余成本合计",
      value: formatOverviewNumber(overview?.total_amortized_cost_amount),
      detail: "overview.total_amortized_cost_amount · formal",
      valueVariant: "text" as const,
    },
    {
      key: "total-accrued-interest",
      label: "应计利息合计",
      value: formatOverviewNumber(overview?.total_accrued_interest_amount),
      detail: "overview.total_accrued_interest_amount · formal",
      valueVariant: "text" as const,
    },
    {
      key: "summary-rows",
      label: "汇总行数",
      value: String(overview?.summary_row_count ?? "—"),
      detail: "overview.summary_row_count · formal",
      valueVariant: "text" as const,
    },
    {
      key: "detail-rows",
      label: "明细行数",
      value: String(overview?.detail_row_count ?? "—"),
      detail: "overview.detail_row_count · formal",
      valueVariant: "text" as const,
    },
    ...(workbook?.cards ?? []).map((card) => ({
      key: `workbook-card-${card.key}`,
      label: card.label,
      value: formatOverviewNumber(card.value),
      detail: `${card.note ?? "workbook.cards"} · workbook`,
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
              Formal Snapshot
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
              {formatCurrencyBasisLabel(overview?.currency_basis ?? currencyBasis)}。如果 fallback、quality 或
              governed 信号异常，优先进入下方正式汇总驾驶舱和右侧治理栏核对，而不是依赖 analytical 衍生结论。
            </p>
          </div>

          <div style={heroMetaRowStyle}>
            {(
              [
                {
                  label: `basis ${overviewMeta?.basis ?? "—"}`,
                  tone: overviewMeta?.basis === "formal" ? "positive" : "neutral",
                },
                {
                  label: `formal_use_allowed ${String(overviewMeta?.formal_use_allowed ?? "—")}`,
                  tone: overviewMeta?.formal_use_allowed ? "positive" : "warning",
                },
                {
                  label: `quality ${overviewMeta?.quality_flag ?? "—"}`,
                  tone: overviewMeta?.quality_flag === "ok" ? "positive" : "warning",
                },
                {
                  label: `fallback ${overviewMeta?.fallback_mode ?? "—"}`,
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
                summary rows，决定首轮汇总阅读范围
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
                detail rows，下钻时再进入明细接口
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
                workbook.cards，保留业务语义更强的正式摘要
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
              Governed Signals
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
              这里不重算风险和利差，只把 decision_items、risk_alerts、event_calendar 的现有 governed 信号提到前面。
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
            detail={card.detail}
            valueVariant={card.valueVariant}
          />
        ))}
      </div>
    </>
  );
}
