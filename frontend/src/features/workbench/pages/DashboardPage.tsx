import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { PageHeader, PageSectionLead } from "../../../components/page/PagePrimitives";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { OverviewSection } from "../../executive-dashboard/components/OverviewSection";

const PnlAttributionSection = lazy(
  () => import("../../executive-dashboard/components/PnlAttributionSection"),
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

function isAttentionMeta(meta: ResultMeta | null | undefined) {
  if (!meta) {
    return false;
  }
  return (
    meta.quality_flag !== "ok" ||
    meta.fallback_mode !== "none" ||
    meta.vendor_status !== "ok"
  );
}

function describeAttention(meta: ResultMeta | null | undefined, title: string) {
  if (!meta || !isAttentionMeta(meta)) {
    return null;
  }

  const parts = [title, meta.quality_flag];
  if (meta.fallback_mode !== "none") {
    parts.push(`fallback=${meta.fallback_mode}`);
  }
  if (meta.vendor_status !== "ok") {
    parts.push(`vendor=${meta.vendor_status}`);
  }
  return parts.join(" / ");
}

function describeMetaStatus(meta: ResultMeta | null | undefined) {
  if (!meta) {
    return {
      quality: "missing",
      generatedAt: "-",
      fallback: "unknown",
    };
  }

  return {
    quality: meta.quality_flag,
    generatedAt: meta.generated_at,
    fallback: meta.fallback_mode,
  };
}

function resolveReturnedDateLabel(
  meta: ResultMeta | null | undefined,
  requestedDateLabel: string,
) {
  const reportDate = meta?.filters_applied?.report_date;
  if (typeof reportDate === "string" && reportDate.trim()) {
    return {
      label: "as_of_date",
      value: reportDate.trim(),
    };
  }

  const effectiveReportDates = meta?.filters_applied?.effective_report_dates;
  if (
    effectiveReportDates &&
    typeof effectiveReportDates === "object" &&
    !Array.isArray(effectiveReportDates)
  ) {
    const values = Object.values(effectiveReportDates)
      .map((value) => (typeof value === "string" ? value.trim() : ""))
      .filter((value) => value.length > 0);

    if (values.length > 0) {
      const uniqueValues = Array.from(new Set(values));
      return {
        label: "as_of_date",
        value: uniqueValues.length === 1 ? uniqueValues[0] : "mixed",
      };
    }
  }

  return {
    label: "requested_date",
    value: requestedDateLabel,
  };
}

const reportDateInputStyle = {
  minWidth: 180,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid #d7dfea",
  background: "#ffffff",
  color: "#162033",
} as const;

export default function DashboardPage() {
  const client = useApiClient();
  const [reportDate, setReportDate] = useState("");
  const requestedDateLabel = reportDate || "latest";

  const queryKeyBase = useMemo(
    () => ["executive-dashboard", client.mode, requestedDateLabel],
    [client.mode, requestedDateLabel],
  );

  const overviewQuery = useQuery({
    queryKey: [...queryKeyBase, "overview"],
    queryFn: () => client.getOverview(reportDate || undefined),
    retry: false,
  });
  const pnlQuery = useQuery({
    queryKey: [...queryKeyBase, "pnl-attribution"],
    queryFn: () => client.getPnlAttribution(reportDate || undefined),
    retry: false,
  });

  const adapterOutput = useMemo(
    () =>
      adaptDashboard({
        overviewEnv: overviewQuery.data,
        attributionEnv: pnlQuery.data,
        overviewLoading: overviewQuery.isLoading,
        overviewError: overviewQuery.isError,
        attributionLoading: pnlQuery.isLoading,
        attributionError: pnlQuery.isError,
      }),
    [
      overviewQuery.data,
      overviewQuery.isLoading,
      overviewQuery.isError,
      pnlQuery.data,
      pnlQuery.isLoading,
      pnlQuery.isError,
    ],
  );

  const overviewMeta = adapterOutput.overview.meta;
  const attributionMeta = adapterOutput.attribution.meta;
  const attentionItems = [
    describeAttention(overviewMeta, "Overview"),
    describeAttention(attributionMeta, "Attribution"),
  ].filter((item): item is string => Boolean(item));
  const overviewStatus = describeMetaStatus(overviewMeta);
  const attributionStatus = describeMetaStatus(attributionMeta);
  const overviewDateLabel = resolveReturnedDateLabel(overviewMeta, requestedDateLabel);
  const attributionDateLabel = resolveReturnedDateLabel(attributionMeta, requestedDateLabel);

  return (
    <section data-testid="fixed-income-dashboard-page">
      <PageHeader
        title="驾驶舱"
        eyebrow="Overview"
        description="首页只保留当前已经落地的受治理概览与经营贡献拆解，不再在首屏混排演示模块、排除面探测结果或静态管理摘要。需要继续下钻时，进入对应工作台。"
        badgeLabel={client.mode === "real" ? "真实 API" : "Mock Mode"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
        actions={
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ color: "#64748b", fontSize: 12 }}>报告日</span>
            <input
              aria-label="报告日"
              type="date"
              value={reportDate}
              onChange={(event) => setReportDate(event.target.value)}
              style={reportDateInputStyle}
            />
          </label>
        }
      >
        <div style={{ display: "grid", gap: 14 }}>
          <p style={{ margin: 0, color: "#64748b", fontSize: 13, lineHeight: 1.7 }}>
            当前首页优先回答两个问题：现在看到的核心经营数字是什么，以及是否需要进入专门页面继续下钻。
            未纳入当前 cutover 的模块不再在这里尝试请求。
          </p>
        </div>
      </PageHeader>

      {client.mode !== "real" || attentionItems.length > 0 ? (
        <section
          data-testid="dashboard-data-warning"
          style={{
            display: "grid",
            gap: 10,
            marginBottom: 20,
            padding: 16,
            borderRadius: 18,
            border: "1px solid #f1d3b5",
            background: "#fff8f1",
            color: "#8a4b14",
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 14 }}>Data Status</div>
          {client.mode !== "real" ? (
            <div style={{ fontSize: 13, lineHeight: 1.6 }}>
              当前页面正在使用 mock 数据源。此时首页数字只用于界面演示，不应作为业务判断依据。
            </div>
          ) : null}
          {attentionItems.length > 0 ? (
            <div style={{ fontSize: 13, lineHeight: 1.6 }}>
              当前首页存在需要人工留意的数据状态： {attentionItems.join("；")}
            </div>
          ) : null}
        </section>
      ) : null}

      <section
        data-testid="dashboard-data-status-strip"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
          marginBottom: 20,
        }}
      >
        {[
          { title: "Overview", status: overviewStatus, date: overviewDateLabel },
          { title: "Attribution", status: attributionStatus, date: attributionDateLabel },
        ].map((item) => (
          <article
            key={item.title}
            style={{
              display: "grid",
              gap: 6,
              padding: 14,
              borderRadius: 16,
              border: "1px solid #e4ebf5",
              background: "#f7f9fc",
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 700, color: "#162033" }}>{item.title}</div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              quality: {item.status.quality}
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              {item.date.label}: {item.date.value}
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              generated_at: {item.status.generatedAt}
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              fallback: {item.status.fallback}
            </div>
          </article>
        ))}
      </section>

      <div
        style={{
          display: "grid",
          gap: 20,
        }}
      >
        <OverviewSection
          overview={adapterOutput.overview}
          onRetry={() => void overviewQuery.refetch()}
        />

        <section data-testid="dashboard-governed-surface" style={{ display: "grid", gap: 16 }}>
          <PageSectionLead
            eyebrow="Governed"
            title="经营贡献拆解"
            description="这里保留首页级经营贡献拆解，用于快速判断是否需要进入专门归因工作台继续分析。页面会同时展示来源元数据，避免把缺数、回退或 mock 情况误判为正式结果。"
            style={{ marginTop: 0 }}
          />
          <Suspense fallback={<LazyPanelFallback title="经营贡献拆解" />}>
            <PnlAttributionSection
              data={pnlQuery.data?.result}
              isLoading={pnlQuery.isLoading}
              isError={pnlQuery.isError}
              onRetry={() => void pnlQuery.refetch()}
            />
          </Suspense>
        </section>

        <FormalResultMetaPanel
          testId="dashboard-governed-meta"
          title="Dashboard Result Meta"
          emptyText="首页受治理模块尚未返回 result_meta。"
          sections={[
            {
              key: "overview",
              title: "Overview",
              meta: overviewMeta,
            },
            {
              key: "attribution",
              title: "Attribution",
              meta: attributionMeta,
            },
          ]}
        />
      </div>
    </section>
  );
}
