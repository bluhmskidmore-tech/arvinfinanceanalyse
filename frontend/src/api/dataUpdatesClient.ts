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

export type DataUpdateRun = {
  workflow?: UpdateWorkflow;
  run_id: string;
  report_date: string;
  status: "queued" | "waiting_inputs" | "running" | "retrying" | "completed" | "failed" | "cancelled";
  submitted_at: string;
  updated_at: string;
  message: string;
  attempt: number;
  current_step?: string | null;
  failure_receipt?: { failed_step?: string; business_body_status?: string } | null;
  steps: { key: string; label: string; status: string; error_message?: string | null; elapsed_seconds?: number | null }[];
  preflight?: UpdatePreflight;
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
  run.steps.forEach((step, index) => assertShape(step, `${path}.steps[${index}]`, [
    { path: "key", type: "string" }, { path: "label", type: "string" },
    { path: "status", type: "string" },
  ]));
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
    requestMarket: () => requestActionJson<{ status: string; message: string }>(fetchImpl, baseUrl,
      `${path}/market`, { method: "POST" }),
  };
}

export type DataUpdatesClient = ReturnType<typeof createDataUpdatesClient>;
