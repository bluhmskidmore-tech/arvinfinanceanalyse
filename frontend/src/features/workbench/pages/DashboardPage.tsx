import { lazy, Suspense, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
import {
  PageFilterTray,
  PageHeader,
  PageSectionLead,
} from "../../../components/page/PagePrimitives";
import { AlertsSection } from "../../executive-dashboard/components/AlertsSection";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { OverviewSection } from "../../executive-dashboard/components/OverviewSection";
import { RiskOverviewSection } from "../../executive-dashboard/components/RiskOverviewSection";
import { SummarySection } from "../../executive-dashboard/components/SummarySection";
import {
  DashboardModuleSnapshot,
  DashboardStructureMaturityTeaser,
  DashboardTasksAndCalendar,
} from "../dashboard/FixedIncomeDashboardHub";

const PnlAttributionSection = lazy(
  () => import("../../executive-dashboard/components/PnlAttributionSection"),
);
const ContributionSection = lazy(
  () => import("../../executive-dashboard/components/ContributionSection"),
);

function LazyPanelFallback({ title }: { title: string }) {
  return (
    <AsyncSection
      title={title}
      isLoading
      isError={false}
      isEmpty={false}
      onRetry={() => undefined}
    >
      <div />
    </AsyncSection>
  );
}

const controlStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

function isUnavailableExecutiveSection(
  vendorStatus: string | undefined,
  error: unknown,
) {
  if (vendorStatus === "vendor_unavailable") {
    return true;
  }
  return error instanceof Error && error.message.includes("(503)");
}

export default function DashboardPage() {
  const client = useApiClient();
  const queryKeyBase = useMemo(
    () => ["executive-dashboard", client.mode],
    [client.mode],
  );

  const overviewQuery = useQuery({
    queryKey: [...queryKeyBase, "overview"],
    queryFn: () => client.getOverview(),
    retry: false,
  });
  const summaryQuery = useQuery({
    queryKey: [...queryKeyBase, "summary"],
    queryFn: () => client.getSummary(),
    retry: false,
  });
  const pnlQuery = useQuery({
    queryKey: [...queryKeyBase, "pnl-attribution"],
    queryFn: () => client.getPnlAttribution(),
    retry: false,
  });
  const riskQuery = useQuery({
    queryKey: [...queryKeyBase, "risk-overview"],
    queryFn: () => client.getRiskOverview(),
    retry: false,
  });
  const contributionQuery = useQuery({
    queryKey: [...queryKeyBase, "contribution"],
    queryFn: () => client.getContribution(),
    retry: false,
  });
  const alertsQuery = useQuery({
    queryKey: [...queryKeyBase, "alerts"],
    queryFn: () => client.getAlerts(),
    retry: false,
  });

  const alertsAvailable =
    alertsQuery.isLoading ||
    !isUnavailableExecutiveSection(
      alertsQuery.data?.result_meta.vendor_status,
      alertsQuery.error,
    );
  const riskAvailable =
    riskQuery.isLoading ||
    !isUnavailableExecutiveSection(
      riskQuery.data?.result_meta.vendor_status,
      riskQuery.error,
    );
  const contributionAvailable =
    contributionQuery.isLoading ||
    !isUnavailableExecutiveSection(
      contributionQuery.data?.result_meta.vendor_status,
      contributionQuery.error,
    );

  return (
    <section data-testid="fixed-income-dashboard-page">
      <PageHeader
        title="驾驶舱"
        eyebrow="Overview"
        description="先看经营总览、全局判断和预警，再顺着模块入口、结构速览与收益风险分解进入各主题工作台。"
        badgeLabel={client.mode === "real" ? "真实 API" : "本地演示数据"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
      >
        <div style={{ display: "grid", gap: 14 }}>
          <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>报告日 2026-03-01</p>
          <PageFilterTray>
            <FilterBar>
              <label>
                <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
                  范围
                </span>
                <select style={controlStyle} disabled>
                  <option>金融市场条线</option>
                </select>
              </label>
              <label>
                <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
                  口径
                </span>
                <select style={controlStyle}>
                  <option>摊余成本</option>
                </select>
              </label>
              <label>
                <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
                  币种
                </span>
                <select style={controlStyle}>
                  <option>全部</option>
                </select>
              </label>
              <label>
                <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
                  部门
                </span>
                <select style={controlStyle}>
                  <option>全部</option>
                </select>
              </label>
            </FilterBar>
          </PageFilterTray>
        </div>
      </PageHeader>

      <div
        style={{
          display: "grid",
          gap: 20,
        }}
      >
        <OverviewSection
          data={overviewQuery.data?.result}
          isLoading={overviewQuery.isLoading}
          isError={overviewQuery.isError}
          onRetry={() => void overviewQuery.refetch()}
        />

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 18,
            alignItems: "stretch",
          }}
        >
          <SummarySection
            sectionTitle="全局判断"
            data={summaryQuery.data?.result}
            isLoading={summaryQuery.isLoading}
            isError={summaryQuery.isError}
            onRetry={() => void summaryQuery.refetch()}
          />
          <DashboardModuleSnapshot />
          {alertsAvailable ? (
            <AlertsSection
              sectionTitle="预警中心"
              data={alertsQuery.data?.result}
              isLoading={alertsQuery.isLoading}
              isError={alertsQuery.isError}
              onRetry={() => void alertsQuery.refetch()}
            />
          ) : null}
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 18,
            alignItems: "stretch",
          }}
        >
          <DashboardStructureMaturityTeaser />
          <DashboardTasksAndCalendar />
        </div>

        <section data-testid="dashboard-extended-panels" style={{ display: "grid", gap: 16 }}>
          <PageSectionLead
            eyebrow="Analytical"
            title="收益归因与风险分解"
            description="在总览判断之后，再展开收益归因、风险概览和团队贡献，保持驾驶舱先判断、后下钻的阅读顺序。"
            style={{ marginTop: 0 }}
          />
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: 18,
            }}
          >
            <Suspense fallback={<LazyPanelFallback title="收益归因" />}>
              <PnlAttributionSection
                data={pnlQuery.data?.result}
                isLoading={pnlQuery.isLoading}
                isError={pnlQuery.isError}
                onRetry={() => void pnlQuery.refetch()}
              />
            </Suspense>
            {riskAvailable ? (
              <RiskOverviewSection
                data={riskQuery.data?.result}
                isLoading={riskQuery.isLoading}
                isError={riskQuery.isError}
                onRetry={() => void riskQuery.refetch()}
              />
            ) : null}
          </div>
          {contributionAvailable ? (
            <Suspense fallback={<LazyPanelFallback title="团队 / 账户 / 策略贡献" />}>
              <ContributionSection
                data={contributionQuery.data?.result}
                isLoading={contributionQuery.isLoading}
                isError={contributionQuery.isError}
                onRetry={() => void contributionQuery.refetch()}
              />
            </Suspense>
          ) : null}
        </section>
      </div>
    </section>
  );
}
