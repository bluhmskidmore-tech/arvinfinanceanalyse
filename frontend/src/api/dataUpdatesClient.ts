import { assertShape, requestActionJson, requestPlainJson } from "./transport";

export type UpdateInputCheck = {
  key: string;
  label: string;
  status: "ready" | "waiting";
  files: string[];
  detail: string;
};

export type UpdatePreflight = {
  workflow?: UpdateWorkflow;
  report_date: string;
  ready: boolean;
  input_directory: string;
  checks: UpdateInputCheck[];
};

export type ProductCategoryRefreshScope = {
  scanned_report_dates: string[];
  scanned_years: string[];
  scanned_date_count: number;
  rebuilt_report_dates: string[];
  rebuilt_years: string[];
  rebuilt_date_count: number;
  reused_report_dates: string[];
  reused_years: string[];
  reused_date_count: number;
  removed_report_dates: string[];
  removed_years: string[];
  removed_date_count: number;
};

export type DataUpdateRun = {
  workflow?: UpdateWorkflow | "choice_stock_pit_history";
  run_id: string;
  report_date: string;
  status: "queued" | "waiting_inputs" | "running" | "retrying" | "completed" | "failed" | "cancelled";
  submitted_at: string;
  updated_at: string;
  message: string;
  attempt: number;
  current_step?: string | null;
  recovery_mode?: "publication_only" | null;
  recovery_of_run_id?: string | null;
  publication_recovery?: { available: boolean; reason: string | null; failed_step: string | null };
  failure_receipt?: { failed_step?: string; business_body_status?: string } | null;
  steps: { key: string; label: string; status: string; error_message?: string | null;
    elapsed_seconds?: number | null; refresh_scope?: ProductCategoryRefreshScope | null }[];
  preflight?: UpdatePreflight | {
    workflow: "choice_stock_pit_history";
    report_date: string;
    ready: boolean;
    source_sha256: string;
    plan_sha256: string;
    insert_counts: Record<string, number>;
  };
};

export type DataUpdateSchedule = {
  task_name: string;
  label: string;
  status: string;
  last_run_time: string | null;
  next_run_time: string | null;
  last_result: string | null;
};

export type DataUpdatesOverview = {
  checked_at: string;
  input_directory: string;
  permissions: { core: boolean; balance?: boolean; market: boolean };
  schedule: { status: string; detail: string; tasks: DataUpdateSchedule[] };
  financial_dates: { key: string; label: string; as_of_date: string | null; status: string }[];
  runs: DataUpdateRun[];
  steps: { key: string; label: string }[];
};

export type UpdateWorkflow = "balance_daily" | "core_financial";

function assertUpdateRun(run: DataUpdateRun, path: string): void {
  assertShape(run, path, [
    { path: "run_id", type: "string" }, { path: "report_date", type: "string" },
    { path: "workflow", type: "string", optional: true }, { path: "status", type: "string" },
    { path: "updated_at", type: "string" }, { path: "message", type: "string" },
    { path: "steps", type: "array" },
  ]);
  run.steps.forEach((step, index) => {
    const stepPath = `${path}.steps[${index}]`;
    assertShape(step, stepPath, [
      { path: "key", type: "string" }, { path: "label", type: "string" },
      { path: "status", type: "string" }, { path: "refresh_scope", type: "object", optional: true },
    ]);
    const scope = step.refresh_scope;
    if (!scope) return;
    if (step.key !== "product_category_pnl" || step.status !== "completed") {
      throw new Error(`产品损益处理范围与步骤状态不一致：${stepPath}`);
    }
    for (const name of ["scanned", "rebuilt", "reused", "removed"] as const) {
      assertShape(scope, `${stepPath}.refresh_scope`, [
        { path: `${name}_report_dates`, type: "array" }, { path: `${name}_years`, type: "array" },
        { path: `${name}_date_count`, type: "number" },
      ]);
      const dates = scope[`${name}_report_dates`];
      const years = scope[`${name}_years`];
      const count = scope[`${name}_date_count`];
      if (dates.some((value) => typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value))
        || years.some((value) => typeof value !== "string" || !/^\d{4}$/.test(value))
        || !Number.isInteger(count) || count < 0 || count !== dates.length || new Set(dates).size !== dates.length) {
        throw new Error(`产品损益处理范围格式无效：${stepPath}.refresh_scope.${name}`);
      }
    }
  });
}

