import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { PageHeader, PageSectionLead } from "../../../components/page/PagePrimitives";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { DashboardLiabilityCounterpartySection } from "../../executive-dashboard/components/DashboardLiabilityCounterpartySection";
import { DashboardNewsDigestSection } from "../../executive-dashboard/components/DashboardNewsDigestSection";
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
  const [allowPartial, setAllowPartial] = useState(false);
  const requestedDateLabel = reportDate || "latest";

  const snapshotQuery = useQuery({
    queryKey: ["home-snapshot", client.mode, requestedDateLabel, allowPartial],
    queryFn: () =>
      client.getHomeSnapshot({
        reportDate: reportDate || undefined,
        allowPartial,
      }),
    retry: false,
  });

  const { overviewEnv, attributionEnv } = useMemo(() => {
    const env = snapshotQuery.data;
    if (!env) return { overviewEnv: undefined, attributionEnv: undefined };
    return {
      overviewEnv: {
        result_meta: env.result_meta,
        result: env.result.overview,
      },
      attributionEnv: {
        result_meta: env.result_meta,
        result: env.result.attribution,
      },
    };
  }, [snapshotQuery.data]);

  const adapterOutput = useMemo(
    () =>
      adaptDashboard({
        overviewEnv,
        attributionEnv,
        overviewLoading: snapshotQuery.isLoading,
        overviewError: snapshotQuery.isError,
        attributionLoading: snapshotQuery.isLoading,
        attributionError: snapshotQuery.isError,
      }),
    [overviewEnv, attributionEnv, snapshotQuery.isLoading, snapshotQuery.isError],
  );

  const overviewMeta = adapterOutput.overview.meta;
  const attributionMeta = adapterOutput.attribution.meta;
  const attentionItems = [
    describeAttention(overviewMeta, "Overview"),
    describeAttention(attributionMeta, "Attribution"),
  ].filter((item): item is string => Boolean(item));

  const snapshotResult = snapshotQuery.data?.result;
  const effectiveReportDate = useMemo(() => {
    const manual = reportDate.trim();
    const snap = snapshotResult?.report_date?.trim();
    return manual || snap || "";
  }, [reportDate, snapshotResult?.report_date]);

  const snapshotPartialNote = useMemo(() => {
    if (!snapshotResult) return null;
    if (snapshotResult.mode === "partial" || snapshotResult.domains_missing.length > 0) {
      const missing = snapshotResult.domains_missing.length
        ? snapshotResult.domains_missing.join(", ")
        : "";
      return `该日部分业务域不可用${missing ? `: ${missing}` : ""}`;
    }
    return null;
  }, [snapshotResult]);

  const overviewDateLabel = useMemo(() => {
    const snapDate = snapshotResult?.report_date?.trim();
    if (snapDate) {
      return { label: "as_of_date" as const, value: snapDate };
    }
    return resolveReturnedDateLabel(overviewMeta, requestedDateLabel);
  }, [snapshotResult?.report_date, overviewMeta, requestedDateLabel]);

  const attributionDateLabel = useMemo(() => {
    const snapDate = snapshotResult?.report_date?.trim();
    if (snapDate) {
      return { label: "as_of_date" as const, value: snapDate };
    }
    return resolveReturnedDateLabel(attributionMeta, requestedDateLabel);
  }, [snapshotResult?.report_date, attributionMeta, requestedDateLabel]);

  const overviewStatus = describeMetaStatus(overviewMeta);
  const attributionStatus = describeMetaStatus(attributionMeta);

  return (
    <section data-testid="fixed-income-dashboard-page">
      <PageHeader
        title="驾驶舱"
        eyebrow="Overview"
        description="首页只保留当前已经落地的受治理概览与经营贡献拆解，不再在首屏混排演示模块、排除面探测结果或静态管理摘要。需要继续下钻时，进入对应工作台。"
        badgeLabel={client.mode === "real" ? "真实 API" : "Mock Mode"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
        actions={
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "end" }}>
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
            <label
              style={{
                display: "flex",
                gap: 8,
                alignItems: "center",
                color: "#162033",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              <input
                aria-label="允许历史日（含缺域）"
                type="checkbox"
                checked={allowPartial}
                onChange={(event) => setAllowPartial(event.target.checked)}
              />
              <span>允许历史日（含缺域）</span>
            </label>
          </div>
        }
      >
        <div style={{ display: "grid", gap: 14 }}>
          <p style={{ margin: 0, color: "#64748b", fontSize: 13, lineHeight: 1.7 }}>
            当前首页优先回答两个问题：现在看到的核心经营数字是什么，以及是否需要进入专门页面继续下钻。
            未纳入当前 cutover 的模块不再在这里尝试请求。
          </p>
        </div>
      </PageHeader>

      {client.mode !== "real" || attentionItems.length > 0 || snapshotPartialNote ? (
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
          {snapshotPartialNote ? (
            <div style={{ fontSize: 13, lineHeight: 1.6 }}>{snapshotPartialNote}</div>
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
          onRetry={() => void snapshotQuery.refetch()}
        />

        <DashboardNewsDigestSection />

        <DashboardLiabilityCounterpartySection reportDate={effectiveReportDate} />

        <section data-testid="dashboard-governed-surface" style={{ display: "grid", gap: 16 }}>
          <PageSectionLead
            eyebrow="Governed"
            title="经营贡献拆解"
            description="这里保留首页级经营贡献拆解，用于快速判断是否需要进入专门损益拆解工作台继续分析。页面会同时展示来源元数据，避免把缺数、回退或 mock 情况误判为正式结果。"
            style={{ marginTop: 0 }}
          />
          <Suspense fallback={<LazyPanelFallback title="经营贡献拆解" />}>
            <PnlAttributionSection
              attribution={adapterOutput.attribution}
              onRetry={() => void snapshotQuery.refetch()}
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
