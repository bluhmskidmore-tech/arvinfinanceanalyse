export type LedgerDirection = "ASSET" | "LIABILITY";

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
};

export type LedgerDashboardData = {
  as_of_date: string | null;
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

const mockMetadata: LedgerResponseMetadata = {
  source_version: "sv_ledger_mock_20260317",
  rule_version: "position_key_contract_v1",
  batch_id: 1,
  stale: false,
  fallback: false,
  no_data: false,
};

const mockTrace: LedgerResponseTrace = {
  request_id: "req_ledger_mock",
  requested_as_of_date: "2026-03-17",
  resolved_as_of_date: "2026-03-17",
  batch_id: 1,
  filters: null,
};

const mockPositions: LedgerPositionItem[] = [
  {
    position_key: "ledger:asset:20260317:0001",
    batch_id: 1,
    row_no: 1,
    as_of_date: "2026-03-17",
    bond_code: "ASSET-001",
    bond_name: "资产样例债券",
    portfolio: "银行账簿",
    direction: "ASSET",
    business_type: "投资",
    business_type_1: "债券",
    account_category_std: "银行账户",
    cost_center: "总行",
    asset_class_std: "持有至到期类资产",
    channel: "ZQTZSHOW",
    currency: "CNY",
    face_amount: 100_000_000,
    fair_value: 99_500_000,
    amortized_cost: 100_100_000,
    accrued_interest: 120_000,
    interest_receivable_payable: 50_000,
    quantity: 1_000_000,
    latest_face_value: 100,
    interest_method: "fixed",
    coupon_rate: 0.03,
    yield_to_maturity: 0.031,
    interest_start_date: "2025-03-17",
    maturity_date: "2028-03-17",
    counterparty_name_cn: "样例发行人A",
    legal_customer_name: "样例发行人A",
    group_customer_name: "样例集团A",
    trace: {
      position_key: "ledger:asset:20260317:0001",
      batch_id: 1,
      row_no: 1,
    },
  },
  {
    position_key: "ledger:liability:20260317:0002",
    batch_id: 1,
    row_no: 2,
    as_of_date: "2026-03-17",
    bond_code: "LIAB-001",
    bond_name: "发行负债样例债券",
    portfolio: "银行账簿",
    direction: "LIABILITY",
    business_type: "发行",
    business_type_1: "债券",
    account_category_std: "发行类债券",
    cost_center: "总行",
    asset_class_std: "发行类债券",
    channel: "ZQTZSHOW",
    currency: "CNY",
    face_amount: 50_000_000,
    fair_value: 49_800_000,
    amortized_cost: 50_020_000,
    accrued_interest: 60_000,
    interest_receivable_payable: 20_000,
    quantity: 500_000,
    latest_face_value: 100,
    interest_method: "fixed",
    coupon_rate: 0.025,
    yield_to_maturity: 0.026,
    interest_start_date: "2025-03-17",
    maturity_date: "2029-03-17",
    counterparty_name_cn: "本行发行",
    legal_customer_name: "本行发行",
    group_customer_name: "本行发行",
    trace: {
      position_key: "ledger:liability:20260317:0002",
      batch_id: 1,
      row_no: 2,
    },
  },
];

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

function positionsParams(options: LedgerPositionsOptions) {
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

export function createMockLedgerClient(): LedgerClientMethods {
  return {
    async getLedgerDates() {
      return {
        data: { items: ["2026-03-17"] },
        metadata: mockMetadata,
        trace: { ...mockTrace, requested_as_of_date: null, resolved_as_of_date: null },
      };
    },
    async getLedgerDashboard(asOfDate: string) {
      const fallback = asOfDate !== "2026-03-17";
      return {
        data: {
          as_of_date: "2026-03-17",
          currency_breakdown: [
            { currency: "CNY", asset_face_amount: 3289.07, liability_face_amount: 1231.77, net_face_exposure: 2057.31 },
            { currency: "USD", asset_face_amount: 2, liability_face_amount: null, net_face_exposure: 2 },
          ],
        },
        metadata: {
          ...mockMetadata,
          stale: fallback,
          fallback,
        },
        trace: {
          ...mockTrace,
          request_id: "req_ledger_dashboard_mock",
          requested_as_of_date: asOfDate,
          resolved_as_of_date: "2026-03-17",
        },
      };
    },
    async getLedgerPositions(options: LedgerPositionsOptions) {
      const items = mockPositions.filter(
        (item) =>
          (!options.direction || item.direction === options.direction) &&
          (!options.currency || item.currency === options.currency.trim().toUpperCase()),
      );
      return {
        data: {
          items,
          page: options.page ?? 1,
          page_size: options.pageSize ?? 50,
          total: items.length,
        },
        metadata: {
          ...mockMetadata,
          no_data: items.length === 0,
          stale: options.asOfDate !== "2026-03-17",
          fallback: options.asOfDate !== "2026-03-17",
        },
        trace: {
          ...mockTrace,
          request_id: "req_ledger_positions_mock",
          requested_as_of_date: options.asOfDate,
          resolved_as_of_date: "2026-03-17",
          filters: positionsParams(options),
        },
      };
    },
    async exportLedgerPositions() {
      return new Blob(["mock ledger positions"], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
    },
    async importLedger(file: File) {
      const runId = `ledger_import:mock:${Date.now()}`;
      return {
        data: { run_id: runId, status: "queued", file_name: file.name },
        trace: { request_id: "req_ledger_import_mock", run_id: runId },
      };
    },
    async getLedgerImportStatus(runId: string) {
      return {
        data: {
          run_id: runId,
          status: "succeeded",
          file_name: "ledger_mock.xlsx",
          batch_id: 1,
          finished_at: new Date().toISOString(),
        },
        trace: { request_id: "req_ledger_import_status_mock", run_id: runId },
      };
    },
  };
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
