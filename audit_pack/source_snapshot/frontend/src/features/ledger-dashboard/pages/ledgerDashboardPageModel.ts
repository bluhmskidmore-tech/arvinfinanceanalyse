import type {
  LedgerDashboardData,
  LedgerDirection,
  LedgerPositionItem,
  LedgerResponseMetadata,
  LedgerResponseTrace,
} from "../../../api/ledgerClient";

export type LedgerDirectionFilter = "ALL" | LedgerDirection;

export type LedgerKpiCardModel = {
  key: "asset" | "liability" | "net" | "alerts";
  label: string;
  value: string;
  detail: string;
  direction: LedgerDirectionFilter;
};

export function formatLedgerYiAmount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(2)} 亿元`;
}

export function formatLedgerYuanAmount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(value);
}

export function buildLedgerKpiCards(data: LedgerDashboardData | null | undefined): LedgerKpiCardModel[] {
  return [
    {
      key: "asset",
      label: "资产面值",
      value: formatLedgerYiAmount(data?.asset_face_amount),
      detail: "direction=ASSET，展示单位为亿元",
      direction: "ASSET",
    },
    {
      key: "liability",
      label: "发行负债面值",
      value: formatLedgerYiAmount(data?.liability_face_amount),
      detail: "direction=LIABILITY，展示单位为亿元",
      direction: "LIABILITY",
    },
    {
      key: "net",
      label: "净敞口",
      value: formatLedgerYiAmount(data?.net_face_exposure),
      detail: "ASSET - LIABILITY，后端按原始元聚合后换算",
      direction: "ALL",
    },
    {
      key: "alerts",
      label: "预警数量",
      value: data?.alert_count === null || data?.alert_count === undefined ? "--" : String(data.alert_count),
      detail: "来自 ledger dashboard metadata，缺数时不补 0",
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
  return "全部";
}

export function positionRowKey(position: LedgerPositionItem): string {
  return `${position.position_key}:${position.batch_id}:${position.row_no}`;
}

export function resolvedLedgerDate(trace: LedgerResponseTrace | null | undefined, dataDate?: string | null) {
  return trace?.resolved_as_of_date ?? dataDate ?? null;
}
