import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import { designTokens } from "../../theme/designSystem";
import { displayTokens } from "../../theme/displayTokens";
import type {
  HealthCheckStatus,
  HealthResponse,
  HealthStatusResponse,
  SourcePreviewSummary,
} from "../../api/contracts";
import { shellTokens as t } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { KpiCard } from "../workbench/components/KpiCard";

const summaryGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const healthGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: 16,
} as const;

const tableShellStyle = {
  overflowX: "auto",
  borderRadius: 16,
  border: `1px solid ${t.colorBorder}`,
  background: t.colorBgSurface,
  marginTop: 18,
} as const;

const tableStyle = {
  width: "100%",
  borderCollapse: "collapse" as const,
  fontSize: 13,
} as const;

const thStyle = {
  textAlign: "left" as const,
  padding: "10px 12px",
  borderBottom: `1px solid ${t.colorBorder}`,
  color: t.colorTextSecondary,
  fontSize: 13,
};

const tdStyle = {
  padding: "12px",
  borderBottom: `1px solid ${t.colorBgMuted}`,
  color: t.colorTextPrimary,
};

const sectionLeadWrapStyle = {
  display: "grid",
  gap: 6,
  marginTop: 28,
} as const;

const sectionEyebrowStyle = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#8090a8",
} as const;

const sectionTitleStyle = {
  margin: 0,
  fontSize: 18,
  fontWeight: 600,
  color: t.colorTextPrimary,
} as const;

const sectionDescriptionStyle = {
  margin: 0,
  maxWidth: 860,
  color: t.colorTextSecondary,
  fontSize: 13,
  lineHeight: 1.7,
} as const;

function resolveCheck(data: HealthResponse, key: string): HealthCheckStatus {
  const c = data.checks ?? {};
  const direct = c[key];
  if (direct) {
    return direct;
  }
  const allOk = data.status === "ok";
  return {
    ok: allOk,
    detail: allOk
      ? "未返回分项检查时，按整体状态推断。"
      : "整体状态异常或未返回分项检查。",
  };
}

function environmentLabel(data: HealthResponse): string {
  const raw = (data as HealthResponse & { environment?: unknown }).environment;
  if (raw === undefined || raw === null || String(raw).trim() === "") {
    return "—";
  }
  return String(raw);
}

function sourceRowOk(summary: SourcePreviewSummary): boolean {
  return summary.total_rows > 0 && summary.manual_review_count === 0;
}

function healthProbeDisplay(q: {
  isLoading: boolean;
  isError: boolean;
  data?: HealthStatusResponse;
}): { value: string; tone: "default" | "positive" | "error" } {
  if (q.isLoading) {
    return { value: "加载中…", tone: "default" };
  }
  if (q.isError) {
    return { value: "请求失败", tone: "error" };
  }
  const s = q.data?.status;
  if (s === undefined || String(s).trim() === "") {
    return { value: "—", tone: "default" };
  }
  const text = String(s);
  return { value: text, tone: text === "ok" ? "positive" : "default" };
}

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "4px 10px",
        borderRadius: 999,
        background: ok ? t.colorBgMuted : t.colorBorder,
        color: ok ? t.colorSuccess : t.colorDanger,
        fontSize: 12,
        fontWeight: 600,
        border: `1px solid ${ok ? t.colorBorderStrong : t.colorDanger}`,
      }}
    >
      {ok ? "正常" : "异常"}
    </span>
  );
}

function SectionLead(props: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div style={sectionLeadWrapStyle}>
      <span style={sectionEyebrowStyle}>{props.eyebrow}</span>
      <h2 style={sectionTitleStyle}>{props.title}</h2>
      <p style={sectionDescriptionStyle}>{props.description}</p>
    </div>
  );
}

