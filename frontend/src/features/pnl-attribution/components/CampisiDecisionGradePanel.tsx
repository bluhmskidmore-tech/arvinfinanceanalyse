import type {
  CampisiDecisionComponents,
  CampisiDecisionEffectKey,
  CampisiDecisionGradePayload,
} from "../../../api/contracts";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";

const CARD_STYLE = {
  padding: designTokens.space[5],
  borderRadius: designTokens.radius.sm,
  border: `1px solid ${designTokens.color.neutral[200]}`,
  background: "#ffffff",
  boxShadow: "0 1px 2px rgba(31, 41, 55, 0.04)",
} as const;

const GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
  gap: designTokens.space[4],
} as const;

const VIEW_GRID_STYLE = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: designTokens.space[4],
  marginTop: designTokens.space[4],
} as const;

const LABEL_STYLE = {
  fontSize: designTokens.fontSize[12],
  color: designTokens.color.neutral[600],
} as const;

const VALUE_STYLE = {
  marginTop: designTokens.space[2],
  fontWeight: 700,
  color: designTokens.color.neutral[900],
  ...tabularNumsStyle,
} as const;

const BOUNDARY_STYLE = {
  display: "flex",
  flexWrap: "wrap",
  gap: designTokens.space[2],
  marginTop: designTokens.space[4],
} as const;

const CHIP_STYLE = {
  padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
  borderRadius: 999,
  background: "#f8fafc",
  border: `1px solid ${designTokens.color.neutral[200]}`,
  color: designTokens.color.neutral[700],
  fontSize: designTokens.fontSize[12],
} as const;

const TABLE_STYLE = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: designTokens.fontSize[12],
} as const;

const TH_STYLE = {
  padding: `${designTokens.space[2]}px 0`,
  textAlign: "left",
  color: designTokens.color.neutral[600],
  borderBottom: `1px solid ${designTokens.color.neutral[200]}`,
} as const;

const TD_STYLE = {
  padding: `${designTokens.space[2]}px 0`,
  borderBottom: `1px solid ${designTokens.color.neutral[100]}`,
  color: designTokens.color.neutral[800],
} as const;

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

