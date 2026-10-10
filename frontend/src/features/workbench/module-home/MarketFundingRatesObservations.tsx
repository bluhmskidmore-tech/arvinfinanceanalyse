import { useEffect, useState, type ReactNode } from "react";
import { Drawer, Grid } from "antd";
import { Link } from "react-router-dom";

import type { MarketFundingObservation, MarketObservationBase, MarketRatesObservation } from "../../../api/contracts/marketMacro";
import { ChartCard, type ChartCardRendererProps } from "../../../components/charts/ChartCard";
import { BaseChart } from "../../../components/charts/BaseChart";
import { DataTable } from "../../../components/layout/DataTable";
import type { EChartsOption } from "../../../lib/echarts";
import { EM_DASH, localeOrDash } from "../../../pageModel";
import { designTokens } from "../../../theme/designSystem";
import { MARKET_CHART_STATIC_PALETTE } from "./marketChartPalette";
import styles from "./marketFundingRatesObservations.module.css";

const numberOptions: Intl.NumberFormatOptions = { maximumSignificantDigits: 15 };
const fundingControlsStorageKey = "moss:market-home:funding-controls";
const keyRatesHash = "#market-overview-chart-key-rate-trend";

function savedFundingControls(): { view?: string; series?: string } {
  try { return JSON.parse(sessionStorage.getItem(fundingControlsStorageKey) ?? "{}"); }
  catch { return {}; }
}

/** Keep shared chart chrome and apply only the market page's approved local font. */
function MarketObservationChart({ option, height }: ChartCardRendererProps) {
  const legend = option.legend as Record<string, unknown>;
  const tooltip = option.tooltip as Record<string, unknown>;
  return <BaseChart height={height} option={{
    ...option,
    textStyle: { ...option.textStyle, fontFamily: designTokens.fontFamily.sans },
    legend: { ...legend, textStyle: { ...(legend.textStyle as object), fontFamily: designTokens.fontFamily.sans } },
    tooltip: { ...tooltip, textStyle: { ...(tooltip.textStyle as object), fontFamily: designTokens.fontFamily.sans } },
  } as EChartsOption} />;
}

/** Only formats backend values; all changes and spreads are calculated by the service. */
function ObservationNumber({ value, unit, signed = false }: { value: number | null; unit: string; signed?: boolean }) {
  return <span className={styles.number} data-direction={signed && value != null ? (value > 0 ? "up" : value < 0 ? "down" : "flat") : undefined}>
    {localeOrDash(value, "zh-CN", { ...numberOptions, signDisplay: signed ? "exceptZero" : "auto" })}
    {value != null ? <small> {unit}</small> : null}
  </span>;
}

function ObservationEvidence({ observation }: { observation: MarketObservationBase }) {
  return <>
    <p>观察日 {observation.observation_date ?? EM_DASH}；比较日 {observation.comparison_date ?? EM_DASH}</p>
    <p>{observation.reason ?? "使用范围见每项证据。"}</p>
    {observation.evidence.map((row) => <section className={styles.evidenceRow} key={row.key}>
      <h4>{row.label}</h4>
      <dl>
        <dt>观测值 / 单位</dt><dd>{row.value == null ? EM_DASH : String(row.value)} / {row.unit}</dd>
        <dt>观测日期</dt><dd>{row.observation_date ?? EM_DASH}</dd>
        <dt>比较值 / 日期</dt><dd>{row.previous_value == null ? EM_DASH : String(row.previous_value)} / {row.previous_date ?? EM_DASH}</dd>
        <dt>变化（bp）</dt><dd>{row.change_bp == null ? EM_DASH : String(row.change_bp)}</dd>
        <dt>序列</dt><dd>{row.series_id}</dd>
        <dt>来源</dt><dd>{row.source ?? EM_DASH}</dd>
        <dt>质量 / 回退</dt><dd>{row.quality_flag} / {row.fallback_mode}</dd>
        <dt>代理说明</dt><dd>{row.is_proxy ? "代理序列；适用限制见来源说明" : "非代理"}</dd>
      </dl>
      {row.reason ? <p>{row.reason}</p> : null}
    </section>)}
    <p>规则版本 {observation.rule_version}</p>
    <Link to={observation.verification_route}>打开来源核验</Link>
  </>;
}

