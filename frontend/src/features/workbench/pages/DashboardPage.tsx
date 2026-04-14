import { lazy, Suspense, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { FilterBar } from "../../../components/FilterBar";
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

const extendedSectionTitleStyle = {
  margin: "8px 0 0",
  fontSize: 16,
  fontWeight: 600,
  color: "#162033",
} as const;

const controlStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

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

  return (
    <section data-testid="fixed-income-dashboard-page">
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 28,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>驾驶舱</h1>
          <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: 13 }}>报期 2026-03-01</p>
        </div>
        <span
          style={{
            margin: 0,
            borderRadius: 999,
            background: client.mode === "real" ? "#e8f6ee" : "#dfe8ff",
            color: client.mode === "real" ? "#2f8f63" : "#1f5eff",
            paddingInline: 12,
            paddingBlock: 8,
            fontSize: 12,
            letterSpacing: "0.04em",
          }}
        >
          {client.mode === "real" ? "真实 API" : "本地演示数据"}
        </span>
      </div>

      <FilterBar style={{ marginBottom: 20 }}>
        <label>
          <span style={{ display: "block", marginBottom: 4, color: "#64748b", fontSize: 12 }}>
            区间
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

      <div
        style={{
          display: "grid",
          gap: 18,
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
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
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
          <DashboardStructureMaturityTeaser />
        </div>

        <DashboardModuleSnapshot />

        <AlertsSection
          sectionTitle="预警中心"
          data={alertsQuery.data?.result}
          isLoading={alertsQuery.isLoading}
          isError={alertsQuery.isError}
          onRetry={() => void alertsQuery.refetch()}
        />

        <DashboardTasksAndCalendar />

        <section data-testid="dashboard-extended-panels" style={{ display: "grid", gap: 16 }}>
          <h2 style={extendedSectionTitleStyle}>收益归因与风险分解</h2>
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
            <RiskOverviewSection
              data={riskQuery.data?.result}
              isLoading={riskQuery.isLoading}
              isError={riskQuery.isError}
              onRetry={() => void riskQuery.refetch()}
            />
          </div>
          <Suspense fallback={<LazyPanelFallback title="团队 / 账户 / 策略贡献" />}>
            <ContributionSection
              data={contributionQuery.data?.result}
              isLoading={contributionQuery.isLoading}
              isError={contributionQuery.isError}
              onRetry={() => void contributionQuery.refetch()}
            />
          </Suspense>
        </section>
      </div>
    </section>
  );
}
