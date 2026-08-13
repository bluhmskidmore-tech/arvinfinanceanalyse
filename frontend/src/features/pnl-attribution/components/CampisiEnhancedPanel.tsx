import type { CampisiEnhancedPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { buildMetricCards } from "./campisiEnhancedPanelSupport";

// 本面板挂在 Nocturne 深色路由（theme-dh-api + pnl-attribution scope）下，
// 面色/文字一律走主题感知 CSS 变量（--dh-api-*），禁止浅色 hex、designTokens
// 浅色 neutral 或 --ib-*（路由边界已算成钢蓝字面值）直灌（迁法同
// CampisiAttributionPanel / CampisiDecisionGradePanel）。
const cardStyle = {
  padding: designTokens.space[5],
  borderRadius: "var(--dh-api-radius)",
  border: "1px solid var(--dh-api-line)",
  background: "var(--dh-api-panel)",
} as const;

function toYi(value: number) {
  return (value / 100_000_000).toFixed(2);
}

/** 后端 `basis`：formal-bridge 路径的判定依据，不靠数值形态猜。 */
const FORMAL_BRIDGE_BASIS = "formal_report_pnl_bridge";

const NOT_DECOMPOSED_BADGE_TEXT = "该路径不拆分";
const NOT_DECOMPOSED_HINT =
  "formal-bridge 一阶分解框架不产出该二阶项，金额为未拆分的 0，贡献并入「剩余/选券」。";

type Props = {
  data: CampisiEnhancedPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

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
            color: "var(--dh-api-soft)",
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
              borderRadius: "var(--dh-api-radius)",
              border: "1px solid var(--dh-api-line-soft)",
              background: "var(--dh-api-panel-2)",
              color: "var(--dh-api-soft)",
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
                borderRadius: "var(--dh-api-radius)",
                background: "var(--dh-api-panel-2)",
              }}
            >
              <div
                style={{
                  fontSize: designTokens.fontSize[12],
                  color: "var(--dh-api-muted)",
                }}
              >
                {label}
              </div>
              <div
                data-testid={`campisi-enhanced-amount-${key}`}
                style={{
                  marginTop: designTokens.space[2],
                  fontWeight: 700,
                  color: "var(--dh-api-ink)",
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
                    color: "var(--dh-api-muted)",
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
