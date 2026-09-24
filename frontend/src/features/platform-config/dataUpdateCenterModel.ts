import type { DataUpdateRun, DataUpdatesOverview } from "../../api/dataUpdatesClient";
import { buildStateSurfaces, type LabeledValue, textOrDash } from "../../pageModel";

const STATUS_LABELS: Record<string, string> = {
  queued: "等待后台执行", waiting_inputs: "等待文件", running: "正在更新", retrying: "等待自动重试",
  completed: "更新已核验", failed: "更新未完成", cancelled: "已取消",
  missing: "未启用", disabled: "已停用", never_run: "等待首次运行", ready: "上次执行成功",
  warning: "执行结果需检查", available: "已有数据", error: "查询失败",
};

export function updateStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? "状态未确认";
}

export function requiresPublicationReview(run: DataUpdateRun): boolean {
  if (run.status !== "failed") return false;
  const receipt = run.failure_receipt;
  // Match the worker's completed-work replay guard; source_preview can also fail
  // before the financial body completes, so its explicit completion evidence is required.
  return receipt?.failed_step === "publish" || receipt?.failed_step === "system_read_publish"
    || (receipt?.failed_step === "source_preview" && receipt.business_body_status === "completed");
}

export function buildDataUpdateCenterModel(data: DataUpdatesOverview) {
  const queue = data.schedule.tasks.find((task) => task.task_name === "MOSS-DataUpdateQueue");
  const schedulerAvailable = Boolean(queue && !["missing", "disabled"].includes(queue.status))
    && data.schedule.status === "available";
  const seenDates = new Set<string>();
  const latestByDate = data.runs.filter((run) => {
    const key = `${run.workflow ?? "core_financial"}:${run.report_date}`;
    if (seenDates.has(key)) return false;
    seenDates.add(key);
    return true;
  });
  const failed = latestByDate.filter((run) => run.status === "failed" || run.status === "retrying");
  const scheduledWarnings = data.schedule.tasks.filter((task) => task.status === "warning");
  const dates: LabeledValue[] = data.financial_dates.map((row) => ({
    key: row.key, label: row.label, value: row.status === "error" ? "查询失败" : textOrDash(row.as_of_date),
    status: row.status === "error" ? "error" : row.as_of_date ? "landed" : "empty",
  }));
  const surfaces = buildStateSurfaces([
    { key: "scheduler", when: !schedulerAvailable, variant: "error", title: "财务自动更新尚不可用",
      description: "后台任务未启用或状态查询失败。恢复后才能提交自动更新请求。" },
    { key: "failures", when: failed.length > 0 || scheduledWarnings.length > 0, variant: "error",
      title: "有更新结果需要处理", description: "请查看执行记录与计划任务。失败记录保留已完成步骤，整条链路通过核验后才标记更新完成。" },
  ]);
  return { dates, surfaces, schedulerAvailable };
}
