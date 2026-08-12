import type { CampisiEnhancedPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";

const cardStyle = {
  padding: designTokens.space[5],
  borderRadius: designTokens.radius.sm,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: designTokens.color.cockpit.white,
  boxShadow: "0 1px 2px rgba(31, 41, 55, 0.04)",
} as const;

function toYi(value: number) {
  return (value / 100_000_000).toFixed(2);
}

type MetricCard = {
  label: string;
  value: number | undefined;
}

type Props = {
  data: CampisiEnhancedPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

function buildMetricCards(totals: CampisiEnhancedPayload["totals"] | undefined): MetricCard[] {
  const hasBridgeDetails =
    totals?.realized_trading !== undefined ||
    totals?.manual_adjustment !== undefined ||
    totals?.fx_translation !== undefined;
  const cards: MetricCard[] = [
    { label: "票息", value: totals?.income_return },
    { label: "国债曲线", value: totals?.treasury_effect },
    { label: "利差", value: totals?.spread_effect },
  ];
  if (hasBridgeDetails) {
    cards.push(
      { label: "已实现交易", value: totals?.realized_trading },
      { label: "手工调整", value: totals?.manual_adjustment },
      { label: "汇兑", value: totals?.fx_translation },
    );
  }
  cards.push(
    { label: "凸性", value: totals?.convexity_effect },
    { label: "交叉项", value: totals?.cross_effect },
    { label: "再投资", value: totals?.reinvestment_effect },
    { label: "剩余/选券", value: totals?.selection_effect },
    { label: "总收益", value: totals?.total_return },
  );
  return cards;
}

/** 前端独立加总：展示分量（不含总收益）之和，供契约闭合断言。 */
export function sumCampisiEnhancedDisplayAmounts(
  totals: CampisiEnhancedPayload["totals"] | undefined,
): number | null {
  if (!totals) {
    return null;
  }
  const cards = buildMetricCards(totals).filter((card) => card.label !== "总收益");
  let sum = 0;
  for (const card of cards) {
    if (typeof card.value !== "number" || !Number.isFinite(card.value)) {
      return null;
    }
    sum += card.value;
  }
  return sum;
}

export function CampisiEnhancedPanel({ data, state, onRetry }: Props) {
  const totals = data?.totals;
  const metricCards = buildMetricCards(totals);

  return (
    <PageDataSection
      title="Campisi 六效应归因（扩展）"
      state={state}
      onRetry={onRetry}
    >
      <div style={cardStyle}>
        <p
          style={{
            margin: `0 0 ${designTokens.space[4]}px`,
            fontSize: designTokens.fontSize[13],
            color: designTokens.color.neutral[700],
            lineHeight: designTokens.lineHeight.normal,
          }}
        >
          将凸性、交叉项与再投资从选券残差中拆出，保留扩展归因的总量与资产类别分布。
        </p>
        {data?.decomposition_basis ? (
          <div
            data-testid="campisi-enhanced-decomposition-basis"
            style={{
              marginBottom: designTokens.space[4],
              padding: `${designTokens.space[3]}px ${designTokens.space[4]}px`,
              borderRadius: designTokens.radius.md,
              border: `1px solid ${designTokens.color.neutral[200]}`,
              background: "#fffdf7",
              color: designTokens.color.neutral[700],
              fontSize: designTokens.fontSize[12],
              lineHeight: designTokens.lineHeight.normal,
            }}
          >
            分解口径：{data.decomposition_basis}
          </div>
        ) : null}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: designTokens.space[3],
          }}
        >
          {metricCards.map(({ label, value }) => (
            <div
              key={label}
              style={{
                padding: designTokens.space[3],
                borderRadius: designTokens.radius.md,
                background: designTokens.color.neutral[50],
              }}
            >
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: designTokens.color.neutral[700],
                }}
              >
                {label}
              </div>
              <div
                style={{
                  marginTop: designTokens.space[2],
                  fontWeight: 700,
                  color: designTokens.color.neutral[900],
                  ...tabularNumsStyle,
                }}
              >
                {value === undefined ? EM_DASH : `${toYi(Number(value))} 亿`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageDataSection>
  );
}
