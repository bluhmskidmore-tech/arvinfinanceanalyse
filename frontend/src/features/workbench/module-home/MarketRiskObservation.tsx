import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer } from "antd";
import { Link } from "react-router-dom";
import { useApiClient } from "../../../api/clientContext";
import type { MarketOverviewSnapshotPayload } from "../../../api/contracts";
import { ChartCard, type ChartCardRendererProps } from "../../../components/charts/ChartCard";
import { BaseChart } from "../../../components/charts/BaseChart";
import type { EChartsOption } from "../../../lib/echarts";
import { EM_DASH, localeOrDash } from "../../../pageModel";
import { designTokens } from "../../../theme/designSystem";
import type { MarketChartPalette } from "./marketChartPalette";
import { COMMODITY_LABELS, CRISIS_COMPONENT_LABELS, CRISIS_INPUT_LABELS, crisisCurrentPublishable, crisisPublicationReason, crisisHistoryOption, isMarketTechnicalReason, marketBusinessReason, riskNumber, riskRecord, riskRows, riskText } from "./marketRiskObservationModel";
import styles from "./marketRiskObservation.module.css";
import { buildMarketSourceLink } from "./marketSourceContext";

type Detail = "crisis" | "commodity" | "signals" | "news";
const TITLES: Record<Detail, string> = { crisis: "Crisis Score 评分依据", commodity: "商品扩展与模型研究", signals: "市场信号依据", news: "新闻比较与人工复核" };
const NUMBER_OPTIONS: Intl.NumberFormatOptions = { maximumFractionDigits: 4 };
const SCORE_OPTIONS: Intl.NumberFormatOptions = { minimumFractionDigits: 2, maximumFractionDigits: 2 };
const PERCENT_OPTIONS: Intl.NumberFormatOptions = { style: "percent", maximumFractionDigits: 1 };

function DataValue({ value, percent = false, unit = "" }: { value: unknown; percent?: boolean; unit?: string }) {
  return <span className={styles.numeric}>{localeOrDash(riskNumber(value), "zh-CN", percent ? PERCENT_OPTIONS : NUMBER_OPTIONS)}{riskNumber(value) !== null ? unit : ""}</span>;
}

function RiskHistoryChart({ option }: ChartCardRendererProps) {
  const legend = riskRecord(option.legend);
  const tooltip = riskRecord(option.tooltip);
  return <BaseChart height={168} option={{
    ...option, textStyle: { ...option.textStyle, fontFamily: designTokens.fontFamily.sans },
    legend: { ...legend, textStyle: { ...riskRecord(legend.textStyle), fontFamily: designTokens.fontFamily.sans } },
    tooltip: { ...tooltip, textStyle: { ...riskRecord(tooltip.textStyle), fontFamily: designTokens.fontFamily.sans } },
  } as EChartsOption} />;
}

