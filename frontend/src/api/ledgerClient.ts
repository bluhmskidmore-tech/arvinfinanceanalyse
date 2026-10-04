export type LedgerDirection = "ASSET" | "LIABILITY" | "UNCLASSIFIED";

export type LedgerResponseMetadata = {
  source_version: string | null;
  rule_version: string | null;
  batch_id: number | string | null;
  stale: boolean;
  fallback: boolean;
  no_data: boolean;
};

export type LedgerResponseTrace = {
  request_id: string;
  requested_as_of_date?: string | null;
  resolved_as_of_date?: string | null;
  batch_id: number | string | null;
  filters?: Record<string, unknown> | null;
};

export type LedgerApiResponse<TData> = {
  data: TData;
  metadata: LedgerResponseMetadata;
  trace: LedgerResponseTrace;
};

export type LedgerDatesData = {
  items: string[];
};

export type LedgerCurrencyBreakdown = {
  currency: string;
  asset_face_amount: number | null;
  liability_face_amount: number | null;
  net_face_exposure: number | null;
  classification_total_row_count: number;
  unclassified_row_count: number | null;
  unclassified_face_amount: number | null;
  classification_coverage_pct: number | null;
};

export type LedgerDashboardData = {
  as_of_date: string | null;
  classification_status: "ready" | "legacy_unassessed" | "invalid_materialization";
  classification_rule_version: string;
  currency_breakdown: LedgerCurrencyBreakdown[];
};

export type LedgerPositionItem = {
  position_key: string;
  batch_id: number | string;
  row_no: number;
  as_of_date: string;
  bond_code: string;
  bond_name: string;
  portfolio: string;
  direction: LedgerDirection;
  business_type: string;
  business_type_1: string;
  account_category_std: string;
  cost_center: string;
  asset_class_std: string;
  channel: string;
  currency: string;
  face_amount: number | null;
  fair_value: number | null;
  amortized_cost: number | null;
  accrued_interest: number | null;
  interest_receivable_payable: number | null;
  quantity: number | null;
  latest_face_value: number | null;
  interest_method: string;
  coupon_rate: number | null;
  yield_to_maturity: number | null;
  interest_start_date: string | null;
  maturity_date: string | null;
  counterparty_name_cn: string;
  legal_customer_name: string;
  group_customer_name: string;
  trace: {
    position_key: string;
    batch_id: number | string;
    row_no: number;
    ingest_batch_id?: string;
  };
};

export type LedgerPositionsData = {
  items: LedgerPositionItem[];
  page: number;
  page_size: number;
  total: number;
};

export type LedgerPositionsOptions = {
  asOfDate: string;
  direction?: LedgerDirection | null;
  bondCode?: string | null;
  portfolio?: string | null;
  accountCategoryStd?: string | null;
  assetClassStd?: string | null;
  costCenter?: string | null;
  currency?: string | null;
  page?: number;
  pageSize?: number;
};

export type LedgerImportStatus = "queued" | "running" | "succeeded" | "duplicate" | "failed";

export type LedgerImportRunData = {
  run_id: string;
  status: LedgerImportStatus;
  file_name: string;
  batch_id?: number | null;
  duplicate_of_batch_id?: number | null;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_category?: string | null;
  error_message?: string | null;
};

export type LedgerImportResponse = {
  data: LedgerImportRunData;
  trace: {
    request_id: string;
    run_id: string;
  };
};

export class LedgerRequestError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
    readonly retryable: boolean,
  ) {
    super(message);
    this.name = "LedgerRequestError";
  }
}

export type LedgerClientMethods = {
  getLedgerDates: () => Promise<LedgerApiResponse<LedgerDatesData>>;
  getLedgerDashboard: (
    asOfDate: string,
  ) => Promise<LedgerApiResponse<LedgerDashboardData>>;
  getLedgerPositions: (
    options: LedgerPositionsOptions,
  ) => Promise<LedgerApiResponse<LedgerPositionsData>>;
  exportLedgerPositions: (options: LedgerPositionsOptions) => Promise<Blob>;
  importLedger: (file: File, signal?: AbortSignal) => Promise<LedgerImportResponse>;
  getLedgerImportStatus: (runId: string, signal?: AbortSignal) => Promise<LedgerImportResponse>;
};

type FetchLike = typeof fetch;

type LedgerClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

function buildQuery(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") {
      continue;
    }
    query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export function positionsParams(options: LedgerPositionsOptions) {
  return {
    as_of_date: options.asOfDate,
    direction: options.direction ?? undefined,
    bond_code: options.bondCode ?? undefined,
    portfolio: options.portfolio ?? undefined,
    account_category_std: options.accountCategoryStd ?? undefined,
    asset_class_std: options.assetClassStd ?? undefined,
    cost_center: options.costCenter ?? undefined,
    currency: options.currency?.trim().toUpperCase() || undefined,
    page: options.page,
    page_size: options.pageSize,
  };
}

async function requestLedgerJson<TData>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
): Promise<LedgerApiResponse<TData>> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = payload?.error;
    const code = typeof error?.code === "string" ? error.code : "LEDGER_REQUEST_FAILED";
    const message =
      typeof error?.message === "string"
        ? error.message
        : `Request failed: ${path} (${response.status})`;
    throw new Error(`${code}: ${message}`);
  }
  return payload as LedgerApiResponse<TData>;
}

async function requestLedgerImportJson(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<LedgerImportResponse> {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = payload?.error;
    const code = typeof error?.code === "string" ? error.code : "LEDGER_REQUEST_FAILED";
    const message =
      typeof error?.message === "string"
        ? error.message
        : `Request failed: ${path} (${response.status})`;
    throw new LedgerRequestError(message, code, response.status, error?.retryable === true);
  }
  return payload as LedgerImportResponse;
}

export function createRealLedgerClient({
  fetchImpl,
  baseUrl,
}: LedgerClientFactoryOptions): LedgerClientMethods {
  return {
    getLedgerDates: () =>
      requestLedgerJson<LedgerDatesData>(fetchImpl, baseUrl, "/api/ledger/dates"),
    getLedgerDashboard: (asOfDate: string) =>
      requestLedgerJson<LedgerDashboardData>(
        fetchImpl,
        baseUrl,
        `/api/ledger/dashboard${buildQuery({ as_of_date: asOfDate })}`,
      ),
    getLedgerPositions: (options: LedgerPositionsOptions) =>
      requestLedgerJson<LedgerPositionsData>(
        fetchImpl,
        baseUrl,
        `/api/ledger/positions${buildQuery(positionsParams(options))}`,
      ),
    exportLedgerPositions: async (options: LedgerPositionsOptions) => {
      const response = await fetchImpl(
        `${baseUrl}/api/ledger/export/positions${buildQuery({
          ...positionsParams(options),
          format: "xlsx",
        })}`,
        { headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" } },
      );
      if (!response.ok) {
        throw new Error(`LEDGER_EXPORT_POSITIONS_FAILED: ${response.status}`);
      }
      return response.blob();
    },
    importLedger: (file: File, signal?: AbortSignal) => {
      const formData = new FormData();
      formData.append("file", file);
      return requestLedgerImportJson(fetchImpl, baseUrl, "/api/ledger/import", {
        method: "POST",
        body: formData,
        signal,
      });
    },
    getLedgerImportStatus: (runId: string, signal?: AbortSignal) =>
      requestLedgerImportJson(
        fetchImpl,
        baseUrl,
        `/api/ledger/import-status${buildQuery({ run_id: runId })}`,
        { signal },
      ),
  };
}
