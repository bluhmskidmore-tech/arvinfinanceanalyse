import { lazy, Suspense, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { AlertsSection } from "../../executive-dashboard/components/AlertsSection";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { OverviewSection } from "../../executive-dashboard/components/OverviewSection";
import { RiskOverviewSection } from "../../executive-dashboard/components/RiskOverviewSection";
import { SummarySection } from "../../executive-dashboard/components/SummarySection";

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
    <section>
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
          <h1
            style={{
              margin: 0,
              fontSize: 34,
              fontWeight: 600,
              letterSpacing: "-0.03em",
            }}
          >
            管理层驾驶舱
          </h1>
          <p
            style={{
              marginTop: 10,
              marginBottom: 0,
              maxWidth: 780,
              color: "#5c6b82",
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            数据源可在 mock 与真实 API 间切换；本页仅演示布局与异步状态（载入、空态、失败、重试），不承载正式分析口径。
          </p>
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

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 18,
        }}
      >
        <div style={{ gridColumn: "1 / -1" }}>
          <OverviewSection
            data={overviewQuery.data?.result}
            isLoading={overviewQuery.isLoading}
            isError={overviewQuery.isError}
            onRetry={() => void overviewQuery.refetch()}
          />
        </div>
        <div>
          <SummarySection
            data={summaryQuery.data?.result}
            isLoading={summaryQuery.isLoading}
            isError={summaryQuery.isError}
            onRetry={() => void summaryQuery.refetch()}
          />
        </div>
        <div>
          <Suspense fallback={<LazyPanelFallback title="收益归因" />}>
            <PnlAttributionSection
              data={pnlQuery.data?.result}
              isLoading={pnlQuery.isLoading}
              isError={pnlQuery.isError}
              onRetry={() => void pnlQuery.refetch()}
            />
          </Suspense>
        </div>
        <div>
          <RiskOverviewSection
            data={riskQuery.data?.result}
            isLoading={riskQuery.isLoading}
            isError={riskQuery.isError}
            onRetry={() => void riskQuery.refetch()}
          />
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <Suspense fallback={<LazyPanelFallback title="团队 / 账户 / 策略贡献" />}>
            <ContributionSection
              data={contributionQuery.data?.result}
              isLoading={contributionQuery.isLoading}
              isError={contributionQuery.isError}
              onRetry={() => void contributionQuery.refetch()}
            />
          </Suspense>
        </div>
        <div>
          <AlertsSection
            data={alertsQuery.data?.result}
            isLoading={alertsQuery.isLoading}
            isError={alertsQuery.isError}
            onRetry={() => void alertsQuery.refetch()}
          />
        </div>
      </div>
    </section>
  );
}
