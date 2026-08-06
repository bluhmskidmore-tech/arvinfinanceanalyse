import type { ReactNode } from "react";

import type {
  MacroBondLinkageEnvironmentScore,
  MacroBondLinkageMethodVariant,
  MacroBondLinkagePayload,
  MacroBondResearchView,
  MacroBondTransmissionAxis,
} from "../../../api/contracts";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { MarketDataSeriesCategoryCard } from "./MarketDataSeriesCategoryCard";

type MarketDataLinkageBusinessDetailProps = {
  payload: MacroBondLinkagePayload;
};

const EMPTY_VALUE = "—";
const FIELD_LABELS: Record<string, string> = {
  category: "类别",
  alignment_mode: "对齐方式",
  lead_lag_days: "领先滞后天数",
  normalized_signal: "标准化信号",
  observation_count: "观察数",
  sample_size: "样本数",
  scoring_method: "评分方法",
  series_id: "序列 ID",
  series_name: "序列名称",
  window_start: "窗口起始",
  window_end: "窗口结束",
  start_value: "起始值",
  latest_value: "最新值",
  delta: "变动",
  direction: "方向",
  contribution: "贡献",
  description: "说明",
  evidence: "证据",
  note: "备注",
  score: "分数",
  signal: "信号",
  source: "来源",
  tags: "标签",
  target: "目标",
  tenor: "期限",
  value: "值",
  warnings: "预警",
  weight: "权重",
  winsorized: "已缩尾",
};

function formatValue(value: string | number | null | undefined, suffix = "") {
  if (value == null || value === "") return EMPTY_VALUE;
  const formatted = typeof value === "number" && !Number.isInteger(value)
    ? value.toFixed(4).replace(/\.?0+$/, "")
    : String(value);
  return `${formatted}${suffix}`;
}