export default function PlatformConfigPage() {
  const client = useApiClient();

  const healthQuery = useQuery({
    queryKey: ["platform-config", "health", client.mode],
    queryFn: () => client.getHealth(),
    retry: false,
  });

  const healthLiveQuery = useQuery({
    queryKey: ["platform-config", "health-live", client.mode],
    queryFn: () => client.getHealthLive(),
    retry: false,
  });

  const healthSummaryQuery = useQuery({
    queryKey: ["platform-config", "health-summary", client.mode],
    queryFn: () => client.getHealthSummary(),
    retry: false,
  });

  const sourcesQuery = useQuery({
    queryKey: ["platform-config", "source-foundation", client.mode],
    queryFn: () => client.getSourceFoundation(),
    retry: false,
  });

  const sources = useMemo(
    () => sourcesQuery.data?.result.sources ?? [],
    [sourcesQuery.data?.result.sources],
  );

  const health = healthQuery.data;

  const duck = health ? resolveCheck(health, "duckdb") : null;
  const redis = health ? resolveCheck(health, "redis") : null;
  const pg = health ? resolveCheck(health, "postgresql") : null;
  const objectStore = health ? resolveCheck(health, "object_store") : null;
  const envLabel = health ? environmentLabel(health) : "—";
  const overallStatusLabel = health?.status ? String(health.status) : "—";
  const sourceCount = sources.length;
  const abnormalSourceCount = useMemo(
    () => sources.filter((summary) => !sourceRowOk(summary)).length,
    [sources],
  );
  const manualReviewRows = useMemo(
    () => sources.reduce((sum, summary) => sum + summary.manual_review_count, 0),
    [sources],
  );

  const liveProbe = healthProbeDisplay(healthLiveQuery);
  const summaryProbe = healthProbeDisplay(healthSummaryQuery);

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <h1
            data-testid="platform-config-page-title"
            style={{
              margin: 0,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.03em",
              color: t.colorTextPrimary,
            }}
          >
            中台配置
          </h1>
          <p
            style={{
              marginTop: 10,
              marginBottom: 0,
              maxWidth: 860,
              color: t.colorTextSecondary,
              fontSize: 15,
              lineHeight: 1.75,
            }}
          >
            系统健康状态、数据源概览与治理信息。
          </p>
        </div>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "8px 12px",
            borderRadius: 999,
            background:
              client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
            color:
              client.mode === "real"
                ? displayTokens.apiMode.realForeground
                : displayTokens.apiMode.mockForeground,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {client.mode === "real" ? "真实治理读链路" : "本地演示数据"}
        </span>
      </div>

      <SectionLead
        eyebrow="总览"
        title="平台概览"
        description="先看系统状态、运行环境和数据源摘要，再下钻到健康检查卡片与数据源表格，保持配置页的阅读顺序与其他标准壳层一致。"
      />
      <div style={summaryGridStyle}>
        <div data-testid="platform-config-overall-status">
          <KpiCard
            title="系统状态"
            value={overallStatusLabel}
            detail="GET /health/ready 返回的聚合状态（就绪检查）"
            valueVariant="text"
          />
        </div>
        <div data-testid="platform-config-health-live">
          <KpiCard
            title="存活探测"
            value={liveProbe.value}
            detail="GET /health/live — 仅展示 status"
            valueVariant="text"
            tone={liveProbe.tone}
          />
        </div>
        <div data-testid="platform-config-health-summary">
          <KpiCard
            title="简易状态"
            value={summaryProbe.value}
            detail="GET /health — 仅展示 status"
            valueVariant="text"
            tone={summaryProbe.tone}
          />
        </div>
        <div data-testid="platform-config-environment-kpi">
          <KpiCard title="系统环境" value={envLabel} detail="部署/运行环境标识" valueVariant="text" />
        </div>
        <div data-testid="platform-config-source-count">
          <KpiCard title="数据源数量" value={String(sourceCount)} detail="当前源基础摘要中的来源数" valueVariant="text" />
        </div>
        <div data-testid="platform-config-abnormal-sources">
          <KpiCard title="异常来源" value={String(abnormalSourceCount)} detail="行数为 0 或仍有人工复核的来源" valueVariant="text" />
        </div>
        <div data-testid="platform-config-manual-review-rows">
          <KpiCard title="人工复核行" value={String(manualReviewRows)} detail="来源摘要中的人工复核计数汇总" valueVariant="text" />
        </div>
      </div>

      <div style={{ display: "grid", gap: 24 }}>
        <SectionLead
          eyebrow="健康"
          title="系统健康状态"
          description="分项来自 GET /health/ready 的检查项（含 DuckDB / Redis / PostgreSQL / 对象存储等），与上方「系统状态」同源；存活探测与简易状态已在平台概览由 /health/live、GET /health 并列展示。"
        />
        <AsyncSection
          title="系统健康状态"
          isLoading={healthQuery.isLoading}
          isError={healthQuery.isError}
          isEmpty={false}
          onRetry={() => void healthQuery.refetch()}
        >
          {health && duck && redis && pg && objectStore ? (
            <div style={healthGridStyle}>
              <KpiCard
                title="DuckDB 状态"
                value={duck.ok ? "正常" : "异常"}
                detail={duck.detail}
                valueVariant="text"
                tone={duck.ok ? "positive" : "error"}
              />
              <KpiCard
                title="Redis 状态"
                value={redis.ok ? "正常" : "异常"}
                detail={redis.detail}
                valueVariant="text"
                tone={redis.ok ? "positive" : "error"}
              />
              <KpiCard
                title="PostgreSQL 状态"
                value={pg.ok ? "正常" : "异常"}
                detail={pg.detail}
                valueVariant="text"
                tone={pg.ok ? "positive" : "error"}
              />
              <KpiCard
                title="对象存储"
                value={objectStore.ok ? "正常" : "异常"}
                detail={objectStore.detail}
                valueVariant="text"
                tone={objectStore.ok ? "positive" : "error"}
              />
              <KpiCard
                title="系统环境"
                value={envLabel}
                detail="部署/运行环境标识（后端返回时展示）。"
                valueVariant="text"
                tone="default"
              />
            </div>
          ) : null}
        </AsyncSection>

        <SectionLead
          eyebrow="数据源"
          title="数据源列表"
          description="数据源列表继续展示最新批次、行数、更新时间和状态，作为治理页的只读汇总表。"
        />
        <AsyncSection
          title="数据源列表"
          isLoading={sourcesQuery.isLoading}
          isError={sourcesQuery.isError}
          isEmpty={!sourcesQuery.isLoading && !sourcesQuery.isError && sources.length === 0}
          onRetry={() => void sourcesQuery.refetch()}
        >
          <div style={tableShellStyle}>
            <table data-testid="platform-config-sources-table" style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle} scope="col">
                    数据源名称
                  </th>
                  <th style={thStyle} scope="col">
                    最新批次
                  </th>
                  <th style={thStyle} scope="col">
                    行数
                  </th>
                  <th style={thStyle} scope="col">
                    最后更新时间
                  </th>
                  <th style={thStyle} scope="col">
                    状态
                  </th>
                </tr>
              </thead>
              <tbody>
                {sources.map((row, index) => {
                  const ok = sourceRowOk(row);
                  const key = `${row.source_family}:${row.ingest_batch_id ?? ""}:${index}`;
                  return (
                    <tr key={key}>
                      <td style={tdStyle}>{row.source_family.toUpperCase()}</td>
                      <td style={tdStyle}>{row.ingest_batch_id ?? "—"}</td>
                      <td style={tdStyle}>{row.total_rows}</td>
                      <td style={{ ...tdStyle, whiteSpace: "nowrap" }}>
                        {row.batch_created_at ?? "—"}
                      </td>
                      <td style={tdStyle}>
                        <StatusBadge ok={ok} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncSection>
      </div>
    </section>
  );
}
