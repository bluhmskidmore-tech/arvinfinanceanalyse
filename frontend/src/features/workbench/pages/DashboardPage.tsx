import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import { PageHeader, PageSectionLead } from "../../../components/page/PagePrimitives";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";
import type { Tone } from "../../../utils/tone";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { DashboardBondCounterpartySection } from "../../executive-dashboard/components/DashboardBondCounterpartySection";
import { DashboardBondHeadlineSection } from "../../executive-dashboard/components/DashboardBondHeadlineSection";
import { DashboardLiabilityCounterpartySection } from "../../executive-dashboard/components/DashboardLiabilityCounterpartySection";
import { DashboardMacroSpotSection } from "../../executive-dashboard/components/DashboardMacroSpotSection";
import { DashboardNewsDigestSection } from "../../executive-dashboard/components/DashboardNewsDigestSection";
import {
  DashboardAlertCenterPanel,
  DashboardGlobalJudgmentPanel,
  DashboardModuleEntryGrid,
  DashboardModuleSnapshotPanel,
  DashboardOverviewHeroStrip,
  DashboardTasksCalendarPanels,
  type DashboardAlert,
  type DashboardHeroMetric,
  type DashboardJudgment,
} from "../dashboard/DashboardOverviewSections";

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

function headerButtonStyle(kind: "primary" | "secondary") {
  const isPrimary = kind === "primary";
  return {
    height: designTokens.space[8],
    padding: `0 ${designTokens.space[4]}px`,
    borderRadius: 999,
    border: isPrimary
      ? `1px solid ${shellTokens.colorAccent}`
      : `1px solid ${shellTokens.colorBorderSoft}`,
    background: isPrimary ? shellTokens.colorAccentSoft : designTokens.color.primary[50],
    color: isPrimary ? shellTokens.colorAccent : shellTokens.colorTextSecondary,
    fontSize: designTokens.fontSize[13],
    fontWeight: 700,
    cursor: "pointer",
  } as const;
}

function dashboardSignalForTone(
  tone: Tone,
  index: number,
): DashboardHeroMetric["spark"] {
  if (tone === "positive") {
    return index % 2 === 0 ? "softUp" : "swing";
  }
  if (tone === "negative") {
    return "softDown";
  }
  if (tone === "warning") {
    return "swing";
  }
  return index % 2 === 0 ? "flat" : "softUp";
}

function formatSnapshotMode(
  mode: string | undefined,
  isLoading: boolean,
): string {
  if (isLoading) return "loading";
  if (!mode) return "pending";
  return mode;
}