function formatYi(value: number): string {
  const amount = value / 100_000_000;
  return `${amount >= 0 ? "+" : ""}${amount.toFixed(2)} 亿`;
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function effectColor(value: number): string {
  if (value > 0) {
    return designTokens.color.semantic.profit;
  }
  if (value < 0) {
    return designTokens.color.semantic.loss;
  }
  return designTokens.color.neutral[600];
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
    <table style={TABLE_STYLE}>
      <thead>
        <tr>
          <th style={TH_STYLE}>来源</th>
          <th style={{ ...TH_STYLE, textAlign: "right" }}>金额</th>
        </tr>
      </thead>
      <tbody>
        {COMPONENT_ORDER.map(([key, label]) => (
          <tr key={key}>
            <td style={TD_STYLE}>{label}</td>
            <td style={{ ...TD_STYLE, textAlign: "right", color: effectColor(components[key]) }}>
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
    <DataSection title="Campisi 决策级解释" state={state} onRetry={onRetry}>
      {data ? (
        <div>
          <div data-testid="campisi-decision-headline" style={CARD_STYLE}>
            <div style={LABEL_STYLE}>
              {data.period_start} 至 {data.period_end}
            </div>
            <div style={{ marginTop: designTokens.space[2], fontSize: 18, fontWeight: 700 }}>
              本期{conclusionVerb(data.summary.formal_actual_pnl)} {formatYi(data.summary.formal_actual_pnl)}，
              主要来自 {effectLabel(data)}。
            </div>
            <div style={BOUNDARY_STYLE}>
              <span style={CHIP_STYLE}>票息不等于主动能力</span>
              <span style={CHIP_STYLE}>残差不算能力</span>
              <span style={CHIP_STYLE}>剩余/选券只作为代理指标</span>
            </div>
          </div>

          <div style={VIEW_GRID_STYLE}>
            <div data-testid="campisi-decision-formal-view" style={CARD_STYLE}>
              <h3 style={{ margin: 0, fontSize: 15 }}>正式 PnL 视图</h3>
              <div style={GRID_STYLE}>
                <div>
                  <div style={LABEL_STYLE}>正式 PnL</div>
                  <div style={VALUE_STYLE}>{formatYi(data.formal_pnl_view.total_actual_pnl)}</div>
                </div>
                <div>
                  <div style={LABEL_STYLE}>解释合计</div>
                  <div style={VALUE_STYLE}>{formatYi(data.formal_pnl_view.explained_pnl)}</div>
                </div>
                <div>
                  <div style={LABEL_STYLE}>闭合差异</div>
                  <div style={VALUE_STYLE}>{formatYi(data.formal_pnl_view.closure.difference)}</div>
                </div>
                <div>
                  <div style={LABEL_STYLE}>残差占比</div>
                  <div style={VALUE_STYLE}>{formatPct(data.summary.residual_ratio)}</div>
                </div>
              </div>
              <div style={{ marginTop: designTokens.space[4] }}>
                {renderComponents(data.formal_pnl_view.components)}
              </div>
            </div>

            <div data-testid="campisi-decision-valuation-view" style={CARD_STYLE}>
              <h3 style={{ margin: 0, fontSize: 15 }}>估值 / OCI 视图</h3>
              <div style={GRID_STYLE}>
                <div>
                  <div style={LABEL_STYLE}>516 合计</div>
                  <div style={VALUE_STYLE}>{formatYi(data.valuation_oci_view.total_valuation_change_516)}</div>
                </div>
                <div>
                  <div style={LABEL_STYLE}>FVOCI</div>
                  <div style={VALUE_STYLE}>{formatYi(data.valuation_oci_view.fvoci_valuation_change_516)}</div>
                </div>
                <div>
                  <div style={LABEL_STYLE}>FVTPL</div>
                  <div style={VALUE_STYLE}>{formatYi(data.valuation_oci_view.fvtpl_valuation_change_516)}</div>
                </div>
              </div>
              <table style={{ ...TABLE_STYLE, marginTop: designTokens.space[4] }}>
                <thead>
                  <tr>
                    <th style={TH_STYLE}>会计分类</th>
                    <th style={{ ...TH_STYLE, textAlign: "right" }}>正式 PnL</th>
                    <th style={{ ...TH_STYLE, textAlign: "right" }}>516 / OCI</th>
                  </tr>
                </thead>
                <tbody>
                  {data.valuation_oci_view.rows_by_accounting_basis.map((row) => (
                    <tr key={row.accounting_basis}>
                      <td style={TD_STYLE}>{row.accounting_basis}</td>
                      <td style={{ ...TD_STYLE, textAlign: "right" }}>{formatYi(row.formal_pnl)}</td>
                      <td style={{ ...TD_STYLE, textAlign: "right" }}>{formatYi(row.valuation_or_oci_516)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ margin: `${designTokens.space[4]}px 0 0`, color: designTokens.color.neutral[700] }}>
                {data.valuation_oci_view.reinvestment.message}
              </p>
            </div>
          </div>

          {data.ability_matrix.length ? (
            <div style={{ ...CARD_STYLE, marginTop: designTokens.space[4] }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>组合/成本中心代理维度</h3>
              <table style={{ ...TABLE_STYLE, marginTop: designTokens.space[3] }}>
                <thead>
                  <tr>
                    <th style={TH_STYLE}>组合</th>
                    <th style={TH_STYLE}>成本中心</th>
                    <th style={{ ...TH_STYLE, textAlign: "right" }}>市场 beta</th>
                    <th style={{ ...TH_STYLE, textAlign: "right" }}>策略代理</th>
                    <th style={{ ...TH_STYLE, textAlign: "right" }}>剩余/选券代理</th>
                    <th style={{ ...TH_STYLE, textAlign: "right" }}>残差</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ability_matrix.map((row) => (
                    <tr key={`${row.portfolio_name}-${row.cost_center}`}>
                      <td style={TD_STYLE}>{row.portfolio_name}</td>
                      <td style={TD_STYLE}>{row.cost_center}</td>
                      <td style={{ ...TD_STYLE, textAlign: "right" }}>{formatYi(row.market_beta)}</td>
                      <td style={{ ...TD_STYLE, textAlign: "right" }}>{formatYi(row.strategy_proxy)}</td>
                      <td style={{ ...TD_STYLE, textAlign: "right" }}>{formatYi(row.selection_proxy)}</td>
                      <td style={{ ...TD_STYLE, textAlign: "right" }}>{formatYi(row.residual_noise)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </DataSection>
  );
}