export function createDataUpdatesClient(options?: { baseUrl?: string; fetchImpl?: typeof fetch }) {
  const rawUrl = options?.baseUrl ?? import.meta.env.VITE_API_BASE_URL ?? "";
  const baseUrl = String(rawUrl).replace(/\/$/, "");
  const fetchImpl = options?.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const path = "/api/data-updates";
  return {
    overview: async () => {
      const result = await requestPlainJson<DataUpdatesOverview>(fetchImpl, baseUrl, path, { errorDetail: "json-detail" });
      assertShape(result, path, [
        { path: "runs", type: "array" }, { path: "financial_dates", type: "array" },
        { path: "schedule.tasks", type: "array" }, { path: "steps", type: "array" },
        { path: "permissions.core", type: "boolean" }, { path: "permissions.market", type: "boolean" },
        { path: "permissions.balance", type: "boolean", optional: true },
        { path: "schedule.status", type: "string" }, { path: "schedule.detail", type: "string" },
        { path: "input_directory", type: "string" },
      ]);
      result.runs.forEach((run, index) => assertUpdateRun(run, `${path}.runs[${index}]`));
      result.financial_dates.forEach((row, index) => assertShape(row, `${path}.financial_dates[${index}]`, [
        { path: "key", type: "string" }, { path: "label", type: "string" },
        { path: "status", type: "string" }, { path: "as_of_date", type: "string", optional: true },
      ]));
      result.schedule.tasks.forEach((task, index) => assertShape(task, `${path}.schedule.tasks[${index}]`, [
        { path: "task_name", type: "string" }, { path: "label", type: "string" },
        { path: "status", type: "string" },
        { path: "last_run_time", type: "string", optional: true },
        { path: "next_run_time", type: "string", optional: true },
      ]));
      result.steps.forEach((step, index) => assertShape(step, `${path}.steps[${index}]`, [
        { path: "key", type: "string" }, { path: "label", type: "string" },
      ]));
      return result;
    },
    preflight: async (reportDate: string, workflow: UpdateWorkflow = "core_financial") => {
      const url = `${path}/preflight?report_date=${encodeURIComponent(reportDate)}&workflow=${workflow}`;
      const result = await requestPlainJson<UpdatePreflight>(fetchImpl, baseUrl, url, { errorDetail: "json-detail" });
      assertShape(result, url, [
        { path: "checks", type: "array" }, { path: "ready", type: "boolean" }, { path: "report_date", type: "string" },
        { path: "workflow", type: "string" }, { path: "input_directory", type: "string" },
      ]);
      if (result.report_date !== reportDate || result.workflow !== workflow) {
        throw new Error(`文件检查结果与所选报告日期或更新范围不一致：${url}`);
      }
      result.checks.forEach((check, index) => assertShape(check, `${url}.checks[${index}]`, [
        { path: "key", type: "string" }, { path: "label", type: "string" },
        { path: "status", type: "string" }, { path: "files", type: "array" },
        { path: "detail", type: "string" },
      ]));
      return result;
    },
    requestCore: async (reportDate: string, waitForInputs: boolean, requestKey: string, workflow: UpdateWorkflow = "core_financial") => {
      const url = `${path}/core`;
      const run = await requestActionJson<DataUpdateRun>(fetchImpl, baseUrl, url, {
        method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": requestKey },
        body: JSON.stringify({ report_date: reportDate, wait_for_inputs: waitForInputs, workflow }),
      });
      assertUpdateRun(run, url);
      if (run.report_date !== reportDate || (run.workflow ?? "core_financial") !== workflow) {
        throw new Error(`更新回执与所选报告日期或更新范围不一致：${url}`);
      }
      return run;
    },
    cancel: async (runId: string) => {
      const url = `${path}/runs/${encodeURIComponent(runId)}/cancel`;
      const run = await requestActionJson<DataUpdateRun>(fetchImpl, baseUrl, url, { method: "POST" });
      assertUpdateRun(run, url);
      if (run.run_id !== runId) throw new Error(`取消回执与所选请求不一致：${url}`);
      return run;
    },
    recoverPublication: async (runId: string, requestKey: string) => {
      const url = `${path}/runs/${encodeURIComponent(runId)}/recover-publication`;
      const run = await requestActionJson<DataUpdateRun>(fetchImpl, baseUrl, url, {
        method: "POST", headers: { "Idempotency-Key": requestKey },
      });
      assertUpdateRun(run, url);
      if (!run.run_id.trim() || run.run_id === runId || run.recovery_mode !== "publication_only"
        || run.recovery_of_run_id !== runId) {
        throw new Error(`发布恢复回执与所选请求不一致：${url}`);
      }
      return run;
    },
    requestMarket: () => requestActionJson<{ status: string; message: string }>(fetchImpl, baseUrl,
      `${path}/market`, { method: "POST" }),
  };
}

export type DataUpdatesClient = ReturnType<typeof createDataUpdatesClient>;
