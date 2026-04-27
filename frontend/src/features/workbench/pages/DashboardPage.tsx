import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ResultMeta, VerdictPayload } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { PageHeader, PageSectionLead } from "../../../components/page/PagePrimitives";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { shellTokens } from "../../../theme/tokens";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import { AsyncSection } from "../../executive-dashboard/components/AsyncSection";
import { DashboardBondCounterpartySection } from "../../executive-dashboard/components/DashboardBondCounterpartySection";
import { DashboardBondHeadlineSection } from "../../executive-dashboard/components/DashboardBondHeadlineSection";
import { DashboardLiabilityCounterpartySection } from "../../executive-dashboard/components/DashboardLiabilityCounterpartySection";
import { DashboardMacroSpotSection } from "../../executive-dashboard/components/DashboardMacroSpotSection";
import { DashboardNewsDigestSection } from "../../executive-dashboard/components/DashboardNewsDigestSection";
import {
  DashboardAlertCenterPanel,
  type DashboardCalendarPanelState,
  DashboardGlobalJudgmentPanel,
  DashboardModuleEntryGrid,
  DashboardModuleSnapshotPanel,
  DashboardOverviewHeroStrip,
  DashboardTasksCalendarPanels,
  type DashboardAlert,
  type DashboardHeroMetric,
} from "../dashboard/DashboardOverviewSections";
import { GovernancePills, type GovernancePill } from "../dashboard/GovernancePills";
import { buildDashboardKeyCalendarModel } from "../dashboard/keyCalendarModel";
import { buildDashboardTodoTasksFromAlerts } from "../dashboard/dashboardTodoModel";

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

function metaQualityLabel(value: ResultMeta["quality_flag"]): string {
  if (value === "ok") return "正常";
  if (value === "warning") return "预警";
  if (value === "error") return "错误";
  if (value === "stale") return "陈旧";
  return value;
}

function metaVendorLabel(value: ResultMeta["vendor_status"]): string {
  if (value === "ok") return "正常";
  if (value === "vendor_stale") return "供应商数据陈旧";
  if (value === "vendor_unavailable") return "供应商不可用";
  return value;
}

function metaFallbackLabel(value: ResultMeta["fallback_mode"]): string {
  if (value === "none") return "未降级";
  if (value === "latest_snapshot") return "最新快照降级";
  return value;
}

function describeAttention(meta: ResultMeta | null | undefined, title: string) {
  if (!meta || !isAttentionMeta(meta)) {
    return null;
  }

  const parts = [title, metaQualityLabel(meta.quality_flag)];
  if (meta.fallback_mode !== "none") {
    parts.push(`降级=${metaFallbackLabel(meta.fallback_mode)}`);
  }
  if (meta.vendor_status !== "ok") {
    parts.push(`供应商=${metaVendorLabel(meta.vendor_status)}`);
  }
  return parts.join(" / ");
}

function headerButtonStyle(kind: "primary" | "secondary") {
  const isPrimary = kind === "primary";
  return {
    height: 28,
    padding: "0 12px",
    borderRadius: 4,
    border: isPrimary
      ? `1px solid ${shellTokens.colorAccent}`
      : `1px solid ${shellTokens.colorBorderSoft}`,
    background: isPrimary ? shellTokens.colorAccentSoft : "#ffffff",
    color: isPrimary ? shellTokens.colorAccent : shellTokens.colorTextSecondary,
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    lineHeight: 1,
  } as const;
}

function formatSnapshotMode(
  mode: string | undefined,
  isLoading: boolean,
): string {
  if (isLoading) return "载入中";
  if (!mode) return "待定";
  if (mode === "partial") return "部分可用";
  if (mode === "complete") return "完整";
  return mode;
}

function formatHeroDelta(display: string | undefined, fallbackLabel: string) {
  if (display && display.trim() && display.trim() !== "—") {
    return display;
  }
  return fallbackLabel;
}

const DASHBOARD_KEY_CALENDAR_LOOKBACK_DAYS = 7;
const DASHBOARD_KEY_CALENDAR_FORWARD_DAYS = 14;

