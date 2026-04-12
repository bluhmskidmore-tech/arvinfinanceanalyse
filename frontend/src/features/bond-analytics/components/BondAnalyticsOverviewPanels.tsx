import { Alert, Button, Card, Col, Row, Select, Space, Tag } from "antd";
import type { BondAnalyticsOverviewModel } from "../lib/bondAnalyticsOverviewModel";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import type { PeriodType } from "../types";

const PERIOD_OPTIONS = [
  { value: "MoM", label: "Month" },
  { value: "YTD", label: "YTD" },
  { value: "TTM", label: "TTM" },
];

function moduleTagColor(
  tier: "summary" | "status" | "blocked",
  statusLabel: string,
) {
  if (tier === "summary") {
    return "success";
  }

  if (tier === "blocked" || statusLabel === "placeholder") {
    return "warning";
  }

  if (statusLabel === "request-error") {
    return "error";
  }

  return "processing";
}

export interface BondAnalyticsOverviewPanelsProps {
  dateOptions: Array<{ value: string; label: string }>;
  reportDate: string;
  onReportDateChange: (value: string) => void;
  periodType: PeriodType;
  onPeriodTypeChange: (value: PeriodType) => void;
  overviewModel: BondAnalyticsOverviewModel;
  onOpenModuleDetail: (key: BondAnalyticsModuleKey) => void;
  onRefreshAnalytics?: () => void;
  isAnalyticsRefreshing?: boolean;
  analyticsRefreshError?: string | null;
  lastAnalyticsRefreshRunId?: string | null;
}