function ObservationNotes({ observation }: { observation: MarketObservationBase }) {
  return <div className={styles.notes}>
    <h4>观察结论</h4>
    <p className={styles.summary} data-restricted={!observation.judgment_allowed}>{observation.summary}</p>
    {observation.reason && observation.reason !== observation.summary ? <p className={styles.warning}>{observation.reason}</p> : null}
    <h4>如何理解</h4>
    <p>{observation.interpretation}</p>
  </div>;
}

export function MarketFundingRatesObservations({ funding, rates, children, display = "all", keyRatesContent }: {
  funding?: MarketFundingObservation;
  rates?: MarketRatesObservation;
  children?: ReactNode;
  display?: "all" | "funding" | "rates";
  keyRatesContent?: ReactNode;
}) {
  const screens = Grid.useBreakpoint();
  const hasKeyRates = Boolean(keyRatesContent);
  const [fundingView, setFundingView] = useState<"funding" | "key-rates">(() => savedFundingControls()?.view === "key-rates" && keyRatesContent ? "key-rates" : "funding");
  const [evidence, setEvidence] = useState<"funding" | "rates" | null>(null);
  const [fundingSeries, setFundingSeries] = useState(() => {
    const saved = savedFundingControls()?.series;
    return typeof saved === "string" ? saved : "dr007";
  });
  useEffect(() => {
    if (display === "rates") return;
    try { sessionStorage.setItem(fundingControlsStorageKey, JSON.stringify({ view: fundingView, series: fundingSeries })); }
    catch { /* Browser storage may be disabled; current-page controls remain usable. */ }
  }, [display, fundingSeries, fundingView]);
  useEffect(() => {
    if (display === "rates" || !hasKeyRates) return;
    let frame = 0;
    const reveal = () => {
      setFundingView("key-rates");
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const target = document.getElementById(keyRatesHash.slice(1));
        if (!target) return;
        target.tabIndex = -1;
        target.scrollIntoView?.({ block: "start" });
        target.focus({ preventScroll: true });
      });
    };
    const onHashChange = () => { if (window.location.hash === keyRatesHash) reveal(); };
    const onReferenceClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest("a") : null;
      if (anchor?.getAttribute("href") === keyRatesHash) reveal();
    };
    onHashChange();
    window.addEventListener("hashchange", onHashChange);
    document.addEventListener("click", onReferenceClick);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("hashchange", onHashChange);
      document.removeEventListener("click", onReferenceClick);
    };
  }, [display, hasKeyRates]);
  const selectedRow = funding?.rows.find((row) => row.key === fundingSeries) ?? funding?.rows[0];
  const policy = funding?.policy_reference;
  const palette = MARKET_CHART_STATIC_PALETTE;
  const axisChrome = {
    axisLabel: { color: palette.inkMuted, fontSize: 11, fontFamily: designTokens.fontFamily.sans },
    nameTextStyle: { color: palette.inkSoft },
    axisLine: { lineStyle: { color: palette.lineSoft } },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: palette.lineSoft, type: "dashed" as const, opacity: 0.65 } },
  };
  const tooltipChrome = {
    trigger: "axis" as const,
    backgroundColor: palette.panel2,
    borderColor: palette.lineSoft,
    textStyle: { color: palette.ink },
    confine: true,
  };
  const fundingDates = selectedRow?.recent_points.map((point) => point.trade_date) ?? [];
  const fundingOption: EChartsOption | null = selectedRow?.recent_points.length ? {
    animation: false,
    grid: { left: 8, right: 8, top: 12, bottom: 28, containLabel: true },
    color: [MARKET_CHART_STATIC_PALETTE.accent, MARKET_CHART_STATIC_PALETTE.amber],
    tooltip: tooltipChrome,
    xAxis: { ...axisChrome, type: "category", boundaryGap: false, data: fundingDates, axisLabel: { ...axisChrome.axisLabel, formatter: (date: string) => date.slice(5), interval: Math.floor(fundingDates.length / 4) }, splitLine: { show: false } },
    yAxis: { ...axisChrome, type: "value", scale: true },
    series: [
      { name: selectedRow.label, type: "line", smooth: false, showSymbol: false, lineStyle: { width: 1.8 }, connectNulls: false, data: selectedRow.recent_points.map((point) => point.value_numeric) },
      ...(selectedRow.key === "dr007" && policy?.validity_status === "verified" && policy.effective_from && policy.unit === selectedRow.unit ? [{
        name: "有效政策基准", type: "line" as const, step: "end" as const, connectNulls: false,
        data: fundingDates.map((date) => date >= policy.effective_from! && (!policy.effective_to || date <= policy.effective_to) ? policy.value : null),
      }] : []),
    ],
  } : null;
  const curveRows = rates?.rows ?? [];
  const curveOption: EChartsOption | null = curveRows.some((row) => row.value != null || row.previous_value != null) ? {
    animation: false,
    grid: { left: 12, right: 40, top: 16, bottom: 28, containLabel: true },
    color: [MARKET_CHART_STATIC_PALETTE.accent, MARKET_CHART_STATIC_PALETTE.inkMuted],
    tooltip: tooltipChrome,
    xAxis: { ...axisChrome, type: "category", boundaryGap: false, data: curveRows.map((row) => row.label), splitLine: { show: false } },
    yAxis: { ...axisChrome, type: "value", scale: true },
    series: [
      { name: `观察日 ${rates?.observation_date ?? EM_DASH}`, type: "line", smooth: false, symbol: "circle", symbolSize: 6, lineStyle: { width: 2 }, connectNulls: false, labelLayout: (point) => ({ align: point.dataIndex === 0 ? "left" : point.dataIndex === curveRows.length - 1 ? "right" : "center" }), label: { show: true, position: "top", distance: 12, color: palette.inkSoft, fontSize: 12, fontFamily: designTokens.fontFamily.tabular, formatter: (point) => typeof point.value === "number" ? `${point.value.toFixed(4)}%` : "" }, data: curveRows.map((row) => rates?.observation_date && row.observation_date === rates.observation_date ? row.value : null) },
      { name: `比较日 ${rates?.comparison_date ?? EM_DASH}`, type: "line", smooth: false, symbol: "emptyCircle", symbolSize: 5, connectNulls: false, lineStyle: { width: 1.5, type: "dashed" }, data: curveRows.map((row) => rates?.comparison_date && row.previous_date === rates.comparison_date ? row.previous_value : null) },
    ],
  } : null;
  const activeObservation = evidence === "funding" ? funding : evidence === "rates" ? rates : undefined;

  return <>
    <div className={display === "all" ? styles.grid : styles.single} data-testid="market-funding-rates-observations">
      {display !== "rates" && <section className={styles.panel} aria-labelledby="market-funding-title">
        {keyRatesContent ? <div className={styles.tabs} role="group" aria-label="资金与利率图表"><button type="button" aria-pressed={fundingView === "funding"} onClick={() => setFundingView("funding")}>资金价格</button><button type="button" aria-pressed={fundingView === "key-rates"} onClick={() => setFundingView("key-rates")}>关键利率</button></div> : null}
        <div hidden={fundingView !== "funding"}>
        <header className={styles.header}>
          <div className={styles.heading}><h3 id="market-funding-title">资金价格</h3><span className={styles.window}>{funding?.window_label ?? EM_DASH}</span></div>
          {funding ? <label className={styles.select}><span className={styles.srOnly}>走势指标</span><select aria-label="走势指标" value={selectedRow?.key ?? fundingSeries} onChange={(event) => setFundingSeries(event.target.value)}>{funding.rows.map((row) => <option value={row.key} key={row.key}>{row.label}</option>)}</select></label> : null}
        </header>
        <p className={styles.dates}>资金观察日 {funding?.observation_date ?? EM_DASH}；比较日 {funding?.comparison_date ?? EM_DASH} · {selectedRow?.unit ?? "单位待返回"}</p>
        {funding ? <>
          <div className={styles.controls}>
            <div className={styles.statuses} role="status">
              {!funding.judgment_allowed ? <span className={styles.restricted} title={funding.reason ?? funding.summary}>判断受限</span> : funding.status !== "ok" ? <span className={styles.restricted}>{funding.status === "unavailable" ? "观察不可用" : "部分可用"}</span> : null}
              {selectedRow?.is_proxy ? <span className={styles.proxy} title={selectedRow.reason ?? "当前所选序列为代理参考。"}>代理参考</span> : null}
              {policy?.validity_status !== "verified" ? <span className={styles.restricted} title={policy?.reason ?? undefined}>政策基准待核验</span> : null}
            </div>
          </div>
          {funding.judgment_allowed && display === "all" ? <p className={styles.summary}>{funding.summary}</p> : null}
          <ChartCard flat ariaLabel={`资金价格${funding.window_label}`} testId="market-funding-chart" height={220} option={fundingOption} chartRenderer={(props) => <MarketObservationChart {...props} />} emptyMessage="暂无可展示的历史观测" />
          <div className={styles.footer}>
            <details className={styles.details}>
            <summary>资金明细与说明</summary>
            <ObservationNotes observation={funding} />
            {selectedRow?.reason && selectedRow.reason !== funding.reason && selectedRow.reason !== funding.summary && selectedRow.reason !== policy?.reason ? <p className={styles.warning}>{selectedRow.reason}</p> : null}
            <p className={styles.limitation}>真实观测缺口留空；政策基准只显示已核验的有效区间。</p>
            <DataTable rows={funding.rows} rowKey="key" rowHeaderKey="label" ariaLabel="资金价格与比较日期" emptyMessage="资金观测缺失" columns={[
              { key: "label", title: "指标", render: (row) => <span>{row.label}{row.key === "shibor_3m" ? <small className={styles.secondary}>期限报价参考</small> : null}<time className={styles.secondary}>{row.observation_date ?? EM_DASH}</time></span> },
              { key: "value", title: "观测值", align: "numeric", render: (row) => <ObservationNumber value={row.value} unit={row.unit} /> },
              { key: "change", title: "较比较日变化", align: "numeric", render: (row) => <><ObservationNumber value={row.change_bp} unit="bp" signed /><time className={styles.secondary}>{row.previous_date ?? EM_DASH}</time></> },
            ]} />
            <div className={styles.policy}>
              <span>相对政策基准偏离</span>
              {policy?.validity_status === "verified" ? <><strong><ObservationNumber value={funding.policy_deviation_bp} unit="bp" signed /></strong><small>基准 <ObservationNumber value={policy.value} unit={policy.unit} />；生效日 {policy.effective_from ?? EM_DASH}</small></> : <strong>{EM_DASH}</strong>}
              {policy?.reason ? <small>{policy.reason}</small> : null}
            </div>
            <div className={styles.limitations}>{funding.limitations.filter((limitation) => limitation !== policy?.reason).map((limitation, index) => <p className={styles.limitation} key={`${index}-${limitation}`}>{limitation}</p>)}</div>
            </details>
            <button className={styles.evidenceButton} type="button" onClick={() => setEvidence("funding")}>查看资金依据</button>
          </div>
        </> : <p className={styles.warning}>资金观察尚未返回，暂不形成判断。</p>}
        </div>
        {keyRatesContent ? <div hidden={fundingView !== "key-rates"}>{keyRatesContent}</div> : null}
      </section>}

      {display !== "funding" && <section className={`${styles.panel} ${styles.curvePanel}`} aria-labelledby="market-rates-title">
        <header className={styles.header}><div className={styles.heading}><h3 id="market-rates-title">国债收益率曲线</h3><span className={styles.window}>收益率（%）</span></div><button className={styles.headerAction} type="button" onClick={() => setEvidence("rates")}>查看曲线依据</button></header>
        <p className={styles.dates}>曲线观察日 {rates?.observation_date ?? EM_DASH}；比较日 {rates?.comparison_date ?? EM_DASH} · %</p>
        {rates ? <>
          {(!rates.judgment_allowed || rates.status !== "ok" || !rates.full_curve_comparison_allowed || display === "all") && <div className={styles.controls}>
            <div className={styles.statuses} role="status">
              {!rates.judgment_allowed ? <span className={styles.restricted} title={rates.reason ?? rates.summary}>判断受限</span> : rates.status !== "ok" ? <span className={styles.restricted}>{rates.status === "unavailable" ? "观察不可用" : "部分可用"}</span> : null}
              {!rates.full_curve_comparison_allowed ? <span className={styles.restricted}>跨期比较待核验</span> : <span className={styles.context}>同口径两期比较</span>}
            </div>
          </div>}
          {rates.judgment_allowed && display === "all" ? <p className={styles.summary}>{rates.summary}</p> : null}
          <ChartCard flat ariaLabel="两期国债曲线" testId="market-rates-chart" height={screens.md ? 280 : 220} option={curveOption} chartRenderer={(props) => <MarketObservationChart {...props} />} emptyMessage="国债曲线观测缺失" />
          <div className={styles.footer}>
            <details className={styles.details}>
            <summary>曲线明细与说明</summary>
            <ObservationNotes observation={rates} />
            <p className={styles.limitation}>{rates.full_curve_comparison_allowed ? "同一曲线口径的两期比较；变化与期限利差见下表。" : "跨期比较条件未全部核验，请按各项日期与使用限制核对。"}</p>
            <DataTable rows={curveRows} rowKey="key" rowHeaderKey="label" ariaLabel="国债分期限变化" emptyMessage="关键期限缺失" columns={[
              { key: "label", title: "期限", render: (row) => <span title={row.reason ?? undefined}>{row.label}<time className={styles.secondary}>{row.observation_date ?? EM_DASH}</time></span> },
              { key: "previous", title: "比较值", align: "numeric", render: (row) => <><ObservationNumber value={row.previous_value} unit={row.unit} /><time className={styles.secondary}>{row.previous_date ?? EM_DASH}</time></> },
              { key: "value", title: "观测值", align: "numeric", render: (row) => <ObservationNumber value={row.value} unit={row.unit} /> },
              { key: "change", title: "变化", align: "numeric", render: (row) => <ObservationNumber value={row.change_bp} unit="bp" signed /> },
            ]} />
            <DataTable rows={rates.spreads} rowKey="key" rowHeaderKey="label" ariaLabel="国债期限利差变化" emptyMessage="期限利差缺失" columns={[
              { key: "label", title: "期限利差", render: (row) => <span>{row.label}{row.reason ? <small className={styles.secondary}>{row.reason}</small> : null}</span> },
              { key: "previous", title: "比较值", align: "numeric", render: (row) => <ObservationNumber value={row.previous_value_bp} unit="bp" /> },
              { key: "value", title: "观测值", align: "numeric", render: (row) => <ObservationNumber value={row.value_bp} unit="bp" /> },
              { key: "change", title: "变化", align: "numeric", render: (row) => <ObservationNumber value={row.change_bp} unit="bp" signed /> },
            ]} />
            <div className={styles.limitations}>{rates.limitations.map((limitation, index) => <p className={styles.limitation} key={`${index}-${limitation}`}>{limitation}</p>)}</div>
            </details>
          </div>
        </> : <p className={styles.warning}>国债曲线观察尚未返回，暂不形成判断。</p>}
      </section>}
      {children}
    </div>
    <Drawer open={activeObservation != null} onClose={() => setEvidence(null)} title={evidence === "funding" ? "资金条件依据" : "利率定价依据"} width="min(720px, 100vw)" rootClassName={`theme-dh-api ${styles.drawer}`} data-moss-theme-scope="market-overview">
      {activeObservation ? <ObservationEvidence observation={activeObservation} /> : null}
      {evidence === "funding" && policy ? <section className={styles.evidenceRow}><h4>政策基准有效性</h4><p>{policy.validity_status === "verified" ? "已核验" : "待核验"}</p><p>原值 {policy.value == null ? EM_DASH : String(policy.value)} {policy.unit}；生效日 {policy.effective_from ?? EM_DASH}；有效至 {policy.effective_to ?? EM_DASH}</p><p>来源 {policy.source ?? EM_DASH}</p><p>{policy.reason}</p></section> : null}
      {evidence === "rates" ? rates?.spreads.map((spread) => <section className={styles.evidenceRow} key={spread.key}><h4>{spread.label}</h4><p>观察日 {spread.observation_date ?? EM_DASH}；比较日 {spread.comparison_date ?? EM_DASH}</p><p>输入序列 {spread.input_keys.join("、")}</p><p>观测值 {spread.value_bp == null ? EM_DASH : String(spread.value_bp)} bp；比较值 {spread.previous_value_bp == null ? EM_DASH : String(spread.previous_value_bp)} bp；变化 {spread.change_bp == null ? EM_DASH : String(spread.change_bp)} bp</p><p>{spread.reason}</p></section>) : null}
    </Drawer>
  </>;
}
