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

/** 后端 `basis`：formal-bridge 路径的判定依据，不靠数值形态猜。 */
const FORMAL_BRIDGE_BASIS = "formal_report_pnl_bridge";

const NOT_DECOMPOSED_BADGE_TEXT = "该路径不拆分";
const NOT_DECOMPOSED_HINT =
  "formal-bridge 一阶分解框架不产出该二阶项，金额为未拆分的 0，贡献并入「剩余/选券」。";

type MetricCard = {
  key: string;
  label: string;
  value: number | undefined;
  /**
   * bridge 路径未拆分该效应。数值仍是精确 0 并继续参与闭合求和，只是不得以数字
   * 形式发布——"0.00 亿"会被读成"观测到二阶贡献为零"。
   */
  notDecomposed?: boolean;
}

type Props = {
  data: CampisiEnhancedPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

function buildMetricCards(
  totals: CampisiEnhancedPayload["totals"] | undefined,
  secondOrderNotDecomposed = false,
): MetricCard[] {
  const hasBridgeDetails =
    totals?.realized_trading !== undefined ||
    totals?.manual_adjustment !== undefined ||
    totals?.fx_translation !== undefined;
  const cards: MetricCard[] = [
    { key: "income_return", label: "票息", value: totals?.income_return },
    { key: "treasury_effect", label: "国债曲线", value: totals?.treasury_effect },
    { key: "spread_effect", label: "利差", value: totals?.spread_effect },
  ];
  if (hasBridgeDetails) {
    cards.push(
      { key: "realized_trading", label: "已实现交易", value: totals?.realized_trading },
      { key: "manual_adjustment", label: "手工调整", value: totals?.manual_adjustment },
      { key: "fx_translation", label: "汇兑", value: totals?.fx_translation },
    );
  }
  cards.push(
    {
      key: "convexity_effect",
      label: "凸性",
      value: totals?.convexity_effect,
      notDecomposed: secondOrderNotDecomposed,
    },
    {
      key: "cross_effect",
      label: "交叉项",
      value: totals?.cross_effect,
      notDecomposed: secondOrderNotDecomposed,
    },
    {
      key: "reinvestment_effect",
      label: "再投资",
      value: totals?.reinvestment_effect,
      notDecomposed: secondOrderNotDecomposed,
    },
    { key: "selection_effect", label: "剩余/选券", value: totals?.selection_effect },
    { key: "total_return", label: "总收益", value: totals?.total_return },
  );
  return cards;
}

/**
 * 前端独立加总：展示分量（不含总收益）之和，供契约闭合断言。
 *
 * 未拆分的效应只影响展示，不退出求和——把它当成缺失会让闭合断言退化成 null，
 * 而 bridge 路径恰恰是靠这个和等于 `total_return` 才能证明没有分量被吞掉。
 */
export function sumCampisiEnhancedDisplayAmounts(
  totals: CampisiEnhancedPayload["totals"] | undefined,
): number | null {
  if (!totals) {
    return null;
  }
  const cards = buildMetricCards(totals).filter((card) => card.key !== "total_return");
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
  const isFormalBridge = data?.basis === FORMAL_BRIDGE_BASIS;
  const metricCards = buildMetricCards(totals, isFormalBridge);

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
          {isFormalBridge
            ? "formal-bridge 路径：凸性、交叉项与再投资不在本路径拆分，其贡献并入「剩余/选券」，三张卡以 — 标注未拆分；其余分量之和仍等于总收益。"
            : "将凸性、交叉项与再投资从选券残差中拆出，保留扩展归因的总量与资产类别分布。"}
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
          {metricCards.map(({ key, label, value, notDecomposed }) => (
            <div
              key={key}
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
                data-testid={`campisi-enhanced-amount-${key}`}
                style={{
                  marginTop: designTokens.space[2],
                  fontWeight: 700,
                  color: designTokens.color.neutral[900],
                  ...tabularNumsStyle,
                }}
              >
                {notDecomposed || value === undefined ? EM_DASH : `${toYi(Number(value))} 亿`}
              </div>
              {notDecomposed ? (
                <div
                  data-testid={`campisi-enhanced-not-decomposed-${key}`}
                  title={NOT_DECOMPOSED_HINT}
                  style={{
                    marginTop: designTokens.space[1],
                    fontSize: designTokens.fontSize[11],
                    color: designTokens.color.neutral[700],
                  }}
                >
                  {NOT_DECOMPOSED_BADGE_TEXT}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </PageDataSection>
  );
}
