import type {
  ResultMeta,
  SourcePreviewSummary,
  CubeDimensionsPayload,
  HealthResponse,
} from "../../../api/contracts";
import {
  metaLabel,
  buildDetailPanel,
} from "./moduleHomePresentation";
import type {
  ModuleHomeTone,
  ModuleHomeDetailRow,
  ModuleHomeDetailPanel,
} from "./moduleHomeDetailTypes";
import { EM_DASH } from "../../../utils/format";
import type {
  ModuleHomeSourceQueries,
  ModuleHomeView,
} from "./moduleHomeModel";
import {
  queryStatus,
  combinedQueryStatus,
  hasError,
  hasLoading,
  baseDataNote,
} from "./moduleHomeSourceState";
import {
  forbiddenOnlyPageState,
  cubeDimensionsMissingDetail,
} from "./moduleHomeQueryPermission";

function governanceSourceMeta(meta: ResultMeta | undefined): string {
  return `来源 source-foundation · ${metaLabel(meta)}`;
}

function governanceCubeMeta(factTable: string): string {
  return `来源 cube / ${factTable}`;
}

function governanceSourceRowOk(summary: SourcePreviewSummary): boolean {
  return summary.total_rows > 0 && summary.manual_review_count === 0;
}

function governanceSourceStatus(summary: SourcePreviewSummary): {
  label: string;
  tone: ModuleHomeTone;
} {
  if (governanceSourceRowOk(summary)) {
    return { label: "正常", tone: "ok" };
  }
  if (summary.manual_review_count > 0) {
    return { label: `待复核 ${summary.manual_review_count}`, tone: "watch" };
  }
  if (summary.total_rows === 0) {
    return { label: "无数据", tone: "watch" };
  }
  return { label: "需关注", tone: "watch" };
}

function buildGovernanceSourceRows(sources: SourcePreviewSummary[]): ModuleHomeDetailRow[] {
  return sources.slice(0, 10).map((summary, index) => {
    const status = governanceSourceStatus(summary);
    const versionParts = [summary.source_version, summary.rule_version].filter(Boolean);
    return {
      key: `source-${summary.source_family}-${index}`,
      label: summary.source_family.toUpperCase(),
      value: status.label,
      tradeDate: summary.report_date ?? summary.batch_created_at ?? EM_DASH,
      source:
        versionParts.length > 0
          ? `版本 ${versionParts.join(" / ")} · 行数 ${summary.total_rows}`
          : `行数 ${summary.total_rows}`,
      tone: status.tone,
    };
  });
}

function buildGovernanceCubeRows(dims: CubeDimensionsPayload): ModuleHomeDetailRow[] {
  const rows: ModuleHomeDetailRow[] = [
    {
      key: "cube-fact-table",
      label: "事实表",
      value: dims.fact_table,
      tradeDate: EM_DASH,
      source: "fact_table",
      tone: "ok",
    },
  ];

  for (const dimension of dims.dimensions) {
    if (rows.length >= 10) {
      break;
    }
    rows.push({
      key: `cube-dim-${dimension}`,
      label: dimension,
      value: "维度",
      tradeDate: EM_DASH,
      source: "dimensions",
      tone: "muted",
    });
  }

  for (const measure of dims.measures) {
    if (rows.length >= 10) {
      break;
    }
    rows.push({
      key: `cube-measure-${measure}`,
      label: measure,
      value: "聚合",
      tradeDate: EM_DASH,
      source: "measures",
      tone: "muted",
    });
  }

  for (const field of dims.measure_fields) {
    if (rows.length >= 10) {
      break;
    }
    rows.push({
      key: `cube-field-${field}`,
      label: field,
      value: "度量字段",
      tradeDate: EM_DASH,
      source: "measure_fields",
      tone: "muted",
    });
  }

  return rows;
}

function extractHealthCheckRows(healthData: unknown): ModuleHomeDetailRow[] {
  if (!healthData || typeof healthData !== "object") {
    return [];
  }
  const checks = (healthData as HealthResponse).checks;
  if (!checks || typeof checks !== "object") {
    return [];
  }
  return Object.entries(checks)
    .slice(0, 10)
    .map(([name, check]) => ({
      key: `health-check-${name}`,
      label: name,
      value: check.ok ? "ok" : "异常",
      tradeDate: EM_DASH,
      source: check.detail || name,
      tone: check.ok ? "ok" : "watch",
    }));
}

