import type {
  CampisiDecisionComponents,
  CampisiDecisionEffectKey,
  CampisiDecisionGradePayload,
  CampisiDecisionWindowDeclaration,
} from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { EM_DASH } from "../../../utils/format";
import { formatYi } from "./pnlAttributionViewModel";
import "./campisiPanels.css";

// 本面板挂在 Nocturne 深色路由（theme-dh-api + pnl-attribution scope）下：
// 布局与面色收敛到共享 campisiPanels.css（--dh-api-* var 链），盈亏语义色经
// data-tone 属性映射（绿涨红跌，与 TONE_DH_CSS_VAR 同源）；禁止浅色 hex 或
// --ib-*（路由边界被算成钢蓝字面值）直灌。

const COMPONENT_ORDER: Array<[CampisiDecisionEffectKey, string]> = [
  ["carry", "票息/Carry"],
  ["rate_level_effect", "利率水平"],
  ["curve_shape_effect", "曲线形态"],
  ["credit_spread_effect", "信用利差"],
  ["convexity_effect", "凸性"],
  ["realized_trading", "已实现交易"],
  ["manual_adjustment", "手工调整"],
  ["selection_proxy", "剩余/选券代理"],
  ["residual_noise", "残差/噪音"],
];

type Props = {
  data: CampisiDecisionGradePayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

function formatPct(value: number | null): string {
  if (value === null) {
    return EM_DASH;
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatWindowLabel(window: CampisiDecisionWindowDeclaration | undefined): string {
  if (!window) {
    return EM_DASH;
  }
  return `${window.start} 至 ${window.end}（${window.kind}）`;
}

/** 盈亏语义 data-tone：正→绿、负→红、零→中性（CSS 侧映射色值）。 */
function effectTone(value: number): "positive" | "negative" | "neutral" {
  if (value > 0) {
    return "positive";
  }
  if (value < 0) {
    return "negative";
  }
  return "neutral";
}

function effectLabel(data: CampisiDecisionGradePayload): string {
  const key = data.summary.main_driver;
  const row = data.effects.find((effect) => effect.key === key);
  if (row) {
    return row.label;
  }
  return COMPONENT_ORDER.find(([effectKey]) => effectKey === key)?.[1] ?? "未识别来源";
}

function conclusionVerb(value: number): string {
  if (value > 0) {
    return "赚";
  }
  if (value < 0) {
    return "亏";
  }
  return "持平";
}

function renderComponents(components: CampisiDecisionComponents) {
  return (
    <table className="campisi-table campisi-table--spaced">
      <thead>
        <tr>
          <th>来源</th>
          <th className="campisi-table__numeric-head">金额</th>
        </tr>
      </thead>
      <tbody>
        {COMPONENT_ORDER.map(([key, label]) => (
          <tr key={key}>
            <td>{label}</td>
            <td
              className="campisi-table__numeric-cell"
              data-tone={effectTone(components[key])}
            >
              {formatYi(components[key])}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CampisiDecisionGradePanel({ data, state, onRetry }: Props) {
  return (
    <PageDataSection title="Campisi 决策级解释" state={state} onRetry={onRetry}>
      {data ? (
        <div>
          <div data-testid="campisi-decision-headline" className="campisi-panel">
            <div className="campisi-field-label">
              {data.period_start} 至 {data.period_end}
            </div>
            <div className="campisi-headline">
              本期{conclusionVerb(data.summary.formal_actual_pnl)} {formatYi(data.summary.formal_actual_pnl)}，
              主要来自 {effectLabel(data)}。
            </div>
            <div className="campisi-chip-row">
              <span className="campisi-chip">票息不等于主动能力</span>
              <span className="campisi-chip">残差不算能力</span>
              <span className="campisi-chip">剩余/选券只作为代理指标</span>
            </div>
            <div
              data-testid="campisi-decision-window-context"
              className="campisi-kv-grid campisi-kv-grid--spaced"
            >
              <div>
                <div className="campisi-field-label">PnL 窗口</div>
                <div className="campisi-field-value">{formatWindowLabel(data.pnl_window)}</div>
              </div>
              <div>
                <div className="campisi-field-label">曲线窗口</div>
                <div className="campisi-field-value">{formatWindowLabel(data.curve_window)}</div>
              </div>
            </div>
            {data.window_disclosure ? (
              <div
                data-testid="campisi-decision-window-disclosure"
                className="campisi-disclosure"
                data-level={data.window_disclosure.level}
              >
                {data.window_disclosure.message}
              </div>
            ) : null}
          </div>

          <div className="campisi-view-grid">
            <div data-testid="campisi-decision-formal-view" className="campisi-panel">
              <h3 className="campisi-panel__heading">正式 PnL 视图</h3>
              <div className="campisi-kv-grid">
                <div>
                  <div className="campisi-field-label">正式 PnL</div>
                  <div className="campisi-field-value">{formatYi(data.formal_pnl_view.total_actual_pnl)}</div>
                </div>
                <div>
                  <div className="campisi-field-label">解释合计</div>
                  <div className="campisi-field-value">{formatYi(data.formal_pnl_view.explained_pnl)}</div>
                </div>
                <div>
                  <div className="campisi-field-label">闭合差异</div>
                  <div className="campisi-field-value">{formatYi(data.formal_pnl_view.closure.difference)}</div>
                </div>
                <div>
                  <div className="campisi-field-label">残差占比</div>
                  <div className="campisi-field-value">{formatPct(data.summary.residual_ratio)}</div>
                </div>
              </div>
              {renderComponents(data.formal_pnl_view.components)}
            </div>

            <div data-testid="campisi-decision-valuation-view" className="campisi-panel">
              <h3 className="campisi-panel__heading">估值 / OCI 视图</h3>
              <div className="campisi-kv-grid">
                <div>
                  <div className="campisi-field-label">516 合计</div>
                  <div className="campisi-field-value">{formatYi(data.valuation_oci_view.total_valuation_change_516)}</div>
                </div>
                <div>
                  <div className="campisi-field-label">FVOCI</div>
                  <div className="campisi-field-value">{formatYi(data.valuation_oci_view.fvoci_valuation_change_516)}</div>
                </div>
                <div>
                  <div className="campisi-field-label">FVTPL</div>
                  <div className="campisi-field-value">{formatYi(data.valuation_oci_view.fvtpl_valuation_change_516)}</div>
                </div>
              </div>
              <table className="campisi-table campisi-table--spaced">
                <thead>
                  <tr>
                    <th>会计分类</th>
                    <th className="campisi-table__numeric-head">正式 PnL</th>
                    <th className="campisi-table__numeric-head">516 / OCI</th>
                  </tr>
                </thead>
                <tbody>
                  {data.valuation_oci_view.rows_by_accounting_basis.map((row) => (
                    <tr key={row.accounting_basis}>
                      <td>{row.accounting_basis}</td>
                      <td className="campisi-table__numeric-cell">{formatYi(row.formal_pnl)}</td>
                      <td className="campisi-table__numeric-cell">{formatYi(row.valuation_or_oci_516)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="campisi-panel__footnote">
                {data.valuation_oci_view.reinvestment.message}
              </p>
            </div>
          </div>

          {data.ability_matrix.length ? (
            <div className="campisi-panel campisi-panel--stacked">
              <h3 className="campisi-panel__heading">组合/成本中心代理维度</h3>
              <table className="campisi-table campisi-table--spaced">
                <thead>
                  <tr>
                    <th>组合</th>
                    <th>成本中心</th>
                    <th className="campisi-table__numeric-head">市场 beta</th>
                    <th className="campisi-table__numeric-head">策略代理</th>
                    <th className="campisi-table__numeric-head">剩余/选券代理</th>
                    <th className="campisi-table__numeric-head">残差</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ability_matrix.map((row) => (
                    <tr key={`${row.portfolio_name}-${row.cost_center}`}>
                      <td>{row.portfolio_name}</td>
                      <td>{row.cost_center}</td>
                      <td className="campisi-table__numeric-cell">{formatYi(row.market_beta)}</td>
                      <td className="campisi-table__numeric-cell">{formatYi(row.strategy_proxy)}</td>
                      <td className="campisi-table__numeric-cell">{formatYi(row.selection_proxy)}</td>
                      <td className="campisi-table__numeric-cell">{formatYi(row.residual_noise)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </PageDataSection>
  );
}
