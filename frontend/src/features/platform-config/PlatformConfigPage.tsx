import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import type { HealthCheckStatus, HealthResponse, SourcePreviewSummary } from "../../api/contracts";
import { shellTokens as t } from "../../theme/tokens";
import { AsyncSection } from "../executive-dashboard/components/AsyncSection";
import { PlaceholderCard } from "../workbench/components/PlaceholderCard";

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

function resolveCheck(
  data: HealthResponse,
  key: "duckdb" | "redis" | "postgresql",
): HealthCheckStatus {
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

export default function PlatformConfigPage() {
  const client = useApiClient();

  const healthQuery = useQuery({
    queryKey: ["platform-config", "health", client.mode],
    queryFn: () => client.getHealth(),
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
  const envLabel = health ? environmentLabel(health) : "—";

  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <h1
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

      <div style={{ display: "grid", gap: 24 }}>
        <AsyncSection
          title="系统健康状态"
          isLoading={healthQuery.isLoading}
          isError={healthQuery.isError}
          isEmpty={false}
          onRetry={() => void healthQuery.refetch()}
        >
          {health && duck && redis && pg ? (
            <div style={healthGridStyle}>
              <PlaceholderCard
                title="DuckDB 状态"
                value={duck.ok ? "正常" : "异常"}
                detail={duck.detail}
                valueVariant="text"
                surfaceTone={duck.ok ? "ok" : "error"}
              />
              <PlaceholderCard
                title="Redis 状态"
                value={redis.ok ? "正常" : "异常"}
                detail={redis.detail}
                valueVariant="text"
                surfaceTone={redis.ok ? "ok" : "error"}
              />
              <PlaceholderCard
                title="PostgreSQL 状态"
                value={pg.ok ? "正常" : "异常"}
                detail={pg.detail}
                valueVariant="text"
                surfaceTone={pg.ok ? "ok" : "error"}
              />
              <PlaceholderCard
                title="系统环境"
                value={envLabel}
                detail="部署/运行环境标识（后端返回时展示）。"
                valueVariant="text"
                surfaceTone="default"
              />
            </div>
          ) : null}
        </AsyncSection>

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
