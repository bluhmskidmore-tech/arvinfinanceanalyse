import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { PageHeader, PageSectionLead } from "../../../components/page/PagePrimitives";
import { shellTokens } from "../../../theme/tokens";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { DashboardBondCounterpartySection } from "../../executive-dashboard/components/DashboardBondCounterpartySection";
import { DashboardBondHeadlineSection } from "../../executive-dashboard/components/DashboardBondHeadlineSection";
import { DashboardLiabilityCounterpartySection } from "../../executive-dashboard/components/DashboardLiabilityCounterpartySection";
import { DashboardMacroSpotSection } from "../../executive-dashboard/components/DashboardMacroSpotSection";
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

const dashboardHeroStyle = {
  padding: "24px clamp(20px, 2vw, 30px)",
  borderRadius: 28,
  border: `1px solid ${shellTokens.colorBorder}`,
  background: `linear-gradient(145deg, ${shellTokens.colorBgCanvas} 0%, ${shellTokens.colorBgSurface} 78%)`,
  boxShadow: shellTokens.shadowPanel,
} as const;

const dashboardSummaryCardStyle = {
  display: "grid",
  gap: 6,
  padding: "14px 16px",
  borderRadius: 18,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: "rgba(255,255,255,0.55)",
  minHeight: 92,
  alignContent: "start",
} as const;

const dashboardWarningPanelStyle = {
  display: "grid",
  gap: 10,
  padding: 18,
  borderRadius: 20,
  border: `1px solid ${shellTokens.colorBorderWarning}`,
  background: shellTokens.colorBgWarningSoft,
  color: shellTokens.colorTextWarning,
  minHeight: "100%",
} as const;

const dashboardGovernancePanelStyle = {
  display: "grid",
  gap: 14,
  padding: 18,
  borderRadius: 20,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: `linear-gradient(180deg, ${shellTokens.colorBgCanvas} 0%, ${shellTokens.colorBgSurface} 100%)`,
} as const;

const dashboardStatusCardStyle = {
  display: "grid",
  gap: 8,
  padding: 16,
  borderRadius: 18,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: shellTokens.colorBgCanvas,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.72)",
} as const;

const dashboardGovernedSurfaceStyle = {
  display: "grid",
  gap: 16,
  padding: 18,
  borderRadius: 24,
  border: `1px solid ${shellTokens.colorBorderSoft}`,
  background: `linear-gradient(180deg, ${shellTokens.colorBgCanvas} 0%, ${shellTokens.colorBgSurface} 100%)`,
} as const;

