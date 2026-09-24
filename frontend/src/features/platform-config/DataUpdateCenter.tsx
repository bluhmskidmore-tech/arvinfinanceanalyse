import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createDataUpdatesClient, type DataUpdateRun, type DataUpdatesClient, type UpdateWorkflow } from "../../api/dataUpdatesClient";
import { PageStateSurface } from "../../components/page/PagePrimitives";
import { EM_DASH } from "../../pageModel";
import { buildDataUpdateCenterModel, requiresPublicationReview, updateStatusLabel } from "./dataUpdateCenterModel";
import styles from "./DataUpdateCenter.module.css";

const defaultApi = createDataUpdatesClient();
const queryKey = ["data-update-center"];

function Status({ value }: { value: string }) {
  return <span className={styles.status} data-status={value}>{updateStatusLabel(value)}</span>;
}

function formatStepElapsedSeconds(step: DataUpdateRun["steps"][number]): string | null {
  const elapsed = step.elapsed_seconds;
  if (!["completed", "failed"].includes(step.status)
    || typeof elapsed !== "number" || !Number.isFinite(elapsed) || elapsed < 0) return null;
  return `耗时 ${elapsed.toFixed(3)} 秒`;
}

export default function DataUpdateCenter({ mode, api = defaultApi }: { mode: "real" | "mock"; api?: DataUpdatesClient }) {
  const queryClient = useQueryClient();
  const [reportDate, setReportDate] = useState("");
  const [workflow, setWorkflow] = useState<UpdateWorkflow>("core_financial");
  const [notice, setNotice] = useState("");
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const overview = useQuery({ queryKey, queryFn: api.overview, enabled: mode === "real", retry: false,
    refetchInterval: 30_000 });
  const data = overview.data;
  const model = useMemo(() => data ? buildDataUpdateCenterModel(data) : null, [data]);
  const preflight = useQuery({ queryKey: [...queryKey, "preflight", reportDate, workflow],
    queryFn: () => api.preflight(reportDate, workflow), enabled: mode === "real" && /^\d{4}-\d{2}-\d{2}$/.test(reportDate),
    retry: false, refetchInterval: 30_000 });
  const refresh = () => void queryClient.invalidateQueries({ queryKey });
  const submit = useMutation({
    mutationFn: (wait: boolean) => api.requestCore(reportDate, wait, requestKey, workflow),
    onSuccess: (run) => { setNotice(run.message); setRequestKey(crypto.randomUUID()); refresh(); },
  });
  const cancel = useMutation({ mutationFn: api.cancel, onSuccess: () => { setNotice("已取消等待。"); refresh(); } });
  const market = useMutation({ mutationFn: api.requestMarket, onSuccess: (result) => { setNotice(result.message); refresh(); } });
  const changeDate = (value: string) => { setReportDate(value); setRequestKey(crypto.randomUUID()); submit.reset(); setNotice(""); };
  const retry = (run: DataUpdateRun) => { changeDate(run.report_date); setWorkflow(run.workflow ?? "core_financial"); setNotice("已选择该报告日，请检查文件后重新提交。"); };
  const error = submit.error ?? cancel.error ?? market.error;
  const canManage = workflow === "balance_daily" ? data?.permissions.balance : data?.permissions.core;
  const preflightMatchesSelection = preflight.data?.report_date === reportDate && preflight.data?.workflow === workflow;
  const canSubmit = Boolean(!overview.isError && model?.schedulerAvailable && canManage && reportDate
    && preflightMatchesSelection && !preflight.isError && !preflight.isFetching && !submit.isPending);

  if (mode !== "real") return <PageStateSurface variant="empty" title="数据更新仅在真实数据模式下开放"
    description="演示模式不会启动后台任务。" />;

  return (
    <section className={styles.center} aria-labelledby="data-update-center-title" data-testid="data-update-center">
      <header className={styles.heading}>
        <div><h2 id="data-update-center-title">数据更新中心</h2><p>查看数据日期、安排更新，处理未完成的任务。</p></div>
        <button type="button" onClick={refresh} disabled={overview.isFetching}>刷新状态</button>
      </header>
      {overview.isError && <PageStateSurface variant="error" title="更新状态读取失败"
        description="无法确认后台当前状态，请刷新重试。" />}
      {overview.isLoading && <PageStateSurface variant="loading" title="正在读取更新状态" />}
      {notice && <p className={styles.notice} role="status">{notice}</p>}
      {error && <p className={styles.error} role="alert">{error instanceof Error ? error.message : "操作失败，请稍后重试。"}</p>}
      {data && model && <>
        {model.surfaces.map(({ key, ...surface }) => <div key={key} role="alert"><PageStateSurface {...surface} /></div>)}
        <dl className={styles.dates} aria-label="各模块实际数据日期">
          {model.dates.map((row) => <div key={row.key}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
        </dl>
        <div className={styles.workspace}>
          <section className={styles.request} aria-label="安排财务更新">
            <h3>安排财务更新</h3>
            <p>按所选报告日和更新范围执行，完成后核验结果日期。</p>
            <label className={styles.dateLabel}>更新范围
              <select value={workflow} onChange={(event) => { setWorkflow(event.target.value as UpdateWorkflow); setRequestKey(crypto.randomUUID()); submit.reset(); }}>
                <option value="balance_daily">每日余额、持仓与风险</option>
                <option value="core_financial">完整财务更新（包含损益）</option>
              </select>
            </label>
            <label className={styles.dateLabel}>报告日期
              <input type="date" value={reportDate} onChange={(event) => changeDate(event.target.value)} />
            </label>
            <p className={styles.directory}>文件投放目录 <code>{data.input_directory}</code></p>
            {!reportDate && <p className={styles.muted}>请选择报告日期，查看所需文件是否到齐。</p>}
            {preflight.isFetching && reportDate && <p role="status">正在检查该报告日的文件…</p>}
            {preflight.isError && <p className={styles.error} role="alert">文件检查失败，请重新选择日期或刷新状态。</p>}
            {preflight.data && !preflightMatchesSelection && <p className={styles.error} role="alert">文件检查结果与所选报告日期或更新范围不一致，请刷新重试。</p>}
            {preflight.data && preflightMatchesSelection && <ul className={styles.checks}>
              {preflight.data.checks.map((check) => <li key={check.key}>
                <span>{check.label}</span><strong data-ready={check.status === "ready"}>{check.status === "ready" ? "可进入校验" : "等待文件"}</strong>
                <small>{check.files.length ? check.files.join("、") : check.detail}</small>
              </li>)}
            </ul>}
            <div className={styles.actions}>
              <button type="button" className={styles.primary} disabled={!canSubmit || !preflight.data?.ready}
                onClick={() => submit.mutate(false)}>立即更新</button>
              <button type="button" disabled={!canSubmit} onClick={() => submit.mutate(true)}>资料齐全后自动更新</button>
            </div>
            {!canManage && <p className={styles.muted}>当前账号没有所选范围的更新权限。</p>}
            <p className={styles.muted}>后台每五分钟检查一次，关闭页面后继续执行。文件到齐后仍须通过内容和日期校验。</p>
          </section>
          <section className={styles.schedule} aria-label="自动更新计划">
            <div className={styles.sectionHeading}><h3>自动更新计划</h3>
              <button type="button" onClick={() => market.mutate()} disabled={overview.isError || !data.permissions.market || market.isPending
                || !data.schedule.tasks.some((task) => task.task_name === "MOSS-DailyDataRefresh"
                  && !["missing", "disabled", "running"].includes(task.status))}>更新市场数据</button>
            </div>
            <p>{data.schedule.detail}</p>
            <ul className={styles.schedules}>
              {data.schedule.tasks.map((task) => <li key={task.task_name}>
                <div><strong>{task.label}</strong><Status value={task.status} /></div>
                <dl><div><dt>上次运行</dt><dd>{task.last_run_time || EM_DASH}</dd></div>
                  <div><dt>下次运行</dt><dd>{task.next_run_time || EM_DASH}</dd></div></dl>
              </li>)}
            </ul>
          </section>
        </div>
        <section className={styles.history} aria-label="财务更新记录">
          <h3>财务更新记录</h3>
          {data.runs.length === 0 ? <p className={styles.muted}>尚未提交财务更新请求。已有计划任务的运行状态显示在上方。</p> :
            <ul className={styles.runs}>{data.runs.map((run) => {
              const publicationNeedsReview = requiresPublicationReview(run);
              return <li key={run.run_id}>
              <div className={styles.sectionHeading}><strong>报告日 {run.report_date}</strong><Status value={run.status} />
                {(run.workflow === "balance_daily" ? data.permissions.balance : data.permissions.core) && ["queued", "waiting_inputs", "retrying"].includes(run.status) &&
                  <button type="button" disabled={cancel.isPending} onClick={() => cancel.mutate(run.run_id)}>取消等待</button>}
                {(run.workflow === "balance_daily" ? data.permissions.balance : data.permissions.core) && run.status === "failed" && !publicationNeedsReview &&
                  <button type="button" onClick={() => retry(run)}>重新提交此日期</button>}
              </div>
              <small>{run.workflow === "balance_daily" ? "每日余额、持仓与风险" : "完整财务更新（包含损益）"}</small>
              {publicationNeedsReview && <div role="alert">
                <p className={styles.error}>财务计算已完成，发布待处理</p>
                <p>请查看失败回执与已完成步骤，由运维核对失败原因及已完成结果。重新提交会重跑所选财务流程，本页暂不提供仅恢复发布的操作。</p>
              </div>}
              <p>{run.message}</p>
              {run.workflow === "balance_daily" && run.status === "completed" &&
                <p className={styles.resultLink}><a href={`/balance-analysis?report_date=${encodeURIComponent(run.report_date)}`}>查看余额结果</a></p>}
              <small>最近变化 {run.updated_at.replace("T", " ").slice(0, 19)} UTC</small>
              {run.current_step && <p role="status">正在执行：{data.steps.find((step) => step.key === run.current_step)?.label ?? "财务更新"}</p>}
              {(run.steps.length > 0 || publicationNeedsReview) && <details>
                <summary>{publicationNeedsReview ? "查看失败回执与已完成步骤" : "查看步骤与结果"}</summary>
                {publicationNeedsReview && <>
                  <p>请求编号：<code>{run.run_id}</code></p>
                  <p>失败阶段：{run.failure_receipt?.failed_step === "source_preview" ? "发布前来源摘要检查" : "只读结果发布"}</p>
                </>}
                <ol className={styles.steps}>
                {run.steps.map((step) => {
                  const elapsed = formatStepElapsedSeconds(step);
                  return <li key={step.key}><span>{step.label}</span><Status value={step.status} />
                    {elapsed && <small>{elapsed}</small>}
                    {step.error_message && <p className={styles.error}>{step.error_message}</p>}</li>;
                })}
              </ol></details>}
            </li>;
            })}</ul>}
        </section>
      </>}
    </section>
  );
}
