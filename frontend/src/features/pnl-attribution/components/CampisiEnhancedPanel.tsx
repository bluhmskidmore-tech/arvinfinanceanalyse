import type { CampisiEnhancedPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { EM_DASH } from "../../../utils/format";
import { buildMetricCards } from "./campisiEnhancedPanelSupport";
import "./campisiPanels.css";

// 本面板挂在 Nocturne 深色路由（theme-dh-api + pnl-attribution scope）下：
// 布局与面色收敛到共享 campisiPanels.css（--dh-api-* var 链），禁止浅色 hex、
// designTokens 浅色 neutral 或 --ib-*（路由边界已算成钢蓝字面值）直灌。

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
      <div className="campisi-panel">
        <p className="campisi-panel__intro">
          {isFormalBridge
            ? "formal-bridge 路径：凸性、交叉项与再投资不在本路径拆分，其贡献并入「剩余/选券」，三张卡以 — 标注未拆分；其余分量之和仍等于总收益。"
            : "将凸性、交叉项与再投资从选券残差中拆出，保留扩展归因的总量与资产类别分布。"}
        </p>
        {data?.decomposition_basis ? (
          <div
            data-testid="campisi-enhanced-decomposition-basis"
            className="campisi-panel__note"
          >
            分解口径：{data.decomposition_basis}
          </div>
        ) : null}
        <div className="campisi-metric-grid">
          {metricCards.map(({ key, label, value, notDecomposed }) => (
            <div key={key} className="campisi-metric">
              <div className="campisi-field-label">{label}</div>
              <div
                data-testid={`campisi-enhanced-amount-${key}`}
                className="campisi-field-value"
              >
                {notDecomposed || value === undefined ? EM_DASH : `${toYi(Number(value))} 亿`}
              </div>
              {notDecomposed ? (
                <div
                  data-testid={`campisi-enhanced-not-decomposed-${key}`}
                  title={NOT_DECOMPOSED_HINT}
                  className="campisi-metric__flag"
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
