import { useQuery } from "@tanstack/react-query";

import {
  fetchDataHealth,
  type DataHealthFetchResult,
  type DataHealthPayload,
  type DataHealthSection,
} from "../../../api/dataHealthClient";
import { EM_DASH } from "../../../utils/format";
import "./StockAnalysisDataHealthCard.css";

/**
 * 「数据健康」紧凑卡：网络断供期"哪里带病、缺口多大"的聚合体温计。
 *
 * 数据健康是系统级信息，先落在股票分析页(主要工作页)，后续可迁独立页。
 * 自包含加载：挂载即拉 GET /api/data-health。
 * 五态：loading 骨架占位(防重排) / 后端明确空或能力不存在(404) → 整面收缩隐藏 /
 * 请求失败 → 一行错误+重试 / ready 正常呈现。
 * 每 section 一行：状态点 + 标签 + 指标，detail 作 tooltip；
 * 整体状态徽章由最差项决定(后端 overall_status，缺失时前端按严重度回退推导)。
 */

export type StockAnalysisDataHealthCardProps = {
  /** 测试/接线注入的加载函数；缺省直连真实端点(同源相对路径)。 */
  loadHealth?: () => Promise<DataHealthFetchResult>;
};

const STATUS_PRESENTATION: Record<string, { label: string; severity: number }> = {
  ok: { label: "正常", severity: 0 },
  warn: { label: "警告", severity: 1 },
  stale: { label: "陈旧", severity: 2 },
  missing: { label: "缺失", severity: 3 },
  error: { label: "异常", severity: 4 },
};

/** 后端 label 为技术词(如 "tradestatus 词表")时按 key 换成业务语言(§7 一页一语域)。 */
const SECTION_LABEL_OVERRIDES: Record<string, string> = {
  tradestatus_vocabulary: "交易状态词表",
};

function sectionLabel(section: DataHealthSection): string {
  const key = section.key?.trim() ?? "";
  return SECTION_LABEL_OVERRIDES[key] ?? section.label ?? EM_DASH;
}

function statusPresentation(status: string | null | undefined): { label: string; severity: number } {
  if (!status) return { label: "未知", severity: 4 };
  return STATUS_PRESENTATION[status] ?? { label: status, severity: 4 };
}

/** 展示回退：后端 overall_status 缺失时按最差 section 推导(仅用于徽章)。 */
function overallStatus(payload: DataHealthPayload, sections: DataHealthSection[]): string {
  if (payload.overall_status && STATUS_PRESENTATION[payload.overall_status]) {
    return payload.overall_status;
  }
  let worst = "ok";
  for (const section of sections) {
    const status = section.status ?? "error";
    if (statusPresentation(status).severity > statusPresentation(worst).severity) {
      worst = status;
    }
  }
  return worst;
}

function HealthRow({ section }: { section: DataHealthSection }) {
  return (
    <li
      className="stock-analysis-data-health__row"
      data-testid={`stock-analysis-data-health-row-${section.key ?? "unknown"}`}
      data-status={section.status ?? undefined}
      title={section.detail ?? undefined}
    >
      <span
        className="stock-analysis-data-health__dot"
        data-status={section.status ?? "error"}
        aria-hidden="true"
      />
      <span className="stock-analysis-data-health__label">{sectionLabel(section)}</span>
      <span className="stock-analysis-data-health__metric">{section.metric ?? EM_DASH}</span>
    </li>
  );
}

export function StockAnalysisDataHealthCard({ loadHealth }: StockAnalysisDataHealthCardProps) {
  const healthQuery = useQuery({
    queryKey: ["data-health", "overview"],
    queryFn: () => (loadHealth ?? fetchDataHealth)(),
    retry: false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
  const result = healthQuery.data;
  const payload = result?.kind === "ok" ? result.payload : undefined;
  const sections = (payload?.sections ?? []).filter(
    (section): section is DataHealthSection => Boolean(section),
  );

  if (healthQuery.isPending && !result) {
    return (
      <section
        className="stock-analysis-data-health stock-analysis-data-health--placeholder"
        data-testid="stock-analysis-data-health-loading"
        aria-label="数据健康加载中"
      >
        <header className="stock-analysis-data-health__head">
          <div className="stock-analysis-data-health__title-group">
            <h3>数据健康</h3>
            <span className="stock-analysis-data-health__as-of">加载中…</span>
          </div>
        </header>
        <div className="stock-analysis-data-health__skeleton" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  }

  if (healthQuery.isError || result?.kind === "error") {
    const reason =
      result?.kind === "error"
        ? result.reason
        : healthQuery.error instanceof Error
          ? healthQuery.error.message
          : String(healthQuery.error);
    return (
      <section
        className="stock-analysis-data-health stock-analysis-data-health--placeholder"
        data-testid="stock-analysis-data-health-error"
        aria-label="数据健康加载失败"
      >
        <header className="stock-analysis-data-health__head">
          <div className="stock-analysis-data-health__title-group">
            <h3>数据健康</h3>
          </div>
        </header>
        <p className="stock-analysis-data-health__error-line" role="alert" title={reason}>
          <span>健康面加载失败，请重试。</span>
          <button
            type="button"
            data-testid="stock-analysis-data-health-retry"
            onClick={() => void healthQuery.refetch()}
          >
            重试
          </button>
        </p>
      </section>
    );
  }

  // 仅后端明确空/能力不存在或 sections 为空时收缩隐藏。
  if (result?.kind === "missing" || sections.length === 0 || !payload) return null;

  const overall = overallStatus(payload, sections);

  return (
    <details
      className="stock-analysis-data-health"
      data-testid="stock-analysis-data-health"
      aria-label="数据健康总览"
      open={overall !== "ok"}
    >
      <summary className="stock-analysis-data-health__head">
        <div className="stock-analysis-data-health__title-group">
          <h3>数据健康</h3>
          <span className="stock-analysis-data-health__as-of">
            评估日 {payload.as_of_date ?? EM_DASH}
          </span>
        </div>
        <span
          className="stock-analysis-data-health__overall"
          data-testid="stock-analysis-data-health-overall"
          data-status={overall}
          title={payload.threshold_note ?? undefined}
        >
          {statusPresentation(overall).label}
        </span>
      </summary>
      <ul className="stock-analysis-data-health__rows">
        {sections.map((section, index) => (
          <HealthRow key={section.key ?? index} section={section} />
        ))}
      </ul>
    </details>
  );
}