const reportDateInputStyle = {
  minWidth: 180,
  padding: "12px 14px",
  borderRadius: 14,
  border: `1px solid ${shellTokens.colorBorder}`,
  background: shellTokens.colorBgCanvas,
  color: shellTokens.colorTextPrimary,
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.72)",
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
  const summaryCards = useMemo(
    () => [
      {
        label: "Report date",
        value: effectiveReportDate || "latest",
        note: snapshotResult?.report_date ? "backend effective" : "user selection",
      },
      {
        label: "Snapshot",
        value: snapshotQuery.isLoading ? "loading" : snapshotResult?.mode ?? "pending",
        note: snapshotPartialNote ? "partial surface" : "complete surface",
      },
      {
        label: "Attention",
        value: attentionItems.length > 0 ? String(attentionItems.length) : "0",
        note: attentionItems.length > 0 ? attentionItems.join(" / ") : "no governed flags",
      },
      {
        label: "Data source",
        value: client.mode === "real" ? "Real API" : "Mock mode",
        note: client.mode === "real" ? "live read path" : "demo surface only",
      },
    ],
    [
      attentionItems,
      client.mode,
      effectiveReportDate,
      snapshotPartialNote,
      snapshotQuery.isLoading,
      snapshotResult?.mode,
      snapshotResult?.report_date,
    ],
  );

  return (
    <section data-testid="fixed-income-dashboard-page">
      <PageHeader
        title="驾驶舱"
        eyebrow="Overview"
        description="首页只保留当前已经落地的受治理概览与经营贡献拆解，不再在首屏混排演示模块、排除面探测结果或静态管理摘要。需要继续下钻时，进入对应工作台。"
        badgeLabel={client.mode === "real" ? "真实 API" : "Mock Mode"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
        style={dashboardHeroStyle}
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
          <p
            style={{
              margin: 0,
              color: shellTokens.colorTextSecondary,
              fontSize: 13,
              lineHeight: 1.75,
              maxWidth: 860,
            }}
          >
            当前首页优先回答两个问题：现在看到的核心经营数字是什么，以及是否需要进入专门页面继续下钻。
            未纳入当前 cutover 的模块不再在这里尝试请求。
          </p>
          <div className="dashboard-hero-summary">
            {summaryCards.map((card) => (
              <article key={card.label} style={dashboardSummaryCardStyle}>
                <span
                  style={{
                    color: shellTokens.colorTextMuted,
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                  }}
                >
                  {card.label}
                </span>
                <strong
                  style={{
                    color: shellTokens.colorTextPrimary,
                    fontSize: 18,
                    lineHeight: 1.2,
                    letterSpacing: "-0.02em",
                  }}
                >
                  {card.value}
                </strong>
                <span
                  style={{
                    color: shellTokens.colorTextSecondary,
                    fontSize: 12,
                    lineHeight: 1.6,
                  }}
                >
                  {card.note}
                </span>
              </article>
            ))}
          </div>
        </div>
      </PageHeader>

      <div className="dashboard-gov-grid">
        {client.mode !== "real" || attentionItems.length > 0 || snapshotPartialNote ? (
          <section data-testid="dashboard-data-warning" style={dashboardWarningPanelStyle}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>Data Status</div>
          {client.mode !== "real" ? (
            <div style={{ fontSize: 13, lineHeight: 1.7 }}>
              当前页面正在使用 mock 数据源。此时首页数字只用于界面演示，不应作为业务判断依据。
            </div>
          ) : null}
          {attentionItems.length > 0 ? (
            <div style={{ fontSize: 13, lineHeight: 1.7 }}>
              当前首页存在需要人工留意的数据状态： {attentionItems.join("；")}
            </div>
          ) : null}
          {snapshotPartialNote ? (
            <div style={{ fontSize: 13, lineHeight: 1.7 }}>{snapshotPartialNote}</div>
          ) : null}
          </section>
        ) : (
          <section style={dashboardGovernancePanelStyle}>
            <div
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Decision Focus
            </div>
            <div style={{ color: shellTokens.colorTextPrimary, fontSize: 18, fontWeight: 700 }}>
              Keep the first screen verdict-driven
            </div>
            <div style={{ color: shellTokens.colorTextSecondary, fontSize: 13, lineHeight: 1.7 }}>
              Review governed freshness and fallback state before trusting any number, then drill
              into the dedicated workspace only when the surface shows clear follow-up demand.
            </div>
          </section>
        )}

        <section style={dashboardGovernancePanelStyle}>
          <div
            style={{
              color: shellTokens.colorTextMuted,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            Governed Surfaces
          </div>
          <section
            data-testid="dashboard-data-status-strip"
            className="dashboard-status-grid"
            style={{ display: "grid", marginBottom: 0 }}
          >
            {[
              { title: "Overview", status: overviewStatus, date: overviewDateLabel },
              { title: "Attribution", status: attributionStatus, date: attributionDateLabel },
            ].map((item) => (
              <article key={item.title} style={dashboardStatusCardStyle}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: shellTokens.colorTextPrimary,
                    letterSpacing: "0.04em",
                  }}
                >
                  {item.title}
                </div>
                <div style={{ fontSize: 12, color: shellTokens.colorTextSecondary }}>
                  quality: {item.status.quality}
                </div>
                <div style={{ fontSize: 12, color: shellTokens.colorTextSecondary }}>
                  {item.date.label}: {item.date.value}
                </div>
                <div style={{ fontSize: 12, color: shellTokens.colorTextSecondary }}>
                  generated_at: {item.status.generatedAt}
                </div>
                <div style={{ fontSize: 12, color: shellTokens.colorTextSecondary }}>
                  fallback: {item.status.fallback}
                </div>
              </article>
            ))}
          </section>
        </section>
      </div>

      <div style={{ display: "grid", gap: 20 }}>
        <div className="dashboard-primary-grid">
          <OverviewSection
          overview={adapterOutput.overview}
          onRetry={() => void snapshotQuery.refetch()}
        />

        <section
          data-testid="dashboard-governed-surface"
          style={dashboardGovernedSurfaceStyle}
        >
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

        </div>

        <div className="dashboard-secondary-grid">
          <div className="dashboard-span-wide">
            <DashboardBondHeadlineSection reportDate={effectiveReportDate} />
          </div>

          <DashboardMacroSpotSection />

          <DashboardNewsDigestSection />

          <DashboardBondCounterpartySection reportDate={effectiveReportDate} />

          <DashboardLiabilityCounterpartySection reportDate={effectiveReportDate} />
        </div>

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
