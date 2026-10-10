import type { LivermoreCandidateHistoryRow, ResultMeta } from "../../../api/contracts";

import {
  compactStockText,
  stockSupplyFallbackLabel,
  stockSupplyQualityLabel,
  stockSupplyVendorLabel,
} from "./stockAnalysisPageCopy";

export type CandidateHistoryStats = {
  total: number;
  matured: number;
  latestDate: string | null;
  avgReturn5d: number | null;
};

export function buildCandidateHistoryStatsByCode(
  candidateHistoryByCode: Map<string, LivermoreCandidateHistoryRow[]>,
): Map<string, CandidateHistoryStats> {
  const map = new Map<string, CandidateHistoryStats>();
  candidateHistoryByCode.forEach((rows, stockCode) => {
    const matureRows = rows.filter(
      (row) => row.data_status === "complete" && typeof row.return_5d === "number" && Number.isFinite(row.return_5d),
    );
    const avgReturn5d =
      matureRows.length > 0
        ? matureRows.reduce((sum, row) => sum + (row.return_5d ?? 0), 0) / matureRows.length
        : null;
    map.set(stockCode, {
      total: rows.length,
      matured: matureRows.length,
      latestDate: rows[0]?.snapshot_as_of_date ?? null,
      avgReturn5d,
    });
  });
  return map;
}

export function buildApiLedgerSourceCells(
  backendTableCount: number,
  resultMeta: ResultMeta | null | undefined,
) {
  return [
    {
      key: "tables",
      label: "后端表",
      value: backendTableCount > 0 ? `${backendTableCount} 张` : "待返回",
      detail: resultMeta?.tables_used?.slice(0, 4).join(" / ") ?? "后端表待返回",
    },
    {
      key: "evidence",
      label: "证据行",
      value:
        typeof resultMeta?.evidence_rows === "number"
          ? resultMeta.evidence_rows.toLocaleString("zh-CN")
          : "待返回",
      detail: `质量 ${stockSupplyQualityLabel(resultMeta?.quality_flag)} / 通道 ${stockSupplyVendorLabel(
        resultMeta?.vendor_status,
      )} / ${stockSupplyFallbackLabel(resultMeta?.fallback_mode)}`,
    },
    {
      key: "rule",
      label: "规则版本",
      value: compactStockText(resultMeta?.rule_version ?? "规则待返回", 24),
      detail: resultMeta?.rule_version ?? "规则版本待返回",
    },
    {
      key: "trace",
      label: "链路",
      value: compactStockText(resultMeta?.trace_id ?? "链路待返回", 18),
      detail: resultMeta?.trace_id ?? "链路待返回",
    },
  ];
}

export function buildGateStateVariantRows() {
  return [
    {
      key: "blocked",
      title: "blocked",
      tone: "warning",
      detail: "有候选但 data_gaps 未闭合，主操作禁用，只允许只读排查。",
    },
    {
      key: "limited_review",
      title: "limited_review",
      tone: "neutral",
      detail: "存在 warning 时允许阅读证据，但复核动作需二次确认。",
    },
    {
      key: "no_data",
      title: "no_data",
      tone: "negative",
      detail: "候选队列为空时，不把 0 包装成正常，直接显示 no_data。",
    },
    {
      key: "stale-fallback",
      title: "stale/fallback",
      tone: "warning",
      detail: "回退日期或缓存口径不一致时，顶部和证据栏同步提示。",
    },
  ];
}