function formatHeroDelta(display: string | undefined, fallbackLabel: string) {
  if (display && display.trim() && display.trim() !== "—") {
    return display;
  }
  return fallbackLabel;
}

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

  const heroMetrics = useMemo<DashboardHeroMetric[]>(() => {
    const overviewMetrics =
      adapterOutput.overview.vm?.metrics.map((metric, index) => ({
        id: metric.id,
        label: metric.label,
        value: metric.value.display,
        note: metric.detail,
        delta: formatHeroDelta(metric.delta.display, "read path"),
        tone: metric.tone,
        spark: dashboardSignalForTone(metric.tone, index),
      })) ?? [];

    const governanceMetrics: DashboardHeroMetric[] = [
      {
        id: "report-date",
        label: "报告日",
        value: effectiveReportDate || "latest",
        note: snapshotResult?.report_date ? "后端生效日期" : "用户选择 / 默认日期",
        delta: overviewDateLabel.label,
        tone: "neutral",
        spark: "flat",
      },
      {
        id: "snapshot-mode",
        label: "快照模式",
        value: formatSnapshotMode(snapshotResult?.mode, snapshotQuery.isLoading),
        note: snapshotPartialNote || "首页首屏只保留已落地的受治理结果。",
        delta: snapshotPartialNote ? "partial surface" : "complete surface",
        tone: snapshotPartialNote ? "warning" : "positive",
        spark: snapshotPartialNote ? "softDown" : "softUp",
      },
      {
        id: "attention-items",
        label: "治理关注",
        value: attentionItems.length > 0 ? `${attentionItems.length} 项` : "无异常",
        note:
          attentionItems.length > 0
            ? attentionItems.join(" / ")
            : "当前没有 quality / fallback / vendor 警示。",
        delta: attentionItems.length > 0 ? "manual review" : "governed",
        tone: attentionItems.length > 0 ? "warning" : "positive",
        spark: attentionItems.length > 0 ? "swing" : "softUp",
      },
      {
        id: "data-source",
        label: "读取模式",
        value: client.mode === "real" ? "Real API" : "Mock",
        note: client.mode === "real" ? "真实读链路" : "仅用于界面演示",
        delta: client.mode === "real" ? "live" : "demo",
        tone: client.mode === "real" ? "positive" : "warning",
        spark: client.mode === "real" ? "softUp" : "flat",
      },
    ];

    return [...overviewMetrics, ...governanceMetrics].slice(0, 8);
  }, [
    adapterOutput.overview.vm?.metrics,
    attentionItems,
    client.mode,
    effectiveReportDate,
    overviewDateLabel.label,
    snapshotPartialNote,
    snapshotQuery.isLoading,
    snapshotResult?.mode,
    snapshotResult?.report_date,
  ]);

  const globalJudgment = useMemo<DashboardJudgment>(() => {
    const metrics = adapterOutput.overview.vm?.metrics ?? [];
    const segments = adapterOutput.attribution.vm?.segments ?? [];

    const bullets = metrics.slice(0, 3).map((metric) => {
      const delta =
        metric.delta.display && metric.delta.display !== "—"
          ? `，变动 ${metric.delta.display}`
          : "";
      return `${metric.label} ${metric.value.display}${delta}：${metric.detail}`;
    });

    if (segments.length > 0) {
      const topSegments = segments
        .slice(0, 2)
        .map((segment) => `${segment.label} ${segment.amount.display}`)
        .join(" / ");
      bullets.push(`经营贡献拆解已就绪：${topSegments}`);
    }

    if (snapshotPartialNote) {
      bullets.push(snapshotPartialNote);
    }

    const tags: DashboardJudgment["tags"] = [];
    tags.push({ label: client.mode === "real" ? "真实读链路" : "演示数据", tone: client.mode === "real" ? "positive" : "warning" });
    tags.push({
      label: attentionItems.length > 0 ? "需人工确认" : "治理通过",
      tone: attentionItems.length > 0 ? "warning" : "positive",
    });
    if (snapshotPartialNote) {
      tags.push({ label: "含缺域", tone: "warning" });
    }
    if (segments.length > 0) {
      tags.push({ label: "贡献拆解可下钻", tone: "accent" });
    }

    if (metrics.length === 0) {
      return {
        title: "全局判断",
        body:
          "首页当前先呈现治理状态、报告日和分流入口。等快照回到可读状态后，再基于首屏数字做方向性判断。",
        bullets: bullets.length > 0 ? bullets : ["等待首页快照返回后再形成正式判断。"],
        tags,
      };
    }

    const leadSummary = metrics
      .slice(0, 3)
      .map((metric) => `${metric.label} ${metric.value.display}`)
      .join("、");

    const body =
      attentionItems.length > 0 || snapshotPartialNote
        ? `当前先看 ${leadSummary}，但首页仍存在需要人工确认的治理提示。首屏可以做方向性判断，正式结论仍应在专题页复核。`
        : `当前先看 ${leadSummary}。首页负责先给状态判断和优先级排序，需要原因链条时，再进入债券分析、跨资产驱动和资产负债分析继续下钻。`;

    return {
      title: "全局判断",
      body,
      bullets,
      tags,
    };
  }, [
    adapterOutput.attribution.vm?.segments,
    adapterOutput.overview.vm?.metrics,
    attentionItems,
    client.mode,
    snapshotPartialNote,
  ]);

  const dashboardAlerts = useMemo<DashboardAlert[]>(() => {
    const alerts: DashboardAlert[] = [];
    const metrics = adapterOutput.overview.vm?.metrics ?? [];

    if (client.mode !== "real") {
      alerts.push({
        id: "mock-mode",
        title: "当前处于 Mock 模式",
        detail: "首屏数字仅用于界面演示，不应直接作为业务判断依据。",
        severity: "high",
      });
    }

    attentionItems.forEach((item, index) => {
      alerts.push({
        id: `attention-${index}`,
        title: "治理状态待复核",
        detail: item,
        severity: "high",
      });
    });

    if (snapshotPartialNote) {
      alerts.push({
        id: "partial-note",
        title: "快照含缺域",
        detail: snapshotPartialNote,
        severity: "medium",
      });
    }

    metrics
      .filter((metric) => metric.tone === "warning" || metric.tone === "negative")
      .slice(0, 3)
      .forEach((metric) => {
        alerts.push({
          id: `metric-${metric.id}`,
          title: metric.label,
          detail: `${metric.value.display} / ${metric.detail}`,
          severity: metric.tone === "negative" ? "high" : "medium",
        });
      });

    if (alerts.length === 0) {
      alerts.push({
        id: "no-strong-alert",
        title: "当前无强治理预警",
        detail: "可以先基于首屏指标做方向性判断，再按模块下钻核实来源。",
        severity: "low",
      });
    }

    return alerts.slice(0, 4);
  }, [
    adapterOutput.overview.vm?.metrics,
    attentionItems,
    client.mode,
    snapshotPartialNote,
  ]);

  return (
    <section data-testid="fixed-income-dashboard-page">
      <PageHeader
        title="驾驶舱"
        eyebrow="Dashboard Overview"
        description={`观察日期 ${effectiveReportDate || "latest"}。首页先做状态判断、风险分流和专题下钻，不在首屏堆叠所有明细。`}
        badgeLabel={client.mode === "real" ? "管理视角" : "演示视角"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
        style={{
          padding: `${designTokens.space[6] + designTokens.space[1]}px clamp(${designTokens.space[5]}px, 2vw, ${designTokens.space[7] - designTokens.space[1]}px)`,
          borderRadius: designTokens.space[7],
          border: `1px solid ${shellTokens.colorBorder}`,
          background: `linear-gradient(180deg, ${designTokens.color.primary[50]} 0%, ${designTokens.color.neutral[50]} 100%)`,
          boxShadow: designTokens.shadow.panel,
        }}
        actions={
          <div
            style={{
              display: "grid",
              gap: designTokens.space[4] - designTokens.space[1],
              justifyItems: "end",
            }}
          >
            <div
              style={{
                display: "flex",
                gap: designTokens.space[2] + designTokens.space[1],
                flexWrap: "wrap",
              }}
            >
              <button
                type="button"
                onClick={() => void snapshotQuery.refetch()}
                style={headerButtonStyle("primary")}
              >
                刷新
              </button>
              <button
                type="button"
                disabled
                style={{
                  ...headerButtonStyle("secondary"),
                  opacity: 0.64,
                  cursor: "not-allowed",
                }}
              >
                导出
              </button>
            </div>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: designTokens.space[4],
                alignItems: "end",
              }}
            >
              <label style={{ display: "grid", gap: designTokens.space[2] }}>
                <span style={{ color: shellTokens.colorTextMuted, fontSize: designTokens.fontSize[12] }}>
                  报告日
                </span>
                <input
                  aria-label="报告日"
                  type="date"
                  value={reportDate}
                  onChange={(event) => setReportDate(event.target.value)}
                  style={{
                    minWidth: designTokens.space[4] * 11,
                    padding: `${designTokens.space[3]}px ${designTokens.space[3]}px`,
                    borderRadius: designTokens.radius.sm + designTokens.space[2],
                    border: `1px solid ${shellTokens.colorBorder}`,
                    background: shellTokens.colorBgCanvas,
                    color: shellTokens.colorTextPrimary,
                    boxShadow: `inset 0 1px 0 ${designTokens.color.neutral[100]}`,
                    ...tabularNumsStyle,
                  }}
                />
              </label>
              <label
                style={{
                  display: "flex",
                  gap: designTokens.space[2],
                  alignItems: "center",
                  color: shellTokens.colorTextPrimary,
                  fontSize: designTokens.fontSize[13],
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
          </div>
        }
      >
        <div style={{ display: "grid", gap: designTokens.space[4] + designTokens.space[2] }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: designTokens.space[2] + designTokens.space[1],
            }}
          >
            {[
              "范围 / 驾驶舱首屏",
              "口径 / 受治理快照",
              `模式 / ${client.mode === "real" ? "live" : "mock"}`,
              `缺域 / ${allowPartial ? "允许" : "关闭"}`,
            ].map((chip) => (
              <span
                key={chip}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: `${designTokens.space[2]}px ${designTokens.space[3]}px`,
                  borderRadius: 999,
                  background: designTokens.color.primary[50],
                  border: `1px solid ${shellTokens.colorBorderSoft}`,
                  color: shellTokens.colorTextSecondary,
                  fontSize: designTokens.fontSize[12],
                  fontWeight: 700,
                }}
              >
                {chip}
              </span>
            ))}
          </div>
          <DashboardOverviewHeroStrip metrics={heroMetrics} />
        </div>
      </PageHeader>

      <div className="dashboard-gov-grid">
        {client.mode !== "real" || attentionItems.length > 0 || snapshotPartialNote ? (
          <section
            data-testid="dashboard-data-warning"
            style={{
              display: "grid",
              gap: designTokens.space[2] + designTokens.space[1],
              padding: designTokens.space[5],
              borderRadius: designTokens.radius.xl,
              border: `1px solid ${shellTokens.colorBorderWarning}`,
              background: shellTokens.colorBgWarningSoft,
              color: shellTokens.colorTextWarning,
              minHeight: "100%",
            }}
          >
            <div style={{ fontWeight: 800, fontSize: designTokens.fontSize[16] }}>Data Status</div>
            {client.mode !== "real" ? (
              <div style={{ fontSize: designTokens.fontSize[13], lineHeight: designTokens.lineHeight.relaxed }}>
                当前页面正在使用 mock 数据源。此时首页数字只用于界面演示，不应直接作为业务判断依据。
              </div>
            ) : null}
            {attentionItems.length > 0 ? (
              <div style={{ fontSize: designTokens.fontSize[13], lineHeight: designTokens.lineHeight.relaxed }}>
                当前首页存在需要人工留意的数据状态：{attentionItems.join("；")}
              </div>
            ) : null}
            {snapshotPartialNote ? (
              <div style={{ fontSize: designTokens.fontSize[13], lineHeight: designTokens.lineHeight.relaxed }}>
                {snapshotPartialNote}
              </div>
            ) : null}
          </section>
        ) : (
          <section
            style={{
              display: "grid",
              gap: designTokens.space[3],
              padding: designTokens.space[5],
              borderRadius: designTokens.radius.xl,
              border: `1px solid ${shellTokens.colorBorderSoft}`,
              background: `linear-gradient(180deg, ${designTokens.color.primary[50]} 0%, ${designTokens.color.neutral[50]} 100%)`,
            }}
          >
            <span
              style={{
                color: shellTokens.colorTextMuted,
                fontSize: designTokens.fontSize[11],
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Decision Focus
            </span>
            <strong
              style={{
                color: shellTokens.colorTextPrimary,
                fontSize: designTokens.fontSize[18],
                fontWeight: 800,
              }}
            >
              Keep the first screen verdict-driven
            </strong>
            <p
              style={{
                margin: 0,
                color: shellTokens.colorTextSecondary,
                fontSize: designTokens.fontSize[13],
                lineHeight: designTokens.lineHeight.relaxed,
              }}
            >
              先确认首页读链路和日期一致，再用首屏数字做方向性判断。原因链条、持仓结构和盘中上下文，都在对应专题页继续展开。
            </p>
          </section>
        )}

        <section
          style={{
            display: "grid",
            gap: designTokens.space[4] - designTokens.space[1],
            padding: designTokens.space[5],
            borderRadius: designTokens.radius.xl,
            border: `1px solid ${shellTokens.colorBorderSoft}`,
            background: `linear-gradient(180deg, ${designTokens.color.primary[50]} 0%, ${designTokens.color.neutral[50]} 100%)`,
          }}
        >
          <div
            style={{
              color: shellTokens.colorTextMuted,
              fontSize: designTokens.fontSize[11],
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
              <article
                key={item.title}
                style={{
                  display: "grid",
                  gap: designTokens.space[2],
                  padding: designTokens.space[4],
                  borderRadius: designTokens.radius.lg + designTokens.space[1],
                  border: `1px solid ${shellTokens.colorBorderSoft}`,
                  background: shellTokens.colorBgCanvas,
                  boxShadow: `inset 0 1px 0 ${designTokens.color.neutral[100]}`,
                }}
              >
                <div
                  style={{
                    fontSize: designTokens.fontSize[12],
                    fontWeight: 700,
                    color: shellTokens.colorTextPrimary,
                    letterSpacing: "0.04em",
                  }}
                >
                  {item.title}
                </div>
                <div style={{ ...tabularNumsStyle, fontSize: designTokens.fontSize[12], color: shellTokens.colorTextSecondary }}>
                  quality: {item.status.quality}
                </div>
                <div style={{ ...tabularNumsStyle, fontSize: designTokens.fontSize[12], color: shellTokens.colorTextSecondary }}>
                  {item.date.label}: {item.date.value}
                </div>
                <div style={{ ...tabularNumsStyle, fontSize: designTokens.fontSize[12], color: shellTokens.colorTextSecondary }}>
                  generated_at: {item.status.generatedAt}
                </div>
                <div style={{ ...tabularNumsStyle, fontSize: designTokens.fontSize[12], color: shellTokens.colorTextSecondary }}>
                  fallback: {item.status.fallback}
                </div>
              </article>
            ))}
          </section>
        </section>
      </div>

      <div className="dashboard-overview-command-grid">
        <DashboardGlobalJudgmentPanel judgment={globalJudgment} />
        <DashboardModuleSnapshotPanel />
        <DashboardAlertCenterPanel alerts={dashboardAlerts} />
      </div>

      <div className="dashboard-overview-support-grid">
        <section
          data-testid="dashboard-governed-surface"
          style={{
            display: "grid",
            gap: designTokens.space[4],
            padding: designTokens.space[6] + designTokens.space[1],
            borderRadius: designTokens.space[6] + designTokens.space[1],
            border: `1px solid ${shellTokens.colorBorderSoft}`,
            background: `linear-gradient(180deg, ${designTokens.color.primary[50]} 0%, ${designTokens.color.neutral[50]} 100%)`,
          }}
        >
          <PageSectionLead
            eyebrow="Contribution"
            title="经营贡献拆解"
            description="首页保留一个足够快的经营贡献视图，用来判断是否需要继续进入正式损益拆解工作台；不会在这里伪造未接入的业务结论。"
            style={{ marginTop: 0 }}
          />
          <Suspense fallback={<LazyPanelFallback title="经营贡献拆解" />}>
            <PnlAttributionSection
              attribution={adapterOutput.attribution}
              onRetry={() => void snapshotQuery.refetch()}
            />
          </Suspense>
        </section>

        <DashboardTasksCalendarPanels />
      </div>

      <div className="dashboard-overview-live-grid">
        <div className="dashboard-span-wide">
          <DashboardBondHeadlineSection reportDate={effectiveReportDate} />
        </div>
        <DashboardMacroSpotSection />
        <DashboardNewsDigestSection />
        <DashboardBondCounterpartySection reportDate={effectiveReportDate} />
        <DashboardLiabilityCounterpartySection reportDate={effectiveReportDate} />
      </div>

      <DashboardModuleEntryGrid />

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
    </section>
  );
}
