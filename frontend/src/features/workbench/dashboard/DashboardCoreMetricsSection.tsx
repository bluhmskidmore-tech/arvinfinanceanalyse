import { Card, Skeleton, Tag, Typography } from "antd";
import type { UseQueryResult } from "@tanstack/react-query";

import type { CoreMetricsCardData, CoreMetricsPayload } from "../../../api/contracts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";

import "./DashboardWorkbenchMetricSections.css";

function numericToneCss(raw: number | null): string {
  if (raw === null || Number.isNaN(raw)) {
    return shellTokens.colorTextSecondary;
  }
  if (raw > 0) {
    return designTokens.color.semantic.profit;
  }
  if (raw < 0) {
    return designTokens.color.semantic.loss;
  }
  return shellTokens.colorTextPrimary;
}

const CARD_KEYS: ReadonlyArray<{
  key: keyof Pick<CoreMetricsPayload["result"], "bond_investments" | "interbank_assets" | "interbank_liabilities">;
  label: string;
}> = [
  { key: "bond_investments", label: "债券投资" },
  { key: "interbank_assets", label: "同业资产" },
  { key: "interbank_liabilities", label: "同业负债" },
];

function CoreMetricsCard({ title, data }: { title: string; data: CoreMetricsCardData }) {
  return (
    <Card size="small" className="dashboard-core-metric-card">
      <div className="dashboard-core-metrics__card-title">
        <Typography.Text strong className="dashboard-core-metrics__card-label">
          {title}
        </Typography.Text>
      </div>
      <div className="dashboard-core-metric-amount" style={tabularNumsStyle}>
        {data.total_amount.display}
      </div>
      <div className="dashboard-core-metric-rate-line">
        利率 <span style={tabularNumsStyle}>{data.weighted_avg_rate.display}</span>
      </div>
      <div className="dashboard-core-metric-change-row" style={tabularNumsStyle}>
        <span style={{ color: numericToneCss(data.change_amount.raw) }}>{data.change_amount.display}</span>{" "}
        <span style={{ color: numericToneCss(data.change_pct.raw) }}>（{data.change_pct.display}）</span>
      </div>
      <Typography.Text type="secondary" className="dashboard-core-metric-caption">
        Top 明细
      </Typography.Text>
      <ul className="dashboard-core-metric-detail-list">
        {data.top_3_details.slice(0, 3).map((row) => (
          <li key={`${title}-${row.name}`}>
            {row.name} · {row.amount} · {row.rate}
          </li>
        ))}
      </ul>
    </Card>
  );
}

type Props = {
  query: UseQueryResult<CoreMetricsPayload>;
  reportDate: string;
};

export function DashboardCoreMetricsSection({ query, reportDate }: Props) {
  const meta = query.data?.result_meta;
  const showQualityBadge = meta && meta.quality_flag !== "ok";

  return (
    <section
      data-testid="dashboard-core-metrics-section"
      className="dashboard-home-panel dashboard-metric-shell"
    >
      <header className="dashboard-metric-header">
        <span className="dashboard-home-section-eyebrow dashboard-metric-eyebrow-label">核心规模</span>
        <div className="dashboard-metric-title-row">
          <h2 className="dashboard-business-balance-summary__title dashboard-metric-section-title">
            债券 / 同业核心指标
          </h2>
          {reportDate.trim() ? (
            <Typography.Text type="secondary" className="dashboard-metric-date-caption">
              所选报告日：{reportDate.trim()}
            </Typography.Text>
          ) : null}
          {showQualityBadge ? (
            <Tag color="orange" data-testid="dashboard-core-metrics-quality-badge">
              质量：非 ok（{meta.quality_flag}）
            </Tag>
          ) : null}
        </div>
        <p className="dashboard-home-muted dashboard-muted-line">金额与变动均由后端返回，前端仅排版展示。</p>
      </header>

      {query.isLoading ? (
        <div data-testid="dashboard-core-metrics-skeleton">
          <Skeleton active paragraph={{ rows: 3 }} />
        </div>
      ) : query.isError ? (
        <Typography.Text type="danger">数据暂不可用</Typography.Text>
      ) : query.data ? (
        <>
          {!query.data.result.report_date.trim() ? (
            <Typography.Text type="secondary">暂无报告日</Typography.Text>
          ) : null}
          <div className="dashboard-core-metrics__grid">
            {CARD_KEYS.map(({ key, label }) => (
              <CoreMetricsCard key={key} title={label} data={query.data!.result[key]} />
            ))}
          </div>
        </>
      ) : (
        <Typography.Text type="secondary">暂无数据</Typography.Text>
      )}
    </section>
  );
}
