import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer } from "antd";

import { useApiClient } from "../../../api/clientContext";
import { numericChartNumberOrNull } from "../../../api/numeric";
import { EM_DASH, localeOrDash } from "../../../pageModel";
import { riskTensorExactScaledAmountDisplayOrNull } from "../../risk-tensor/riskTensorPageModel";
import styles from "./marketPortfolioScenarioPanel.module.css";

/** Remount date-bound state when the curve observation changes. */
export function MarketPortfolioScenarioPanel({ curveObservationDate }: { curveObservationDate: string | null }) {
  return <ScenarioContent key={curveObservationDate ?? "missing-curve"} curveObservationDate={curveObservationDate} />;
}

function ScenarioContent({ curveObservationDate }: { curveObservationDate: string | null }) {
  const client = useApiClient();
  const [opened, setOpened] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [historicalDate, setHistoricalDate] = useState("");
  const dates = useQuery({
    queryKey: ["market-portfolio-scenario", "dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    enabled: opened && Boolean(curveObservationDate),
    retry: false,
  });
  const blockedDates = dates.data?.result.blocked_report_dates ?? [];
  const availableDates = (dates.data?.result.report_dates ?? [])
    .filter((date) => !blockedDates.some((blocked) => blocked.report_date === date));
  const sameDateAvailable = Boolean(curveObservationDate && availableDates.includes(curveObservationDate));
  const selectedDate = historicalDate && availableDates.includes(historicalDate)
    ? historicalDate : !historicalDate && sameDateAvailable ? curveObservationDate : null;
  const historicalOptions = availableDates.filter((date) => curveObservationDate && date < curveObservationDate).sort().reverse();
  const scenario = useQuery({
    queryKey: ["market-portfolio-scenario", client.mode, selectedDate],
    queryFn: () => client.getRiskScenarioStress(selectedDate!),
    enabled: opened && dates.isSuccess && Boolean(selectedDate),
    retry: false,
  });
  const payload = scenario.data?.result;
  const meta = scenario.data?.result_meta;
  const evidence = payload?.evidence;
  const row = payload?.scenarios.find((item) => item.scenario_key === "parallel_rate_up_10bp");
  const rawAmount = numericChartNumberOrNull(row?.estimated_impact);
  const verified = dates.isSuccess && !scenario.isError && payload?.basis === "scenario"
    && evidence?.amount_display_allowed === true
    && evidence.date_status === "verified" && evidence.fallback_status === "none"
    && evidence.actual_risk_date === selectedDate && evidence.requested_report_date === selectedDate
    && payload.report_date === selectedDate && evidence.coverage.status === "complete"
    && evidence.metric_id === "MTR-RSK-001R" && evidence.human_review_required === true
    && row?.source_field === "regulatory_dv01" && row.data_status === "available"
    && row.human_review_required === true && row.estimated_impact.unit === "yuan"
    && row.shock.unit === "bp" && numericChartNumberOrNull(row.shock) === 10
    && rawAmount !== null && meta?.fallback_mode === "none" && meta.result_kind === "risk.tensor.scenario_stress"
    && meta.basis === "scenario" && meta.formal_use_allowed === false;
  const amount = verified
    ? riskTensorExactScaledAmountDisplayOrNull(row?.estimated_impact, 1, rawAmount !== 0)
      ?? localeOrDash(rawAmount, "zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: "exceptZero" })
    : null;
  const error = dates.error ?? scenario.error;
  const errorText = error instanceof Error ? error.message : String(error ?? "");
  const forbidden = /\b403\b/.test(errorText);
  const noSameDate = dates.isSuccess && !sameDateAvailable;
  const scenarioUnavailable = Boolean(selectedDate) && !scenario.isFetching
    && (scenario.isError || (scenario.isSuccess && !verified));
  const canSelectHistory = dates.isSuccess && !forbidden
    && (noSameDate || scenarioUnavailable || Boolean(historicalDate));
  const dateConflict = Boolean(payload && evidence?.actual_risk_date !== selectedDate);
  const warnings = [...new Set([...(payload?.warnings ?? []), ...(payload?.source_warnings ?? []), ...(evidence?.coverage.reasons ?? [])])];
  const drillDate = evidence?.actual_risk_date ?? selectedDate ?? curveObservationDate;

  return (
    <section className={styles.panel} aria-label="组合利率情景">
      <div className={styles.heading}>
        <div className={styles.headingText}>
          <h3>组合利率情景</h3>
          <span className={styles.description}>{opened ? "独立情景 / 需人工复核" : "尚未加载持仓"}</span>
        </div>
        <button type="button" className={styles.action} aria-expanded={detailsOpen} onClick={() => { setOpened(true); setDetailsOpen(true); }}>
          {opened ? "查看计算依据" : "加载组合情景"}
        </button>
      </div>
      <div className={styles.overview}>
        <p>风险日 {opened ? evidence?.actual_risk_date ?? EM_DASH : EM_DASH} / {historicalDate ? "历史持仓" : opened ? "已请求核验" : "尚未读取"}</p>
        <div className={styles.estimate}>
          <strong>平行上行 10 bp</strong>
          <div className={styles.amount}><strong data-direction={verified && rawAmount !== null ? rawAmount < 0 ? "down" : rawAmount > 0 ? "up" : "flat" : undefined}>{!error && verified ? amount : EM_DASH}</strong><span>元</span></div>
          <p>这是独立利率情景，不是当日实际损益。</p>
        </div>
        {opened && evidence && !error ? <p>纳入 {localeOrDash(evidence.coverage.included_position_count, "zh-CN")} 项 / 总计 {localeOrDash(evidence.coverage.total_position_count, "zh-CN")} 项；按口径排除 {localeOrDash(evidence.coverage.excluded_position_count, "zh-CN")} 项；风险输入缺失 {localeOrDash(evidence.coverage.missing_risk_position_count, "zh-CN")} 项</p> : <p>加载后核验风险日、持仓覆盖与读取权限。</p>}
        <p className={styles.warning}>{!opened ? "点击加载组合情景后读取风险数据。" : forbidden ? "组合风险数据权限受限，暂不显示金额。" : verified && !error ? "监管口径 DV01；估算需人工复核。" : "风险日、覆盖或来源尚未通过核验，暂不显示金额。"}</p>
      </div>
      <Drawer open={detailsOpen} destroyOnHidden onClose={() => setDetailsOpen(false)} title="组合利率情景依据" width="min(640px, 100vw)" rootClassName={`theme-dh-api ${styles.drawer}`} data-moss-theme-scope="market-overview">
        <div className={styles.content}>
          <span className={styles.badge}>情景估算 · 需复核</span>
          <p>基于已物化监管口径 DV01 的线性冲击估算，不代表实际损益、未来利润或完整债券重估。</p>
          <div className={styles.dates}>
            <span>曲线观察日 <strong>{curveObservationDate ?? EM_DASH}</strong></span>
            <span>实际风险数据日 <strong>{evidence?.actual_risk_date ?? EM_DASH}</strong></span>
          </div>
          {!curveObservationDate && <p role="status">缺少曲线观察日，暂不读取组合情景。请到风险详情核验。</p>}
          {(dates.isLoading || scenario.isLoading) && <p role="status">正在核验风险日期与情景来源…</p>}
          {error && (
            <div role="status">
              <p>{forbidden ? "组合风险数据权限受限，市场分析仍可查看。" : "组合情景读取失败，暂不显示金额。"}</p>
              {!forbidden && <button className={styles.action} type="button" onClick={() => void (dates.isError ? dates.refetch() : scenario.refetch())}>重试组合情景</button>}
            </div>
          )}
          {!forbidden && noSameDate && <p role="status">缺少同日风险数据。选择可用的历史风险日期后，可核验基于历史持仓的情景。</p>}
          {canSelectHistory && !noSameDate && !historicalDate && historicalOptions.length > 0 && (
            <p>当前日期的情景不可用，可选择历史风险日期，核验基于历史持仓的情景。</p>
          )}
          {canSelectHistory && historicalOptions.length === 0 && <p>暂无可选择的历史风险日期。</p>}
          {!forbidden && noSameDate && blockedDates.find((date) => date.report_date === curveObservationDate)?.reason && (
            <p>{blockedDates.find((date) => date.report_date === curveObservationDate)?.reason}</p>
          )}
          {canSelectHistory && historicalOptions.length > 0 && (
            <label className={styles.selector}>历史风险日期
              <select value={historicalDate} onChange={(event) => setHistoricalDate(event.target.value)}>
                <option value="">请选择历史日期</option>
                {historicalOptions.map((date) => <option key={date} value={date}>{date}</option>)}
              </select>
            </label>
          )}
          {payload && !error && (
            <>
              <h4>{historicalDate ? "基于历史持仓的情景" : "同日持仓情景核验"}</h4>
              {verified ? <div className={styles.amount}><span>估算影响</span><strong>{amount}</strong><span>元</span></div>
                : <p role="status">{dateConflict ? "风险实际日期与所选日期不一致，暂不显示金额。" : "来源日期、监管风险覆盖或情景口径未通过核验，暂不显示金额。"}</p>}
              <p>风险口径：监管口径 DV01（MTR-RSK-001R）。范围：{evidence?.scope_label || "尚未核验"}。</p>
              {evidence && (
                <p>持仓共 {localeOrDash(evidence.coverage.total_position_count, "zh-CN")} 项，纳入 {localeOrDash(evidence.coverage.included_position_count, "zh-CN")} 项，按口径排除 {localeOrDash(evidence.coverage.excluded_position_count, "zh-CN")} 项，风险输入缺失 {localeOrDash(evidence.coverage.missing_risk_position_count, "zh-CN")} 项。</p>
              )}
              {warnings.length > 0 && <p className={styles.warning}>来源含 {warnings.length} 条使用限制，请查看情景依据并复核。</p>}
              <details>
                <summary>查看情景依据</summary>
                <p>固定平行上行10 bp；数据口径 scenario；使用监管 DV01。需要人工复核，不提供账户拆分或利率下行情景。</p>
                {warnings.map((warning) => <p key={warning}>{warning}</p>)}
                <p>规则版本：{payload.rule_version || EM_DASH}；来源版本：{payload.source.source_version || EM_DASH}。</p>
              </details>
            </>
          )}
          <a className={styles.link} href={drillDate ? `/risk-tensor?report_date=${encodeURIComponent(drillDate)}` : "/risk-tensor"}>查看风险详情</a>
        </div>
      </Drawer>
    </section>
  );
}