function formatLabel(key: string) {
  return FIELD_LABELS[key] ?? key
    .split("_")
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function DetailTable({
  children,
  testId,
}: {
  children: ReactNode;
  testId?: string;
}) {
  return (
    <div className="market-data-detail-deck__scroll-panel">
      <table className="market-data-tushare-table" data-testid={testId}>
        {children}
      </table>
    </div>
  );
}

function renderList(values: readonly string[] | null | undefined) {
  if (!values || values.length === 0) return <span>{EMPTY_VALUE}</span>;
  return (
    <ul className="market-data-detail-deck__compact-list">
      {values.map((value) => (
        <li key={value}>{value}</li>
      ))}
    </ul>
  );
}

function renderUnknown(value: unknown): ReactNode {
  if (value == null) return EMPTY_VALUE;
  if (Array.isArray(value)) {
    if (value.length === 0) return EMPTY_VALUE;
    return (
      <ul className="market-data-detail-deck__compact-list">
        {value.map((item, index) => (
          <li key={`${index}-${typeof item === "object" ? "object" : String(item)}`}>{renderUnknown(item)}</li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return EMPTY_VALUE;
    return (
      <dl className="market-data-detail-deck__definition-grid">
        {entries.map(([key, nestedValue]) => (
          <div key={key}>
            <dt>{formatLabel(key)}</dt>
            <dd>{renderUnknown(nestedValue)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  if (typeof value === "number") return formatValue(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function EnvironmentSummary({ environmentScore }: { environmentScore: Partial<MacroBondLinkageEnvironmentScore> }) {
  return (
    <DetailTable>
      <tbody>
        <tr>
          <th scope="row">业务日期</th>
          <td>{formatValue(environmentScore.report_date)}</td>
        </tr>
        <tr>
          <th scope="row">利率方向</th>
          <td>{formatValue(environmentScore.rate_direction)}</td>
        </tr>
        <tr>
          <th scope="row">利率方向分</th>
          <td style={tabularNumsStyle}>{formatValue(environmentScore.rate_direction_score)}</td>
        </tr>
        <tr>
          <th scope="row">流动性分</th>
          <td style={tabularNumsStyle}>{formatValue(environmentScore.liquidity_score)}</td>
        </tr>
        <tr>
          <th scope="row">增长分</th>
          <td style={tabularNumsStyle}>{formatValue(environmentScore.growth_score)}</td>
        </tr>
        <tr>
          <th scope="row">通胀分</th>
          <td style={tabularNumsStyle}>{formatValue(environmentScore.inflation_score)}</td>
        </tr>
        <tr>
          <th scope="row">综合分</th>
          <td style={tabularNumsStyle}>{formatValue(environmentScore.composite_score)}</td>
        </tr>
        <tr>
          <th scope="row">综合公式版本</th>
          <td>{formatValue(environmentScore.composite_formula_version)}</td>
        </tr>
        <tr>
          <th scope="row">信号说明</th>
          <td>{formatValue(environmentScore.signal_description)}</td>
        </tr>
      </tbody>
    </DetailTable>
  );
}

function ContributionTable({
  contributions,
}: {
  contributions: NonNullable<MacroBondLinkageEnvironmentScore["composite_contributions"]>;
}) {
  if (contributions.length === 0) return <p>{EMPTY_VALUE}</p>;
  return (
    <DetailTable testId="market-data-detail-linkage-composite-contributions">
      <thead>
        <tr>
          <th scope="col">分项</th>
          <th scope="col">原始分</th>
          <th scope="col">权重</th>
          <th scope="col">带符号贡献</th>
        </tr>
      </thead>
      <tbody>
        {contributions.map((contribution) => (
          <tr key={contribution.component}>
            <td>{contribution.component}</td>
            <td style={tabularNumsStyle}>{formatValue(contribution.raw_score)}</td>
            <td style={tabularNumsStyle}>{formatValue(contribution.weight)}</td>
            <td style={tabularNumsStyle}>{formatValue(contribution.signed_contribution)}</td>
          </tr>
        ))}
      </tbody>
    </DetailTable>
  );
}

function FactorList({
  factors,
}: {
  factors: NonNullable<MacroBondLinkageEnvironmentScore["contributing_factors"]>;
}) {
  if (factors.length === 0) return <p>{EMPTY_VALUE}</p>;
  return (
    <div
      className="market-data-detail-deck__stack"
      data-testid="market-data-detail-linkage-contributing-factors"
    >
      {factors.map((factor, index) => (
        <section className="market-data-detail-deck__group-card" key={`factor-${index}`}>
          <header>
            <strong>因子 {index + 1}</strong>
            <em>
              {typeof factor.series_name === "string"
                ? factor.series_name
                : typeof factor.category === "string"
                  ? factor.category
                  : EMPTY_VALUE}
            </em>
          </header>
          {renderUnknown(factor)}
        </section>
      ))}
    </div>
  );
}

function VariantMeta({
  variantKey,
  variant,
}: {
  variantKey: "conservative" | "market_timing";
  variant: MacroBondLinkageMethodVariant | undefined;
}) {
  return (
    <section className="market-data-detail-deck__group-card">
      <h4>{variantKey === "conservative" ? "保守对齐" : "市场时点"}</h4>
      <DetailTable>
        <tbody>
          <tr>
            <th scope="row">变体</th>
            <td>{formatValue(variant?.method_meta.variant)}</td>
          </tr>
          <tr>
            <th scope="row">说明</th>
            <td>{formatValue(variant?.method_meta.description)}</td>
          </tr>
          <tr>
            <th scope="row">预警</th>
            <td>{renderList(variant?.method_meta.warnings)}</td>
          </tr>
        </tbody>
      </DetailTable>
    </section>
  );
}

function ResearchViewsTable({ views }: { views: readonly MacroBondResearchView[] | undefined }) {
  if (!views || views.length === 0) return <p>{EMPTY_VALUE}</p>;
  return (
    <DetailTable testId="market-data-detail-linkage-research-views-table">
      <thead>
        <tr>
          <th scope="col">视图</th>
          <th scope="col">状态</th>
          <th scope="col">立场</th>
          <th scope="col">置信度</th>
          <th scope="col">摘要</th>
          <th scope="col">影响标的</th>
          <th scope="col">证据</th>
        </tr>
      </thead>
      <tbody>
        {views.map((view) => (
          <tr key={view.key}>
            <td>{view.key}</td>
            <td>{view.status}</td>
            <td>{view.stance}</td>
            <td>{view.confidence}</td>
            <td>{view.summary}</td>
            <td>{view.affected_targets?.length ? view.affected_targets.join(", ") : EMPTY_VALUE}</td>
            <td>{view.evidence?.length ? view.evidence.join(", ") : EMPTY_VALUE}</td>
          </tr>
        ))}
      </tbody>
    </DetailTable>
  );
}

function TransmissionAxesTable({ axes }: { axes: readonly MacroBondTransmissionAxis[] | undefined }) {
  if (!axes || axes.length === 0) return <p>{EMPTY_VALUE}</p>;
  return (
    <DetailTable testId="market-data-detail-linkage-transmission-axes-table">
      <thead>
        <tr>
          <th scope="col">传导轴</th>
          <th scope="col">状态</th>
          <th scope="col">立场</th>
          <th scope="col">摘要</th>
          <th scope="col">影响视图</th>
          <th scope="col">所需序列</th>
          <th scope="col">预警</th>
        </tr>
      </thead>
      <tbody>
        {axes.map((axis) => (
          <tr key={axis.axis_key}>
            <td>{axis.axis_key}</td>
            <td>{axis.status}</td>
            <td>{axis.stance}</td>
            <td>{axis.summary}</td>
            <td>{axis.impacted_views?.length ? axis.impacted_views.join(", ") : EMPTY_VALUE}</td>
            <td>{axis.required_series_ids?.length ? axis.required_series_ids.join(", ") : EMPTY_VALUE}</td>
            <td>{axis.warnings?.length ? axis.warnings.join(", ") : EMPTY_VALUE}</td>
          </tr>
        ))}
      </tbody>
    </DetailTable>
  );
}

export function MarketDataLinkageBusinessDetail({ payload }: MarketDataLinkageBusinessDetailProps) {
  const environmentScore = payload.environment_score ?? {};
  const portfolioImpact = payload.portfolio_impact ?? {};

  return (
    <MarketDataSeriesCategoryCard
      title="宏债联动业务细项"
      caption={`${payload.report_date} · 计算于 ${payload.computed_at}`}
      tone="analytical"
      testId="market-data-detail-linkage-business"
      showLinkTierTag={false}
    >
      <div className="market-data-detail-deck__stack">
        <section
          className="market-data-detail-deck__group-card"
          data-testid="market-data-detail-linkage-environment"
        >
          <h4>环境评分</h4>
          <EnvironmentSummary environmentScore={environmentScore} />
          <h5>综合分贡献</h5>
          <ContributionTable contributions={environmentScore.composite_contributions ?? []} />
          <h5>贡献因子</h5>
          <FactorList factors={environmentScore.contributing_factors ?? []} />
          <h5>环境预警</h5>
          <div data-testid="market-data-detail-linkage-environment-warnings">
            {renderList(environmentScore.warnings)}
          </div>
        </section>

        <section
          className="market-data-detail-deck__group-card"
          data-testid="market-data-detail-linkage-portfolio-impact"
        >
          <h4>组合影响</h4>
          <DetailTable>
            <tbody>
              <tr>
                <th scope="row">估算利率变化</th>
                <td style={tabularNumsStyle}>{formatValue(portfolioImpact.estimated_rate_change_bps, " bps")}</td>
              </tr>
              <tr>
                <th scope="row">估算利差走阔</th>
                <td style={tabularNumsStyle}>
                  {formatValue(portfolioImpact.estimated_spread_widening_bps, " bps")}
                </td>
              </tr>
              <tr>
                <th scope="row">估算利率 PnL 影响</th>
                <td style={tabularNumsStyle}>{formatValue(portfolioImpact.estimated_rate_pnl_impact)}</td>
              </tr>
              <tr>
                <th scope="row">估算利差 PnL 影响</th>
                <td style={tabularNumsStyle}>{formatValue(portfolioImpact.estimated_spread_pnl_impact)}</td>
              </tr>
              <tr>
                <th scope="row">估算总影响</th>
                <td style={tabularNumsStyle}>{formatValue(portfolioImpact.total_estimated_impact)}</td>
              </tr>
              <tr>
                <th scope="row">相对市值影响率</th>
                <td style={tabularNumsStyle}>{formatValue(portfolioImpact.impact_ratio_to_market_value)}</td>
              </tr>
            </tbody>
          </DetailTable>
        </section>

        <section
          className="market-data-detail-deck__group-card"
          data-testid="market-data-detail-linkage-method-variants"
        >
          <h4>方法变体</h4>
          <VariantMeta variantKey="conservative" variant={payload.method_variants?.conservative} />
          <VariantMeta variantKey="market_timing" variant={payload.method_variants?.market_timing} />
        </section>

        <section
          className="market-data-detail-deck__group-card"
          data-testid="market-data-detail-linkage-research-views"
        >
          <h4>研究视图</h4>
          <ResearchViewsTable views={payload.research_views} />
        </section>

        <section
          className="market-data-detail-deck__group-card"
          data-testid="market-data-detail-linkage-transmission-axes"
        >
          <h4>传导轴</h4>
          <TransmissionAxesTable axes={payload.transmission_axes} />
        </section>

        <section
          className="market-data-detail-deck__group-card"
          data-testid="market-data-detail-linkage-warnings"
        >
          <h4>业务预警</h4>
          {renderList(payload.warnings)}
        </section>
      </div>
    </MarketDataSeriesCategoryCard>
  );
}
