import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../api/client";
import type {
  HealthCheckStatus,
  HealthResponse,
  HealthStatusResponse,
  SourcePreviewSummary,
} from "../../api/contracts";
import { KpiCard } from "../../components/KpiCard";
import {
  EvidencePanel,
  PageHeader,
  PageSectionLead,
  PageStateSurface,
} from "../../components/page/PagePrimitives";
import { SkeletonBarStack } from "../../components/SkeletonBars";
import { EM_DASH } from "../../utils/format";

import styles from "./PlatformConfigPage.module.css";

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
    return EM_DASH;
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
    return { value: EM_DASH, tone: "default" };
  }
  const text = String(s);
  return { value: text, tone: text === "ok" ? "positive" : "default" };
}

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span className={styles.statusBadge} data-ok={ok ? "true" : "false"}>
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
  const envLabel = health ? environmentLabel(health) : EM_DASH;
  const overallStatusLabel = health?.status ? String(health.status) : EM_DASH;
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
    <section className={styles.page} data-moss-theme-scope="platform-config">
      <PageHeader
        eyebrow="报表与数据"
        title="中台配置"
        titleTestId="platform-config-page-title"
        description="系统健康状态、数据源概览与治理信息。"
        badgeLabel={client.mode === "real" ? "真实治理读链路" : "本地演示数据"}
        badgeTone={client.mode === "real" ? "positive" : "accent"}
      />

      <PageSectionLead
        eyebrow="总览"
        title="平台概览"
        description="先看系统状态、运行环境和数据源摘要，再下钻到健康检查卡片与数据源表格，保持配置页的阅读顺序与其他标准壳层一致。"
      />
      <div className={styles.kpiGrid}>
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
            detail="GET /health/live，仅展示 status"
            valueVariant="text"
            tone={liveProbe.tone}
          />
        </div>
        <div data-testid="platform-config-health-summary">
          <KpiCard
            title="简易状态"
            value={summaryProbe.value}
            detail="GET /health，仅展示 status"
            valueVariant="text"
            tone={summaryProbe.tone}
          />
        </div>
        <div data-testid="platform-config-environment-kpi">
          <KpiCard title="系统环境" value={envLabel} detail="部署/运行环境标识" valueVariant="text" />
        </div>
        <div data-testid="platform-config-source-count">
          <KpiCard title="数据源数量" value={String(sourceCount)} detail="当前源基础摘要中的来源数" />
        </div>
        <div data-testid="platform-config-abnormal-sources">
          <KpiCard title="异常来源" value={String(abnormalSourceCount)} detail="行数为 0 或仍有人工复核的来源" />
        </div>
        <div data-testid="platform-config-manual-review-rows">
          <KpiCard title="人工复核行" value={String(manualReviewRows)} detail="来源摘要中的人工复核计数汇总" />
        </div>
      </div>

      <PageStateSurface
        variant="definition-pending"
        testId="platform-config-diagnostic-boundary"
        className={styles.contractNote}
        title="PAGE-CONTRACT-PENDING:/platform-config"
        description="MTR-PLT-001、MTR-PLT-002、MTR-PLT-003 仅为候选诊断指标，来自 GET /ui/preview/source-foundation；健康状态、状态文本与环境卡片不在此列，亦不构成数据质量审批。"
      />

      <div className={styles.stack}>
        <PageSectionLead
          eyebrow="健康"
          title="系统健康状态"
          description="分项来自 GET /health/ready 的检查项（含 DuckDB / Redis / PostgreSQL / 对象存储等），与上方「系统状态」同源；存活探测与简易状态已在平台概览由 /health/live、GET /health 并列展示。"
        />
        <EvidencePanel testId="platform-config-health-section">
          {healthQuery.isLoading ? (
            <PageStateSurface variant="loading" title="正在载入系统健康状态">
              <SkeletonBarStack />
            </PageStateSurface>
          ) : healthQuery.isError ? (
            <PageStateSurface
              variant="error"
              title="数据载入失败。"
              description="当前页面保留重试入口，不在浏览器端自行拼接正式口径。"
              actions={
                <button
                  type="button"
                  className={styles.retryButton}
                  onClick={() => void healthQuery.refetch()}
                >
                  重试
                </button>
              }
            />
          ) : health && duck && redis && pg && objectStore ? (
            <div className={styles.kpiGrid}>
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
        </EvidencePanel>

        <PageSectionLead
          eyebrow="数据源"
          title="数据源列表"
          description="数据源列表继续展示最新批次、行数、更新时间和状态，作为治理页的只读汇总表。"
        />
        <EvidencePanel testId="platform-config-sources-section">
          {sourcesQuery.isLoading ? (
            <PageStateSurface variant="loading" title="正在载入数据源列表">
              <SkeletonBarStack />
            </PageStateSurface>
          ) : sourcesQuery.isError ? (
            <PageStateSurface
              variant="error"
              title="数据载入失败。"
              description="当前页面保留重试入口，不在浏览器端自行拼接正式口径。"
              actions={
                <button
                  type="button"
                  className={styles.retryButton}
                  onClick={() => void sourcesQuery.refetch()}
                >
                  重试
                </button>
              }
            />
          ) : sources.length === 0 ? (
            <PageStateSurface variant="empty" description="当前暂无可展示内容。" />
          ) : (
            <div className={styles.tableShell}>
              <table data-testid="platform-config-sources-table" className={styles.table}>
                <thead>
                  <tr>
                    <th className={styles.th} scope="col">
                      数据源名称
                    </th>
                    <th className={styles.th} scope="col">
                      最新批次
                    </th>
                    <th className={styles.th} scope="col">
                      行数
                    </th>
                    <th className={styles.th} scope="col">
                      最后更新时间
                    </th>
                    <th className={styles.th} scope="col">
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
                        <td className={styles.td}>{row.source_family.toUpperCase()}</td>
                        <td className={styles.td}>{row.ingest_batch_id ?? EM_DASH}</td>
                        <td className={`${styles.td} ${styles.tdNumeric}`}>{row.total_rows}</td>
                        <td className={`${styles.td} ${styles.tdNowrap}`}>
                          {row.batch_created_at ?? EM_DASH}
                        </td>
                        <td className={styles.td}>
                          <StatusBadge ok={ok} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </EvidencePanel>
      </div>
    </section>
  );
}
