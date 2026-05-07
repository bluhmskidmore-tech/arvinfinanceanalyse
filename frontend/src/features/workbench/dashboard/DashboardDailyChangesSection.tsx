import { Skeleton, Table, Tag, Typography } from "antd";
import type { UseQueryResult } from "@tanstack/react-query";

import type { DailyChangePeriod, DailyChangesPayload, Numeric } from "../../../api/contracts";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";

import "./DashboardWorkbenchMetricSections.css";

function cellColor(n: Numeric): string {
  const raw = n.raw;
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

const PERIOD_LABEL: Record<DailyChangePeriod["period"], string> = {
  day: "日",
  week: "周",
  month: "月",
};

type Props = {
  query: UseQueryResult<DailyChangesPayload>;
};

export function DashboardDailyChangesSection({ query }: Props) {
  const meta = query.data?.result_meta;
  const showQualityBadge = meta && meta.quality_flag !== "ok";

  return (
    <section
      data-testid="dashboard-daily-changes-section"
      className="dashboard-home-panel dashboard-metric-shell dashboard-metric-shell--spaced"
    >
      <header className="dashboard-metric-header">
        <span className="dashboard-home-section-eyebrow dashboard-metric-eyebrow-label">区间变动</span>
        <div className="dashboard-metric-title-row">
          <h2 className="dashboard-business-balance-summary__title dashboard-metric-section-title">
            日 / 周 / 月变动
          </h2>
          {query.data?.result.report_date.trim() ? (
            <Typography.Text type="secondary" className="dashboard-metric-date-caption">
              后端报告日：{query.data.result.report_date.trim()}
            </Typography.Text>
          ) : null}
          {showQualityBadge ? (
            <Tag color="orange" data-testid="dashboard-daily-changes-quality-badge">
              质量：非 ok（{meta.quality_flag}）
            </Tag>
          ) : null}
        </div>
      </header>

      {query.isLoading ? (
        <div data-testid="dashboard-daily-changes-skeleton">
          <Skeleton active paragraph={{ rows: 2 }} />
        </div>
      ) : query.isError ? (
        <Typography.Text type="danger">数据暂不可用</Typography.Text>
      ) : query.data ? (
        <Table<DailyChangePeriod>
          size="small"
          pagination={false}
          dataSource={[...query.data.result.periods].sort((a, b) => {
            const rank: DailyChangePeriod["period"][] = ["day", "week", "month"];
            return rank.indexOf(a.period) - rank.indexOf(b.period);
          })}
          rowKey={(row) => row.period}
          columns={[
            {
              title: "周期",
              dataIndex: "period",
              render: (p: DailyChangePeriod["period"]) => PERIOD_LABEL[p] ?? p,
            },
            {
              title: "债券投资",
              dataIndex: "bond_investments_change",
              align: "right",
              render: (n: Numeric) => (
                <span className="dashboard-daily-num" style={{ ...tabularNumsStyle, color: cellColor(n) }}>
                  {n.display}
                </span>
              ),
            },
            {
              title: "同业资产",
              dataIndex: "interbank_assets_change",
              align: "right",
              render: (n: Numeric) => (
                <span className="dashboard-daily-num" style={{ ...tabularNumsStyle, color: cellColor(n) }}>
                  {n.display}
                </span>
              ),
            },
            {
              title: "同业负债",
              dataIndex: "interbank_liabilities_change",
              align: "right",
              render: (n: Numeric) => (
                <span className="dashboard-daily-num" style={{ ...tabularNumsStyle, color: cellColor(n) }}>
                  {n.display}
                </span>
              ),
            },
            {
              title: "净变动",
              dataIndex: "net_change",
              align: "right",
              render: (n: Numeric) => (
                <span className="dashboard-daily-num" style={{ ...tabularNumsStyle, color: cellColor(n) }}>
                  {n.display}
                </span>
              ),
            },
          ]}
        />
      ) : (
        <Typography.Text type="secondary">暂无数据</Typography.Text>
      )}
    </section>
  );
}
