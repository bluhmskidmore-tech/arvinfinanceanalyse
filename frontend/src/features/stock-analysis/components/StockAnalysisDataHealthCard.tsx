import { useEffect, useState } from "react";

import {
  fetchDataHealth,
  type DataHealthPayload,
  type DataHealthSection,
} from "../../../api/dataHealthClient";
import { EM_DASH } from "../../../utils/format";
import "./StockAnalysisDataHealthCard.css";

/**
 * 「数据健康」紧凑卡：网络断供期"哪里带病、缺口多大"的聚合体温计。
 *
 * 数据健康是系统级信息，先落在股票分析页(主要工作页)，后续可迁独立页。
 * 自包含加载：挂载即拉 GET /api/data-health；健康面不可用(404/失败 → null)
 * 或 sections 为空时整面隐藏(render null)，不留空壳。
 * 每 section 一行：状态点 + 标签 + 指标，detail 作 tooltip；
 * 整体状态徽章由最差项决定(后端 overall_status，缺失时前端按严重度回退推导)。
 */

type PanelPhase =
  | { status: "loading" }
  | { status: "hidden" }
  | { status: "ready"; payload: DataHealthPayload };

export type StockAnalysisDataHealthCardProps = {
  /** 测试/接线注入的加载函数；缺省直连真实端点(同源相对路径)。 */
  loadHealth?: () => Promise<DataHealthPayload | null>;
};

const STATUS_PRESENTATION: Record<string, { label: string; severity: number }> = {
  ok: { label: "正常", severity: 0 },
  warn: { label: "警告", severity: 1 },
  stale: { label: "陈旧", severity: 2 },
  missing: { label: "缺失", severity: 3 },
  error: { label: "异常", severity: 4 },
};

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
      <span className="stock-analysis-data-health__label">{section.label ?? EM_DASH}</span>
      <span className="stock-analysis-data-health__metric">{section.metric ?? EM_DASH}</span>
    </li>
  );
}

export function StockAnalysisDataHealthCard({ loadHealth }: StockAnalysisDataHealthCardProps) {
  const [phase, setPhase] = useState<PanelPhase>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    const load = loadHealth ?? (() => fetchDataHealth());
    load()
      .then((payload) => {
        if (cancelled) return;
        const sections = (payload?.sections ?? []).filter(
          (section): section is DataHealthSection => Boolean(section),
        );
        if (payload && sections.length > 0) {
          setPhase({ status: "ready", payload: { ...payload, sections } });
        } else {
          setPhase({ status: "hidden" });
        }
      })
      .catch(() => {
        if (!cancelled) setPhase({ status: "hidden" });
      });
    return () => {
      cancelled = true;
    };
  }, [loadHealth]);

  // 健康面不可用(404/失败) / sections 为空 → 整面隐藏；加载中不占位。
  if (phase.status !== "ready") return null;

  const { payload } = phase;
  const sections = (payload.sections ?? []).filter(
    (section): section is DataHealthSection => Boolean(section),
  );
  const overall = overallStatus(payload, sections);

  return (
    <section
      className="stock-analysis-data-health"
      data-testid="stock-analysis-data-health"
      aria-label="数据健康总览"
    >
      <header className="stock-analysis-data-health__head">
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
      </header>
      <ul className="stock-analysis-data-health__rows">
        {sections.map((section, index) => (
          <HealthRow key={section.key ?? index} section={section} />
        ))}
      </ul>
    </section>
  );
}