export function BondAnalyticsOverviewPanels({
  dateOptions,
  reportDate,
  onReportDateChange,
  periodType,
  onPeriodTypeChange,
  overviewModel,
  onOpenModuleDetail,
  onRefreshAnalytics,
  isAnalyticsRefreshing = false,
  analyticsRefreshError = null,
  lastAnalyticsRefreshRunId = null,
}: BondAnalyticsOverviewPanelsProps) {
  return (
    <>
      <Card size="small">
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 12,
              }}
            >
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Bond analytics</h2>
              {onRefreshAnalytics ? (
                <Button
                  type="default"
                  size="small"
                  loading={isAnalyticsRefreshing}
                  disabled={isAnalyticsRefreshing}
                  onClick={() => onRefreshAnalytics()}
                  data-testid="bond-analytics-refresh-button"
                >
                  刷新分析
                </Button>
              ) : null}
            </div>
            {lastAnalyticsRefreshRunId ? (
              <div style={{ color: "#5c6b82", fontSize: 12 }}>
                最近刷新任务：{lastAnalyticsRefreshRunId}
              </div>
            ) : null}
            {analyticsRefreshError ? (
              <div style={{ color: "#b42318", fontSize: 12 }}>{analyticsRefreshError}</div>
            ) : null}
            <div style={{ color: "#5c6b82", fontSize: 13, maxWidth: 640 }}>
              Start with the overview, then drill into the active module only when it is
              relevant. The first screen stays summary-first and does not pretend
              placeholder data is a real KPI.
            </div>
          </div>

          <Space size={12} wrap>
            <div>
              <span style={{ marginRight: 8, color: "#5c6b82", fontSize: 13 }}>
                Report date
              </span>
              <Select
                value={reportDate}
                onChange={onReportDateChange}
                options={dateOptions}
                style={{ width: 160 }}
                size="small"
              />
            </div>
            <div>
              <span style={{ marginRight: 8, color: "#5c6b82", fontSize: 13 }}>
                Period
              </span>
              <Select
                value={periodType}
                onChange={(value) => onPeriodTypeChange(value as PeriodType)}
                options={PERIOD_OPTIONS}
                style={{ width: 140 }}
                size="small"
              />
            </div>
          </Space>
        </div>
      </Card>

      <Alert
        type="info"
        showIcon
        data-testid="bond-analysis-truth-panel"
        message="Truth boundary"
        description={
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span>The overview only promotes stable, real summary modules.</span>
            <span>All other modules keep their honest status and detail entry points.</span>
          </div>
        }
      />

      {overviewModel.topWarnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="Overview warning"
          description={overviewModel.topWarnings.map((warning, index) => (
            <div key={`${warning}-${index}`}>{warning}</div>
          ))}
        />
      )}

      <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16 }}>Summary first</h3>
          <div style={{ color: "#8090a8", fontSize: 13 }}>
            Only stable summary modules are surfaced here.
          </div>
        </div>

        {overviewModel.summaryModules.length === 0 ? (
          <Card size="small" data-testid="bond-analysis-no-summary">
            No summary modules are ready yet. Start from the module status grid below.
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {overviewModel.summaryModules.map((module) => (
              <Col key={module.key} xs={24} md={12} lg={8}>
                <Card
                  size="small"
                  title={module.label}
                  extra={<Tag color="success">Real summary</Tag>}
                  data-testid={`bond-analysis-summary-${module.key}`}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ color: "#8090a8", fontSize: 13 }}>
                      {module.description}
                    </div>
                    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                      <div>
                        <div style={{ color: "#8090a8", fontSize: 12 }}>
                          {module.summary?.primaryLabel}
                        </div>
                        <div style={{ fontSize: 22, fontWeight: 600 }}>
                          {module.summary?.primaryValue}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: "#8090a8", fontSize: 12 }}>
                          {module.summary?.secondaryLabel}
                        </div>
                        <div style={{ fontSize: 18, fontWeight: 600 }}>
                          {module.summary?.secondaryValue}
                        </div>
                      </div>
                    </div>
                    <Button
                      size="small"
                      onClick={() => onOpenModuleDetail(module.key)}
                      data-testid={`bond-analysis-open-summary-${module.key}`}
                    >
                      Open detail
                    </Button>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16 }}>Current module status</h3>
          <div style={{ color: "#8090a8", fontSize: 13 }}>
            Ready modules keep the detail entry point, but the overview stays ahead.
          </div>
        </div>

        <Row gutter={[16, 16]} data-testid="bond-analysis-module-grid">
          {overviewModel.currentModules.map((module) => (
            <Col key={module.key} xs={24} md={12} lg={8}>
              <Card
                size="small"
                data-testid={`bond-analysis-module-${module.key}`}
                data-tier={module.tier}
                title={module.label}
                extra={
                  <Tag color={moduleTagColor(module.tier, module.statusLabel)}>
                    {module.statusLabel}
                  </Tag>
                }
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ color: "#5c6b82", fontSize: 13 }}>
                    {module.description}
                  </div>
                  <div style={{ fontSize: 13 }}>{module.statusReason}</div>
                  {module.summary && (
                    <div style={{ display: "flex", gap: 16 }}>
                      <div>
                        <div style={{ color: "#8090a8", fontSize: 12 }}>
                          {module.summary.primaryLabel}
                        </div>
                        <div style={{ fontWeight: 600 }}>{module.summary.primaryValue}</div>
                      </div>
                      <div>
                        <div style={{ color: "#8090a8", fontSize: 12 }}>
                          {module.summary.secondaryLabel}
                        </div>
                        <div style={{ fontWeight: 600 }}>{module.summary.secondaryValue}</div>
                      </div>
                    </div>
                  )}
                  <div style={{ color: "#8090a8", fontSize: 12 }}>
                    {module.detailHint}
                  </div>
                  <Button
                    size="small"
                    onClick={() => onOpenModuleDetail(module.key)}
                    data-testid={`bond-analysis-open-${module.key}`}
                  >
                    Enter detail
                  </Button>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </section>

      <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16 }}>Future modules</h3>
          <div style={{ color: "#8090a8", fontSize: 13 }}>
            These modules stay blocked until the backend surface is ready.
          </div>
        </div>

        <Row gutter={[16, 16]} data-testid="bond-analysis-future-grid">
          {overviewModel.futureModules.map((module) => (
            <Col key={module.key} xs={24} md={12} lg={8}>
              <Card
                size="small"
                title={module.label}
                extra={<Tag color="default">blocked</Tag>}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ color: "#5c6b82", fontSize: 13 }}>
                    {module.description}
                  </div>
                  <div style={{ fontSize: 13 }}>{module.statusReason}</div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </section>
    </>
  );
}

export default BondAnalyticsOverviewPanels;
