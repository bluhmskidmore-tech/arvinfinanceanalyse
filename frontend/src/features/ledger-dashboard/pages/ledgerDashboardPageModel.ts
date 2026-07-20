import type {
  LedgerDashboardData,
  LedgerCurrencyBreakdown,
  LedgerDirection,
  LedgerImportStatus,
  LedgerPositionItem,
  LedgerResponseMetadata,
  LedgerResponseTrace,
} from "../../../api/ledgerClient";
import { EM_DASH } from "../../../utils/format";

export type LedgerDirectionFilter = "ALL" | LedgerDirection;

export type LedgerKpiCardModel = {
  key: "asset" | "liability" | "net";
  label: string;
  value: string;
  detail: string;
  direction: LedgerDirectionFilter;
};

export type LedgerImportPresentation = {
  label: string;
  tone: "pending" | "success" | "duplicate" | "failure";
};

const ledgerImportPresentations: Record<LedgerImportStatus, LedgerImportPresentation> = {
  queued: { label: "已进入导入队列", tone: "pending" },
  running: { label: "正在校验并导入", tone: "pending" },
  succeeded: { label: "导入完成", tone: "success" },
  duplicate: { label: "文件内容已存在，未新增批次", tone: "duplicate" },
  failed: { label: "导入失败", tone: "failure" },
};

export function ledgerImportPresentation(status: LedgerImportStatus): LedgerImportPresentation {
  return ledgerImportPresentations[status];
}

export function ledgerImportStatusIsTerminal(status: LedgerImportStatus): boolean {
  return status === "succeeded" || status === "duplicate" || status === "failed";
}

export function formatLedgerYiAmount(value: number | null | undefined, currency: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(2)} ${currency}/1亿`;
}

export function formatLedgerYuanAmount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return EM_DASH;
  }
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value);
}

export function selectLedgerCurrency(
  breakdown: LedgerCurrencyBreakdown[],
  requested: string | null | undefined,
): string {
  const currencies = breakdown.map((item) => item.currency).sort();
  const normalized = requested?.trim().toUpperCase();
  if (normalized && currencies.includes(normalized)) return normalized;
  if (currencies.includes("CNY")) return "CNY";
  return currencies[0] ?? "";
}

export function buildLedgerKpiCards(
  data: LedgerDashboardData | null | undefined,
  currency: string,
): LedgerKpiCardModel[] {
  const bucket = data?.currency_breakdown.find((item) => item.currency === currency);
  return [
    {
      key: "asset",
      label: "资产面值",
      value: formatLedgerYiAmount(bucket?.asset_face_amount, currency),
      detail: `导入快照候选资产分类；${currency} 原币/1亿，无 FX 换算`,
      direction: "ASSET",
    },
    {
      key: "liability",
      label: "发行负债面值",
      value: formatLedgerYiAmount(bucket?.liability_face_amount, currency),
      detail: `导入快照候选负债分类；${currency} 原币/1亿，无 FX 换算`,
      direction: "LIABILITY",
    },
    {
      key: "net",
      label: "净敞口",
      value: formatLedgerYiAmount(bucket?.net_face_exposure, currency),
      detail: `资产 - 发行负债；仅限 ${currency} 币种桶，未分类不计入`,
      direction: "ALL",
    },
  ];
}
export function ledgerDataState(
  metadata: LedgerResponseMetadata | null | undefined,
  error: unknown,
): "loading_failure" | "no_data" | "fallback" | "stale" | "ready" {
  if (error) {
    return "loading_failure";
  }
  if (metadata?.no_data) {
    return "no_data";
  }
  if (metadata?.fallback) {
    return "fallback";
  }
  if (metadata?.stale) {
    return "stale";
  }
  return "ready";
}

export function directionLabel(direction: LedgerDirectionFilter): string {
  if (direction === "ASSET") return "资产";
  if (direction === "LIABILITY") return "发行负债";
  if (direction === "UNCLASSIFIED") return "未分类";
  return "全部";
}

export function positionRowKey(position: LedgerPositionItem): string {
  return `${position.position_key}:${position.batch_id}:${position.row_no}`;
}

export function resolvedLedgerDate(trace: LedgerResponseTrace | null | undefined, dataDate?: string | null) {
  return trace?.resolved_as_of_date ?? dataDate ?? null;
}