function addDaysToIsoDate(date: string, days: number): string {
  const trimmed = date.trim();
  if (!trimmed) {
    return "";
  }
  const parsed = new Date(`${trimmed}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return trimmed;
  }
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

function todayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
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
        verdictPayload: snapshotQuery.data?.result.verdict ?? null,
      }),
    [
      overviewEnv,
      attributionEnv,
      snapshotQuery.isLoading,
      snapshotQuery.isError,
      snapshotQuery.data?.result.verdict,
    ],
  );

  const overviewMeta = adapterOutput.overview.meta;
  const attributionMeta = adapterOutput.attribution.meta;
  const attentionItems = [
    describeAttention(overviewMeta, "总览"),
    describeAttention(attributionMeta, "归因"),
  ].filter((item): item is string => Boolean(item));

  const snapshotResult = snapshotQuery.data?.result;
  const effectiveReportDate = useMemo(() => {
    const snap = snapshotResult?.report_date?.trim();
    const manual = reportDate.trim();
    return snap || manual || "";
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

  const calendarAnchorDate = todayIsoDate();
  const calendarStartDate = addDaysToIsoDate(
    calendarAnchorDate,
    -DASHBOARD_KEY_CALENDAR_LOOKBACK_DAYS,
  );
  const calendarEndDate = addDaysToIsoDate(
    calendarAnchorDate,
    DASHBOARD_KEY_CALENDAR_FORWARD_DAYS,
  );

  const researchCalendarQuery = useQuery({
    queryKey: ["research-calendar", client.mode, calendarStartDate, calendarEndDate],
    queryFn: () =>
      client.getResearchCalendarEvents(
        client.mode === "real"
          ? {
              startDate: calendarStartDate,
              endDate: calendarEndDate,
            }
          : { startDate: calendarStartDate, endDate: calendarEndDate },
      ),
    retry: false,
  });

  const sanitizedOverviewMetrics = useMemo(
    () =>
      (adapterOutput.overview.vm?.metrics ?? []).map((metric) =>
        sanitizeMetricCopy(metric),
      ),
    [adapterOutput.overview.vm?.metrics],
  );

  const heroMetrics = useMemo<DashboardHeroMetric[]>(() => {
    return sanitizedOverviewMetrics
      .map((metric) => ({
        id: metric.id,
        label: metric.label,
        caliberLabel: metric.caliberLabel,
        value: metric.value.display,
        note: metric.detail,
        delta: formatHeroDelta(metric.delta.display, "读链路"),
        tone: metric.tone,
        history: metric.history,
      }))
      .slice(0, 4);
  }, [sanitizedOverviewMetrics]);

  const governancePills = useMemo<GovernancePill[]>(() => {
    const dateValue = effectiveReportDate || "最新可用";
    const dateHint = snapshotResult?.report_date
      ? `归属日期 ${snapshotResult.report_date}`
      : "用户选择 / 默认日期";

    const snapshotMode = formatSnapshotMode(
      snapshotResult?.mode,
      snapshotQuery.isLoading,
    );
    const snapshotValue = snapshotPartialNote ? "含缺域" : snapshotMode;
    const snapshotHint =
      snapshotPartialNote ?? "首页首屏只保留已落地的受治理结果";

    const attentionValue =
      attentionItems.length > 0 ? `${attentionItems.length} 项关注` : "通过";
    const attentionHint =
      attentionItems.length > 0
        ? attentionItems.join(" / ")
        : "无质量、降级或供应商警示";

    const sourceValue = client.mode === "real" ? "真实链路" : "模拟演示";
    const sourceHint =
      client.mode === "real" ? "正式接口" : "仅用于界面演示，不应作为业务判断依据";

    return [
      { id: "report-date", label: "报告日", value: dateValue, tone: "info", hint: dateHint },
      {
        id: "snapshot",
        label: "快照",
        value: snapshotValue,
        tone: snapshotPartialNote ? "warning" : "ok",
        hint: snapshotHint,
      },
      {
        id: "attention",
        label: "治理",
        value: attentionValue,
        tone: attentionItems.length > 0 ? "warning" : "ok",
        hint: attentionHint,
      },
      {
        id: "source",
        label: "读链路",
        value: sourceValue,
        tone: client.mode === "real" ? "ok" : "warning",
        hint: sourceHint,
      },
    ];
  }, [
    attentionItems,
    client.mode,
    effectiveReportDate,
    snapshotPartialNote,
    snapshotQuery.isLoading,
    snapshotResult?.mode,
    snapshotResult?.report_date,
  ]);

  const fallbackVerdict = useMemo<VerdictPayload>(
    () => ({
      conclusion:
        client.mode !== "real" || snapshotPartialNote || attentionItems.length > 0
          ? "数据状态需先复核，再做方向性判断"
          : "当前指标平稳，等待下一组观测",
      tone:
        client.mode !== "real" || snapshotPartialNote || attentionItems.length > 0
          ? "warning"
          : "neutral",
      reasons: [],
      suggestions: [],
    }),
    [client.mode, snapshotPartialNote, attentionItems.length],
  );

  const dashboardAlerts = useMemo<DashboardAlert[]>(() => {
    const alerts: DashboardAlert[] = [];
    const metrics = sanitizedOverviewMetrics;

    if (client.mode !== "real") {
      alerts.push({
        id: "mock-mode",
        title: "当前处于模拟模式",
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
    sanitizedOverviewMetrics,
    attentionItems,
    client.mode,
    snapshotPartialNote,
  ]);

  const dashboardCalendar = useMemo(
    () =>
      buildDashboardKeyCalendarModel({
        events: researchCalendarQuery.data,
        isLoading:
          !effectiveReportDate ||
          (researchCalendarQuery.isLoading && !researchCalendarQuery.data),
        isError: researchCalendarQuery.isError,
      }),
    [
      effectiveReportDate,
      researchCalendarQuery.data,
      researchCalendarQuery.isError,
      researchCalendarQuery.isLoading,
    ],
  );

  const dashboardCalendarState = useMemo<DashboardCalendarPanelState>(
    () => ({
      status: dashboardCalendar.status,
      message: dashboardCalendar.message,
    }),
    [dashboardCalendar.message, dashboardCalendar.status],
  );

  const dashboardTasks = useMemo(
    () => buildDashboardTodoTasksFromAlerts(dashboardAlerts),
    [dashboardAlerts],
  );

  return (
    <section data-testid="fixed-income-dashboard-page">
      <PageHeader
        title="驾驶舱"
        eyebrow="总览驾驶舱"
        description={`观察日期 ${effectiveReportDate || "最新可用"}。首页先做状态判断、风险分流和专题下钻，不在首屏堆叠所有明细。`}
        badgeLabel={client.mode === "real" ? "管理视角" : "演示视角"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
        style={{
          padding: `${designTokens.space[5]}px ${designTokens.space[5]}px`,
          borderRadius: designTokens.radius.md,
          border: `1px solid ${shellTokens.colorBorderSoft}`,
          background: "#ffffff",
        }}
        actions={
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
              alignItems: "center",
              justifyContent: "flex-end",
            }}
          >
            <label
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                color: shellTokens.colorTextMuted,
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              报告日
              <input
                aria-label="报告日"
                type="date"
                value={reportDate}
                onChange={(event) => setReportDate(event.target.value)}
                style={{
                  height: 28,
                  padding: "0 8px",
                  borderRadius: 4,
                  border: `1px solid ${shellTokens.colorBorderSoft}`,
                  background: "#ffffff",
                  color: shellTokens.colorTextPrimary,
                  fontSize: 12,
                  ...tabularNumsStyle,
                }}
              />
            </label>
            <label
              style={{
                display: "inline-flex",
                gap: 6,
                alignItems: "center",
                color: shellTokens.colorTextSecondary,
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              <input
                aria-label="允许历史日（含缺域）"
                type="checkbox"
                checked={allowPartial}
                onChange={(event) => setAllowPartial(event.target.checked)}
                style={{ margin: 0 }}
              />
              含缺域
            </label>
            <span
              aria-hidden="true"
              style={{
                width: 1,
                height: 18,
                background: shellTokens.colorBorderSoft,
                margin: "0 4px",
              }}
            />
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
                opacity: 0.5,
                cursor: "not-allowed",
              }}
            >
              导出
            </button>
          </div>
        }
      >
        <div style={{ display: "grid", gap: designTokens.space[3] }}>
          <GovernancePills pills={governancePills} />
          <DashboardOverviewHeroStrip metrics={heroMetrics} />
        </div>
      </PageHeader>

      {(client.mode !== "real" || attentionItems.length > 0 || snapshotPartialNote) && (
        <section
          data-testid="dashboard-data-warning"
          className="dashboard-gov-grid"
          style={{
            display: "grid",
            gap: 6,
            padding: "10px 14px",
            borderRadius: designTokens.radius.sm,
            border: `1px solid ${shellTokens.colorBorderWarning}`,
            background: shellTokens.colorBgWarningSoft,
            color: shellTokens.colorTextWarning,
          }}
        >
          <div style={{ fontWeight: 700, fontSize: designTokens.fontSize[12], letterSpacing: "0.04em" }}>
            数据状态 · 需人工复核
          </div>
          {client.mode !== "real" ? (
            <div style={{ fontSize: 12, lineHeight: 1.5 }}>
              当前页面正在使用模拟数据源，首页数字仅用于界面演示，不应直接作为业务判断依据。
            </div>
          ) : null}
          {attentionItems.length > 0 ? (
            <div style={{ fontSize: 12, lineHeight: 1.5 }}>
              {attentionItems.join("；")}
            </div>
          ) : null}
          {snapshotPartialNote ? (
            <div style={{ fontSize: 12, lineHeight: 1.5 }}>
              {snapshotPartialNote}
            </div>
          ) : null}
        </section>
      )}

      <div className="dashboard-overview-command-grid">
        <DashboardGlobalJudgmentPanel
          verdict={adapterOutput.verdict ?? fallbackVerdict}
        />
        <DashboardModuleSnapshotPanel />
        <DashboardAlertCenterPanel alerts={dashboardAlerts} />
      </div>

      <div className="dashboard-overview-support-grid">
        <section
          data-testid="dashboard-governed-surface"
          style={{
            display: "grid",
            gap: designTokens.space[3],
            padding: designTokens.space[4],
            borderRadius: designTokens.radius.md,
            border: `1px solid ${shellTokens.colorBorderSoft}`,
            background: "#ffffff",
          }}
        >
          <PageSectionLead
            eyebrow="经营贡献"
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

        <DashboardTasksCalendarPanels
          tasks={dashboardTasks}
          calendarItems={dashboardCalendar.items}
          calendarState={dashboardCalendarState}
        />
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

    </section>
  );
}