export function governanceView(
  queries: ModuleHomeSourceQueries,
): Omit<ModuleHomeView, "kind" | "title" | "question" | "summary" | "sourceScope"> {
  const live = queries.healthLive?.data?.status;
  const summary = queries.healthSummary?.data?.status;
  // 保留 undefined：读取失败/未返回 ≠ 0 个数据源，KPI 侧必须能区分。
  const sourceList = queries.sourceFoundation?.data?.result.sources;
  const sources = sourceList ?? [];
  const dims = queries.cubeDimensions?.data;
  const cubeFactTable = dims?.fact_table ?? "bond_analytics";

  const sourceRows = buildGovernanceSourceRows(sources);
  const sourceStatus = queryStatus(
    "source-status-detail",
    "数据源状态",
    queries.sourceFoundation,
    sourceRows.length > 0
      ? `source foundation 已返回 ${sources.length} 个 source family。`
      : "source foundation 列表为空。",
  );
  const sourcePanel = buildDetailPanel({
    key: "source-status",
    title: "数据源状态",
    meta: governanceSourceMeta(queries.sourceFoundation?.data?.result_meta),
    status: sourceStatus,
    rows: sourceRows,
  });

  const cubeRows = dims ? buildGovernanceCubeRows(dims) : [];
  const cubeStatus = queryStatus(
    "cube-dimensions-detail",
    "Cube 维度与度量",
    queries.cubeDimensions,
    cubeRows.length > 0
      ? `cube dimensions 已返回 ${dims?.dimensions.length ?? 0} 个维度。`
      : "cube dimensions 为空。",
  );
  const cubePanel = buildDetailPanel({
    key: "cube-dimensions",
    title: "Cube 维度与度量",
    meta: governanceCubeMeta(cubeFactTable),
    status: cubeStatus,
    rows: cubeRows,
  });

  const healthCheckRows = [
    ...extractHealthCheckRows(queries.healthLive?.data),
    ...extractHealthCheckRows(queries.healthSummary?.data),
  ].filter((row, index, allRows) => allRows.findIndex((item) => item.key === row.key) === index);

  const detailPanels: ModuleHomeDetailPanel[] = [sourcePanel, cubePanel];

  if (healthCheckRows.length > 0) {
    const healthCheckStatus = combinedQueryStatus(
      "health-checks-detail",
      "健康检查明细",
      [queries.healthLive, queries.healthSummary],
      `已返回 ${healthCheckRows.length} 项健康检查。`,
    );
    detailPanels.push(
      buildDetailPanel({
        key: "health-checks",
        title: "健康检查明细",
        meta: "来源 health / health/live",
        status: healthCheckStatus,
        rows: healthCheckRows,
      }),
    );
  }

  const forbiddenState = forbiddenOnlyPageState(queries);

  return {
    stateLabel: forbiddenState?.stateLabel ?? (hasError(queries) ? "读取失败" : hasLoading(queries) ? "读取中" : "已接入"),
    stateDetail: forbiddenState?.stateDetail ?? (hasError(queries)
      ? "数据中心读链路失败，不使用前端补数，可重试或进入下钻页核验。"
      : `存活探测 ${live ?? EM_DASH}，健康检查 ${summary ?? EM_DASH}，数据源 ${
          sourceList ? sourceList.length : EM_DASH
        } 个。`),
    kpis: [
      {
        key: "health-live",
        label: "存活探测",
        value: live ?? EM_DASH,
        detail: "服务进程存活状态。",
        detailTitle: "GET /health/live",
        tone: live === "ok" ? "ok" : live ? "watch" : "muted",
      },
      {
        key: "health-summary",
        label: "健康检查",
        value: summary ?? EM_DASH,
        detail: "系统健康汇总状态。",
        detailTitle: "GET /health",
        tone: summary === "ok" ? "ok" : summary ? "watch" : "muted",
      },
      {
        key: "source-count",
        label: "数据源",
        value: sourceList ? `${sourceList.length}` : EM_DASH,
        detail: sourceList ? "已接入数据源族数量。" : "数据源清单读取失败或未返回。",
        detailTitle: "getSourceFoundation",
        tone: sourceList && sourceList.length > 0 ? "ok" : "watch",
      },
      {
        key: "cube-dimensions",
        label: "Cube 维度",
        value: dims ? `${dims.dimensions.length}` : EM_DASH,
        detail: dims
          ? `事实表 ${dims.fact_table}，度量 ${dims.measures.length} 项。`
          : cubeDimensionsMissingDetail(queries.cubeDimensions),
        detailTitle: "getCubeDimensions(bond_analytics)",
        tone: dims ? "ok" : "watch",
      },
    ],
    statuses: [
      queryStatus("health-live", "实时健康", queries.healthLive, "live probe 已返回。"),
      queryStatus("source", "数据源状态", queries.sourceFoundation, "source foundation 已返回。"),
      queryStatus("cube", "自助查询", queries.cubeDimensions, "cube dimensions 已返回。"),
      {
        key: "reports",
        label: "报表中心",
        value: "规划中",
        detail: "未接入统一报表后端接口，不伪造报表数据。",
        tone: "watch",
      },
    ],
    briefings: [
      {
        title: "系统健康",
        conclusion: `存活探测 ${live ?? EM_DASH}，健康检查 ${summary ?? EM_DASH}。`,
        evidence: "来自既有健康检查读链路。",
        tone: live === "ok" && summary === "ok" ? "ok" : "watch",
      },
      {
        title: "数据源状态",
        conclusion: sources.length > 0 ? `已返回 ${sources.length} 个数据源族。` : "暂无数据源清单。",
        evidence: "使用 source foundation 读链路，不在首页扫描数据库。",
        tone: sources.length > 0 ? "ok" : "watch",
      },
      {
        title: "报表规划",
        conclusion: "统一报表中心仍显示规划/待接入状态。",
        evidence: "当前只保留下钻和数据说明，不构造报表 payload。",
        tone: "watch",
      },
    ],
    detailPanels,
    dataNote: baseDataNote("governance", queries),
  };
}