/** Snapshot owns publication eligibility. Full analysis is an on-demand evidence source only. */
export function MarketRiskObservation({ snapshot, chartPalette }: { snapshot?: MarketOverviewSnapshotPayload; chartPalette?: MarketChartPalette }) {
  const client = useApiClient();
  const [detail, setDetail] = useState<Detail | null>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const section = useRef<HTMLElement | null>(null);
  useLayoutEffect(() => {
    if (detail) section.current?.querySelector<HTMLButtonElement>(".ant-drawer-close")?.focus({ preventScroll: true });
  }, [detail]);
  useEffect(() => {
    if (!detail) return;
    // A nested view can unmount the focused control. Keep Escape available until this drawer closes.
    const onEscape = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); setDetail(null); } };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [detail]);
  const crisis = snapshot?.crisis;
  const current = crisisCurrentPublishable(crisis);
  const history = useMemo(() => (crisis?.score_history ?? []).slice(-60), [crisis?.score_history]);
  const option = useMemo(() => crisisHistoryOption(history, chartPalette), [history, chartPalette]);
  const last = history.at(-1);
  const signals = snapshot?.signals;
  const marketSignals = signals?.status !== "unavailable" ? (signals?.cards ?? []).filter(card => card.kind === "market_signal") : [];
  const operationalCards = (signals?.cards ?? []).filter(card => card.kind === "ops_status");
  const operationalIssues = operationalCards.filter(card => ["negative", "warning", "error", "missing"].includes(card.tone ?? ""));
  const operationalStateUnconfirmed = operationalCards.some(card => !["positive", "neutral", "ok", "negative", "warning", "error", "missing"].includes(card.tone ?? ""));
  const actions = [...(snapshot?.actions?.items ?? [])].sort((a, b) => a.priority.localeCompare(b.priority));
  const news = snapshot?.news;
  const compare = news?.status !== "unavailable" ? news?.compare : undefined;
  const full = useQuery({
    queryKey: ["market-risk-evidence", client.mode, crisis?.report_date, "full", 60],
    queryFn: () => client.getMacroToolkitAnalysis({ detail: "full", historyLimit: 60 }),
    enabled: detail === "crisis" || detail === "commodity",
    retry: false,
  });
  const capability = full.data?.result.capability_results.find(item => item.key === "crisis_score_cn");
  const result = capability?.result;
  const evidenceReadable = capability?.status === "complete" || capability?.status === "degraded";
  const components = riskRows(result?.components);
  const weights = riskRecord(result?.weights);
  const componentKeys = [...new Set([...Object.keys(CRISIS_COMPONENT_LABELS), ...Object.keys(weights), ...components.map(row => riskText(row.key))])];
  const inputs = crisis?.input_evidence?.inputs ?? [];
  const reason = crisisPublicationReason(crisis);
  const open = (next: Detail) => { trigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; setDetail(next); };
  const close = () => setDetail(null);
  const fullError = full.isError;

  return <section ref={section} id="market-risk-observation" className={styles.section} aria-labelledby="market-risk-title">
    <h2 id="market-risk-title">风险观察</h2>
    <div className={styles.columns}>
      <article className={`${styles.panel} ${styles.crisis}`}>
        <div className={styles.heading}><h3>Crisis Score</h3><button type="button" onClick={() => open("crisis")}>评分依据</button></div>
        <p className={styles.muted}>报告日 {crisis?.report_date ?? EM_DASH}</p>
        <div className={styles.current}><strong data-testid="market-risk-current-score">{current ? localeOrDash(crisis?.score, "zh-CN", SCORE_OPTIONS) : EM_DASH}</strong><span className={!current ? styles.warning : undefined}>{current ? crisis?.regime ?? "级别未返回" : "当前待核验"}</span></div>
        <p className={styles.description}>{current ? `历史分位 ${localeOrDash(crisis?.percentile, "zh-CN", NUMBER_OPTIONS)}${crisis?.percentile == null ? "" : "%"}；分位不代表危机发生概率。` : <><DataValue value={crisis?.available_component_count} /> / <DataValue value={crisis?.component_count} /> 项可用；{reason}</>}</p>

        <div className={styles.history}><ChartCard flat height={160} option={option} chartRenderer={props => <RiskHistoryChart {...props} />} legend="none" emptyMessage="暂无可用历史序列" ariaLabel="Crisis Score 近 60 期历史" /></div>
        <p className={styles.caption}>近 {history.length} 期历史；虚线为部分输入或待核验结果</p>
        <div className={styles.trends}>{[20, 60].map(window => {
          const trend = crisis?.score_trends?.find(item => item.requested_window_points === window);
          return <div key={window}><span className={styles.muted}>{window} 期变化</span><strong className={styles.numeric}>{localeOrDash(trend?.score_change, "zh-CN", { ...SCORE_OPTIONS, signDisplay: "exceptZero" })}</strong></div>;
        })}</div>
        <div className={styles.heading}><p className={styles.muted}>历史末值 <DataValue value={last?.crisis_score} />{last ? ` / ${last.date}` : ""}</p><Link className={styles.button} to="/macro-toolkit">恢复与复核</Link></div>
      </article>
      <div className={styles.side}>
        <article className={styles.panel}><h3>市场信号</h3>
          {marketSignals.length ? marketSignals.map(card => <div key={card.key}><strong>{card.title ?? card.key}</strong><p>{card.stance ?? EM_DASH}</p></div>) : <><strong className={styles.warning}>方向暂不发布</strong><p className={styles.description}>{marketBusinessReason(signals?.reason, "流动性、风险偏好与信用信号等待有效证据。")}</p></>}
          <button type="button" onClick={() => open("signals")}>查看信号依据</button>
        </article>
        <article className={styles.panel}><h3>待核验事项</h3>
          {actions.map(action => <div className={styles.action} key={action.key}>
            <div className={styles.heading}><strong>{action.priority} {action.label}</strong>{action.key === "crisis_regime_review" || action.key === "news_human_review" ? <button type="button" onClick={() => open(action.key === "news_human_review" ? "news" : "crisis")}>去核验</button> : <Link className={styles.button} to={["/macro-toolkit", "/news-events", "/macro-observation"].includes(action.route) ? action.route : "/macro-toolkit"}>去核验</Link>}</div>
            <p className={styles.muted}>{action.key === "crisis_regime_review" ? "核对评分依据及当前可用范围。" : action.key === "news_human_review" ? <>同向 <DataValue value={compare?.same_direction} /> / 冲突 <DataValue value={compare?.conflicting} /> / 待复核 <DataValue value={compare?.review_needed} /></> : "请更新数据后复核受影响的分析结果。"}</p>
          </div>)}
          {operationalIssues.length > 0 ? <p className={styles.warning}>数据更新需复核，部分分析结果可能暂不可用。请查看信号依据。</p> : null}
          {operationalStateUnconfirmed && operationalIssues.length === 0 ? <p className={styles.muted}>部分数据的可用状态待核验，请查看信号依据。</p> : null}
          {!actions.length && operationalIssues.length === 0 && !operationalStateUnconfirmed && <p className={styles.muted}>{snapshot?.actions?.status === "ok" ? "当前无待核验事项。" : "核验事项尚未完整返回。"}</p>}
          {!actions.some(action => action.key === "news_human_review") && <button type="button" onClick={() => open("news")}>新闻比较与人工复核</button>}
        </article>
      </div>
    </div>
    <Drawer getContainer={false} open={detail !== null} width="min(640px, 100vw)" title={detail ? TITLES[detail] : "风险依据"} onClose={close} afterOpenChange={opened => { if (!opened) trigger.current?.focus(); }} rootClassName={styles.drawer} className={styles.drawerPanel} keyboard maskClosable destroyOnClose>
      {detail && <div className={styles.detail} data-moss-theme-scope="market-overview">
        <p className={styles.muted}>来源评分报告日 {crisis?.report_date ?? EM_DASH}</p>
        {(detail === "crisis" || detail === "commodity") && <>
          <p className={styles.muted}>完整分析实际日期 {full.data?.result.as_of_date ?? EM_DASH}。当前读取不代表来源日历史回放。</p>
          {full.isFetching && !full.data && <p role="status">正在读取完整评分依据…</p>}
          {fullError && <div role="alert"><p>评分依据读取失败，未使用缓存结果补当前评分。</p><button type="button" onClick={() => void full.refetch()}>重试</button></div>}
          {!full.isFetching && !fullError && !evidenceReadable && <p>完整分析未返回可用 Crisis Score 依据，暂不展示研究明细。</p>}
          {!fullError && capability?.status === "degraded" && <p className={styles.warning}>完整分析为部分可用，以下研究明细保留缺项与质量限制。</p>}
        </>}
        {detail === "crisis" && <>
          <section className={styles.detailBlock}><h3>当前发布状态</h3><p>{current ? `当前评分 ${localeOrDash(crisis?.score, "zh-CN", SCORE_OPTIONS)} / ${crisis?.regime ?? EM_DASH}` : `当前评分 ${EM_DASH}，当前待核验。${reason}`}</p><p>{crisis?.risk_gate?.eligible === true && current ? crisis.risk_gate.triggered ? "已触发后端风险阈值" : "具备判定资格，未触发后端阈值" : "不具备风险阈值判定资格，不能解释为安全"}；阈值 <DataValue value={crisis?.risk_gate?.threshold} /></p><p className={styles.muted}>规则 {crisis?.rule_version ?? EM_DASH}</p>{crisis?.reason && crisis.reason !== reason && <details><summary>原始诊断信息</summary><p className={styles.muted}>{crisis.reason}</p></details>}</section>
          <section className={styles.detailBlock}><h3>历史窗口</h3>{[20, 60].map(window => { const trend = crisis?.score_trends?.find(item => item.requested_window_points === window); return <div key={window}><strong>{window} 期变化 <DataValue value={trend?.score_change} /></strong><p className={styles.muted}>{trend?.start_date ?? EM_DASH} 至 {trend?.end_date ?? EM_DASH} / 实际 <DataValue value={trend?.window_points} /> 期</p><p className={styles.muted}>历史分位 <DataValue value={trend?.start_percentile} unit="%" /> 至 <DataValue value={trend?.end_percentile} unit="%" /></p><p className={styles.muted}>分位变化 <DataValue value={trend?.percentile_change} /> 百分点</p></div>; })}<p className={styles.muted}>历史分位是历史评分的相对位置，不代表危机概率。</p></section>
          {!fullError && evidenceReadable && <section className={styles.detailBlock}><h3>评分组成</h3><p className={styles.muted}>原始值与标准化值由后端返回；权重不等于当前实际贡献。</p>{componentKeys.map(key => { const row = components.find(item => item.key === key); return <div className={styles.evidenceRow} key={key}><strong>{CRISIS_COMPONENT_LABELS[key] ?? riskText(row?.label)}</strong><p>原始值 <DataValue value={row?.raw_value} />{riskNumber(row?.raw_value) !== null ? key === "credit_spread" || key === "liquidity_stress" ? " 百分点" : ["equity_vol", "fx_vol", "commodity_vol"].includes(key) ? " %" : "（单位待核验）" : ""} / z 值 <DataValue value={row?.z_score} /> / 权重 <DataValue value={weights[key] ?? row?.weight} percent /></p><p className={styles.muted}>{row ? `观察日 ${riskText(row.latest_date)}` : "组成项缺失，保留位置待补齐"}</p></div>; })}</section>}
          <section className={styles.detailBlock}><h3>评分输入</h3>{inputs.length ? inputs.map(input => <div className={styles.evidenceRow} key={input.field}><strong>{input.series_id === "CA.DR007" ? "FDR007（代理）" : CRISIS_INPUT_LABELS[input.field] ?? input.label}</strong><p>{input.available ? "有记录" : "缺少记录"}{input.stale ? " / 数据陈旧" : ""} / {input.latest_date ?? EM_DASH}</p><p className={styles.muted}>{input.series_id ?? EM_DASH} / {input.source ?? EM_DASH}</p>{input.series_id === "CA.DR007" && <p className={styles.warning}>CA.DR007 为 FDR007 代理，不等同于精确 DR007。</p>}</div>) : <p>评分输入证据未返回。</p>}</section>
          <section className={styles.detailBlock}><h3>计算口径</h3><p>实现波动窗口 20 期；标准化窗口 120 期，至少 60 期观测。分数越高表示该模型的压力越大。</p><p className={styles.muted}>部分输入结果按可用权重归一。组成项的原始值、标准化值和权重均以完整分析返回为准。</p></section><button type="button" onClick={() => setDetail("commodity")}>商品扩展与影子分析</button><Link className={styles.button} to={buildMarketSourceLink("/macro-observation", "risk", { market_observation_date: crisis?.report_date ?? undefined })}>进入宏观观察</Link>
        </>}
        {detail === "commodity" && <><button type="button" onClick={() => setDetail("crisis")}>返回评分依据</button><p className={styles.warning}>以下为只读研究与审批材料，不替代缺失的正式评分组成项。当前发布资格仍以首页核验状态为准。</p>{!fullError && evidenceReadable && <CommodityEvidence result={riskRecord(result)} />}<Link className={styles.button} to={buildMarketSourceLink("/macro-observation", "risk", { market_observation_date: crisis?.report_date ?? undefined })}>进入宏观观察</Link></>}
        {detail === "signals" && <><section className={styles.detailBlock}><h3>方向发布状态</h3><p>{marketBusinessReason(signals?.reason, marketSignals.length ? "当前市场信号可供参考。" : "方向暂不发布，等待有效证据。")}</p></section>{marketSignals.map(card => <section className={styles.detailBlock} key={card.key}><h3>{card.title ?? card.key}</h3><p>{card.stance ?? EM_DASH}</p>{card.evidence?.map((evidence, index) => <p key={index}>{evidence}</p>)}</section>)}{operationalCards.length > 0 || isMarketTechnicalReason(signals?.reason) ? <details className={styles.detailBlock}><summary>技术诊断</summary>{isMarketTechnicalReason(signals?.reason) ? <p>{signals?.reason}</p> : null}{operationalCards.map(card => <section key={card.key}><h3>运行核验：{card.title ?? card.key}</h3><p>{card.stance ?? EM_DASH}</p>{card.evidence?.map((evidence, index) => <p key={index}>{evidence}</p>)}</section>)}</details> : null}<p className={styles.muted}>方向标签不构成交易指令。</p><Link className={styles.button} to="/macro-toolkit">进入宏观工具</Link></>}
        {detail === "news" && <><section className={styles.detailBlock}><h3>新闻与市场信号比较</h3><p>同向 <DataValue value={compare?.same_direction} /> / 冲突 <DataValue value={compare?.conflicting} /> / 待复核 <DataValue value={compare?.review_needed} /></p><p>候选情景 <DataValue value={compare?.candidate_scenarios} /></p><p className={styles.muted}>各类计数可能重叠，不相加为新闻总数。比较结果用于人工核对，不证明因果。</p>{news?.reason && <p>{news.reason}</p>}</section>{compare?.review_items?.length ? compare.review_items.map((item, index) => <section className={styles.detailBlock} key={riskText(item.event_key) + index}><h3>{riskText(item.headline)}</h3><p className={styles.muted}>主题 {riskText(item.topic_code)} / {riskText(item.theme)}</p><p className={styles.muted}>接收时间 {riskText(news?.latest?.find(event => event.event_key === item.event_key)?.received_at)}</p><p>{item.human_review_required === true ? "需要人工复核" : "核对原始新闻与市场证据"}</p></section>) : <p>{compare ? "当前未返回人工复核明细。" : "新闻比较依据尚不可用。"}</p>}<Link className={styles.button} to={buildMarketSourceLink("/news-events", "risk")}>进入新闻事件</Link></>}
      </div>}
    </Drawer>
  </section>;
}

function CommodityEvidence({ result }: { result: Record<string, unknown> }) {
  const coverage = riskRecord(result.commodity_coverage);
  const shadow = riskRecord(result.shadow_impact);
  const admission = riskRecord(result.commodity_candidate_admission);
  const approval = riskRecord(result.commodity_candidate_approval_pack);
  const counts = riskRecord(admission.decision_counts);
  return <>
    <nav className={styles.chapters} aria-label="商品研究章节">{[["coverage", "覆盖"], ["shadow", "影子分析"], ["admission", "准入与审批"]].map(([id, title]) => <button type="button" key={id} onClick={() => document.getElementById(`market-risk-${id}`)?.scrollIntoView({ block: "start" })}>{title}</button>)}</nav>
    <section id="market-risk-coverage" className={styles.detailBlock}><h3>商品覆盖</h3><p><DataValue value={coverage.available_count} /> 类有记录 / <DataValue value={coverage.tracked_count} /> 类跟踪</p>{riskRows(coverage.items).map(row => <div className={styles.evidenceRow} key={riskText(row.field)}><strong>{COMMODITY_LABELS[riskText(row.field)] ?? riskText(row.label)}</strong><p>{riskText(row.latest_date)} / {row.available === true ? "有记录" : "记录待补"} / {row.used_in_formula === false ? "未入正式公式" : "公式归属待核验"}</p><p className={styles.muted}>{riskText(row.source)} / {riskText(row.series_id)}</p><p className={styles.muted}>{row.date_alignment_status === "lagging" ? "观察日落后于分析日" : row.date_alignment_status === "aligned" ? "与分析日一致" : "日期对齐待核验"}</p></div>)}{!riskRows(coverage.items).length && <p>商品覆盖未返回。</p>}</section>
    <section id="market-risk-shadow" className={styles.detailBlock}><h3>影子公式比较</h3><p>原始模型试算 <DataValue value={shadow.current_score} /></p><p>影子试算 <DataValue value={shadow.shadow_score} /></p><p>试算差额 <DataValue value={shadow.delta} /></p><p className={styles.warning}>这里的原始模型试算属于研究输入，不是当前可发布评分。</p><p className={styles.muted}>方法 {riskText(shadow.formula_version)}</p>{riskRows(shadow.candidate_contributions).map(row => <div className={styles.evidenceRow} key={riskText(row.field)}><strong>{COMMODITY_LABELS[riskText(row.field)] ?? riskText(row.label)}</strong><p>z 值 <DataValue value={row.candidate_value} /> / 权重 <DataValue value={row.weight} percent /> / 后端贡献 <DataValue value={row.contribution} /></p><p className={styles.muted}>{riskText(row.latest_date)} / {row.used_in_official_score === false ? "未计入正式评分" : "正式归属待核验"}</p></div>)}<p>{riskText(shadow.next_step)}</p></section>
    <section id="market-risk-admission" className={styles.detailBlock}><h3>候选准入</h3><p>建议纳入 <DataValue value={counts.recommend_include} /> / 继续观察 <DataValue value={counts.watch} /> / 不纳入 <DataValue value={counts.do_not_include} /></p><p className={styles.muted}>相关系数取后端绝对值最大项，用于评估，不代表因果。</p>{riskRows(admission.items).map(row => <div className={styles.evidenceRow} key={riskText(row.field)}><strong>{COMMODITY_LABELS[riskText(row.field)] ?? riskText(row.label)} / {riskText(row.decision_label)}</strong><p>样本 <DataValue value={row.sample_count} /> / 危机样本 <DataValue value={row.crisis_sample_count} /> / 相关 <DataValue value={row.max_abs_correlation} /></p><p className={styles.muted}>危机期命中率 <DataValue value={row.crisis_hit_rate} percent /> / 相关阈值 <DataValue value={row.correlation_threshold} /></p><p>{riskText(row.reason)}</p></div>)}<p className={styles.muted}>规则 {riskText(admission.rule_version)}</p></section>
    <section className={styles.detailBlock}><h3>审批材料（只读）</h3><p>{riskText(approval.summary)}</p><p className={styles.warning}>材料保留后端原文，其中“正式评分”措辞属于试算材料，不解除首页发布限制。</p><textarea aria-label="审批材料原文" readOnly value={riskText(approval.copy_text)} rows={12} /><p className={styles.muted}>审批与权重调整在既有治理流程完成，此处不会提交或修改公式。</p></section>
  </>;
}
