import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Select, Spin, Typography } from "antd";

import type { Numeric } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import type { DataSectionState } from "../../../components/DataSection.types";
import { ChartCard } from "../../../components/charts/ChartCard";
import { CHART_CARD_HEIGHTS } from "../../../components/charts/chartCardScale";
import { DataTable, SectionHead, type DataTableColumn } from "../../../components/layout";
import { PageDataSection } from "../../../components/page/PageDataSection";
import { modeBadgeStyle } from "../../../components/page/pageStyles";
import { type EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import { adaptCashflowProjection, type CashflowMaturingAssetVM } from "../adapters/cashflowProjectionAdapter";
import { EM_DASH } from "../../../utils/format";
import {
  cashflowRateSensitivityYiDisplay,
  selectCashflowConclusion,
  describeCashflowWarning,
  selectCashflowDurationGapTone,
  selectCashflowDurationGapTrendLabel,
  selectCashflowMonthlyProjectionSeries,
  selectCashflowProjectionRiskReadout,
  selectCashflowRateSensitivitySemantic,
  tooltipYi,
  toYi,
  type CashflowConclusion,
  type CashflowDurationGapTone,
} from "./cashflowProjectionPageModel";
import styles from "./CashflowProjectionPage.module.css";

type KpiSpec = {
  key: string;
  testId: string;
  title: string;
  value: Numeric;
  detail: string;
  priority: "primary" | "supporting" | "supplemental";
  tone?: "default" | "positive" | "negative" | "warning" | CashflowDurationGapTone;
};

type RailPoint = {
  label: string;
  /** hover 披露：月份 + 亿元读数（缺数月标注缺数）。 */
  title: string;
  height: number;
  tone: "positive" | "negative" | "neutral" | "missing";
};

function axisYiLabel(value: number): string {
  if (!Number.isFinite(value)) return "";
  return `${toYi(value).toFixed(1)}亿`;
}

const TOP_MATURING_ASSETS_COLUMNS: readonly DataTableColumn<CashflowMaturingAssetVM>[] = [
  { key: "instrumentCode", title: "代码" },
  { key: "instrumentName", title: "名称" },
  { key: "maturityDate", title: "到期日" },
  { key: "faceValue", title: "面值", align: "numeric", render: (row) => row.faceValue.display },
  { key: "marketValue", title: "市值", align: "numeric", render: (row) => row.marketValue.display },
];

function buildProjectionRail(
  monthlySeries: ReturnType<typeof selectCashflowMonthlyProjectionSeries>,
): RailPoint[] {
  if (!monthlySeries) return [];
  const values = monthlySeries.cumulativeNet.slice(0, 24);
  const maxAbs = Math.max(1, ...values.map((value) => (value === null ? 0 : Math.abs(value))));
  return values.map((value, index) => {
    const label = monthlySeries.categories[index] ?? "";
    if (value === null) {
      return { label, title: `${label} · 缺数`, height: 10, tone: "missing" };
    }
    return {
      label,
      title: `${label} · ${tooltipYi(value)}`,
      height: Math.max(10, Math.round((Math.abs(value) / maxAbs) * 42)),
      tone: value > 0 ? "positive" : value < 0 ? "negative" : "neutral",
    };
  });
}

export default function CashflowProjectionPage() {
  const client = useApiClient();
  const datesQuery = useQuery({
    queryKey: ["cashflow-projection", "balance-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
  });

  const dateOptions = datesQuery.data?.result.report_dates ?? [];
  const [reportDate, setReportDate] = useState<string>("");

  const effectiveDate = reportDate || dateOptions[0] || "";

  const projectionQuery = useQuery({
    queryKey: ["cashflow-projection", client.mode, effectiveDate],
    queryFn: () => client.getCashflowProjection(effectiveDate),
    enabled: Boolean(effectiveDate),
    retry: false,
  });

  const adapted = useMemo(
    () =>
      adaptCashflowProjection({
        envelope: projectionQuery.data,
        isLoading: projectionQuery.isLoading,
        isError: projectionQuery.isError,
      }),
    [projectionQuery.data, projectionQuery.isLoading, projectionQuery.isError],
  );
  const sectionState = useMemo<DataSectionState>(() => {
    if (datesQuery.isLoading && !effectiveDate) {
      return { kind: "loading" };
    }
    if (!effectiveDate && !datesQuery.isLoading) {
      return {
        kind: "empty",
        hint: "未取得可用报告日，现金流预测暂无法展示。",
      };
    }
    return adapted.state;
  }, [adapted.state, datesQuery.isLoading, effectiveDate]);
  const vm = adapted.vm;
  const projectionMeta = adapted.meta;
  const conclusion: CashflowConclusion = selectCashflowConclusion(vm?.kpis.durationGap);
  const monthlySeries = useMemo(() => selectCashflowMonthlyProjectionSeries(vm), [vm]);
  const riskReadout = useMemo(() => selectCashflowProjectionRiskReadout(vm), [vm]);
  const projectionRail = useMemo(() => buildProjectionRail(monthlySeries), [monthlySeries]);
  const rateSensitivity1bpDisplay = cashflowRateSensitivityYiDisplay(vm?.kpis.rateSensitivity1bp);
  const rateSensitivitySemantic = useMemo(
    () => selectCashflowRateSensitivitySemantic(vm?.kpis.rateSensitivity1bp),
    [vm?.kpis.rateSensitivity1bp],
  );
  // 决策条与 KPI 卡同读数同色：正缺口琥珀/中性（2026-07-19 红线，禁 up 绿），敏感度负值红。
  const durationGapTone = selectCashflowDurationGapTone(vm?.kpis.durationGap);
  const deckGapToneClass =
    durationGapTone === "default" ? "" : (styles[`deckValue_${durationGapTone}`] ?? "");
  const deckSensitivityToneClass =
    rateSensitivitySemantic.tone === "default"
      ? ""
      : (styles[`deckValue_${rateSensitivitySemantic.tone}`] ?? "");
  const warningDisplays = useMemo(
    () => (vm?.warnings ?? []).map(describeCashflowWarning),
    [vm?.warnings],
  );
  const warningOriginals = warningDisplays.flatMap((item) =>
    item.original === null ? [] : [item.original],
  );
  const kpis = useMemo<KpiSpec[]>(() => {
    if (!vm) return [];
    return [
      {
        key: "duration-gap",
        testId: "cashflow-kpi-duration-gap",
        title: "久期缺口（年）",
        value: vm.kpis.durationGap,
        detail: "资产久期 - 负债久期",
        priority: "primary",
        tone: selectCashflowDurationGapTone(vm.kpis.durationGap),
      },
      {
        key: "dv01",
        testId: "cashflow-kpi-dv01",
        title: "1bp 敏感度",
        value: { ...vm.kpis.rateSensitivity1bp, display: rateSensitivity1bpDisplay },
        detail: rateSensitivitySemantic.detail,
        priority: "primary",
        tone: rateSensitivitySemantic.tone,
      },
      {
        key: "asset-duration",
        testId: "cashflow-kpi-asset-dur",
        title: "资产久期（年）",
        value: vm.kpis.assetDuration,
        detail: "资产侧久期",
        priority: "supporting",
      },
      {
        key: "liability-duration",
        testId: "cashflow-kpi-liability-dur",
        title: "负债久期（年）",
        value: vm.kpis.liabilityDuration,
        detail: "负债侧久期",
        priority: "supporting",
      },
      {
        key: "equity-duration",
        testId: "cashflow-kpi-equity-dur",
        title: "权益久期（年）",
        value: vm.kpis.equityDuration,
        detail: "权益侧久期",
        priority: "supplemental",
      },
      {
        key: "reinvest-risk",
        testId: "cashflow-kpi-reinvest",
        title: "再投资风险（12M）",
        value: vm.kpis.reinvestmentRisk12m,
        detail: "12 个月再投资风险",
        priority: "supplemental",
        tone: "warning",
      },
    ];
  }, [rateSensitivity1bpDisplay, rateSensitivitySemantic, vm]);

  const chartOption = useMemo((): EChartsOption | null => {
    if (!monthlySeries) {
      return null;
    }
    return {
      // canvas 不消费 CSS 变量：取色走 nocturneTokens 常量组（组合工作台先例）。
      // 语义：资产流入=绿 / 负债流出=红 / 累计净现金流=accent，方向不变仅去饱和。
      color: [
        nocturneTokens.color.green,
        nocturneTokens.color.red,
        nocturneTokens.color.blue,
      ],
      animationDuration: 420,
      grid: { left: 64, right: 24, top: 54 },
      tooltip: {
        trigger: "axis",
        // 直接透传 value：缺失桶的 null/空串由 tooltipYi 拦成 EM_DASH，
        // 先 Number() 会把它们变成 0 再显示成 0.00 亿。
        valueFormatter: (value) => tooltipYi(value),
      },
      legend: {
        data: ["资产流入", "负债流出", "累计净现金流"],
      },
      xAxis: {
        type: "category",
        data: monthlySeries.categories,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: nocturneTokens.color.line } },
        axisLabel: { color: nocturneTokens.color.inkMuted, rotate: 30 },
      },
      yAxis: [
        {
          type: "value",
          name: "当月流量",
          nameTextStyle: { color: nocturneTokens.color.inkMuted },
          axisLabel: { color: nocturneTokens.color.inkMuted, formatter: axisYiLabel },
          splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
        },
        {
          type: "value",
          name: "累计",
          nameTextStyle: { color: nocturneTokens.color.inkMuted },
          axisLabel: { color: nocturneTokens.color.inkMuted, formatter: axisYiLabel },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "资产流入",
          type: "bar",
          data: monthlySeries.assetInflow,
          barMaxWidth: 22,
        },
        {
          name: "负债流出",
          type: "bar",
          data: monthlySeries.liabilityOutflow,
          barMaxWidth: 22,
        },
        {
          name: "累计净现金流",
          type: "line",
          yAxisIndex: 1,
          data: monthlySeries.cumulativeNet,
          smooth: true,
          symbolSize: 6,
          lineStyle: { width: 3 },
          emphasis: { focus: "series" },
        },
      ],
    };
  }, [monthlySeries]);

  return (
    <section
      data-testid="cashflow-projection-page"
      data-moss-theme-scope="cashflow-projection"
      className={styles.page}
    >
      <div className={styles.hero}>
        <div className={styles.heroMain}>
          <div className={styles.eyebrowRow}>
            <span
              style={{
                ...modeBadgeStyle,
                background:
                  client.mode === "real" ? "var(--dh-api-green-soft)" : "var(--dh-api-blue-soft)",
                color: client.mode === "real" ? "var(--dh-api-green)" : "var(--dh-api-blue)",
              }}
            >
              {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
            </span>
          </div>
          {/* 页面唯一 h1（可访问名 / 大纲）；字号由 .title 钉在原 level=2 的 24px，不随 h1 放大。 */}
          <Typography.Title level={1} className={styles.title} data-testid="cashflow-page-title">
            现金流预测
          </Typography.Title>
          <Typography.Paragraph className={styles.subtitle}>
            用同一报告日串起久期缺口、利率敏感度、月度现金流分桶和 12 个月到期资产。
          </Typography.Paragraph>
        </div>

        <div className={styles.datePanel}>
          <Typography.Text className={styles.filterLabel}>报告日</Typography.Text>
          <Select
            aria-label="cashflow-report-date"
            className={styles.dateSelect}
            placeholder={datesQuery.isLoading ? "加载日期..." : "选择报告日"}
            loading={datesQuery.isLoading}
            value={effectiveDate || undefined}
            options={dateOptions.map((d) => ({ value: d, label: d }))}
            onChange={(v) => setReportDate(v)}
            disabled={!dateOptions.length && !reportDate}
            getPopupContainer={(trigger) => trigger.parentElement ?? document.body}
          />
        </div>
      </div>

      <PageDataSection
        title=""
        state={sectionState}
        onRetry={() => {
          if (effectiveDate) {
            void projectionQuery.refetch();
          } else {
            void datesQuery.refetch();
          }
        }}
      >
        {projectionQuery.isLoading ? (
          <div className={styles.loadingState}>
            <Spin />
          </div>
        ) : projectionQuery.isError ? (
          <Alert type="error" message="加载现金流预测失败，请稍后重试。" showIcon />
        ) : vm ? (
          <div className={styles.contentStack}>
            <div
              data-testid="cashflow-conclusion"
              className={`${styles.decisionDeck} ${styles[`decisionDeck_${conclusion.tone}`]}`}
            >
              <div className={styles.decisionCopy}>
                <span className={styles.conclusionLabel}>{conclusion.title}</span>
                <h2>{conclusion.body}</h2>
                <p title="久期缺口来自 /api/cashflow-projection">{`报告日 ${vm.reportDate}`}</p>
              </div>
              <div className={styles.decisionMetric}>
                <span>{selectCashflowDurationGapTrendLabel(vm.kpis.durationGap)}</span>
                <strong className={deckGapToneClass}>{vm.kpis.durationGap.display}</strong>
              </div>
              <div className={styles.decisionFacts}>
                <div>
                  <span>资产久期</span>
                  <strong>{vm.kpis.assetDuration.display}</strong>
                </div>
                <div>
                  <span>负债久期</span>
                  <strong>{vm.kpis.liabilityDuration.display}</strong>
                </div>
                <div>
                  <span>1bp 敏感度</span>
                  <strong className={deckSensitivityToneClass}>{rateSensitivity1bpDisplay}</strong>
                </div>
              </div>
              {projectionRail.length ? (
                <div className={styles.rail} aria-label="24个月累计净现金流轨迹">
                  <div className={styles.railHeader}>
                    <span>24M 累计净现金流轨迹</span>
                    <span>亿元口径图表见下方</span>
                  </div>
                  <div className={styles.railBars}>
                    {projectionRail.map((point, index) => (
                      <span
                        key={`${point.label}-${index}`}
                        title={point.title}
                        className={`${styles.railBar} ${styles[`railBar_${point.tone}`]}`}
                        style={{ height: point.height }}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            {projectionMeta ? (
              <section className={styles.contractStatus} data-testid="cashflow-contract-status">
                <div className={styles.contractStatusTitle}>
                  候选指标 · PAGE-CFP-001 · 临时例外
                </div>
                <div className={styles.contractStatusGrid}>
                  <span>正式可用: {projectionMeta.formal_use_allowed ? "是" : "否"}</span>
                  <span>口径 {projectionMeta.basis}</span>
                  <span>质量 {projectionMeta.quality_flag}</span>
                  <span>结果类型 {projectionMeta.result_kind}</span>
                  <span>日期基准 {projectionMeta.date_basis ?? EM_DASH}</span>
                  <span>请求日 {projectionMeta.requested_report_date ?? EM_DASH}</span>
                  <span>解析日 {projectionMeta.resolved_report_date ?? EM_DASH}</span>
                  <span>数据截至日 {projectionMeta.as_of_date ?? EM_DASH}</span>
                  <span>回退 {projectionMeta.fallback_mode ?? EM_DASH}</span>
                  <span>回退日 {projectionMeta.fallback_date ?? EM_DASH}</span>
                  <span>使用表 {projectionMeta.tables_used?.join(", ") || EM_DASH}</span>
                  <span>证据行 {projectionMeta.evidence_rows ?? EM_DASH}</span>
                </div>
                <div
                  className={styles.contractStatusNote}
                  data-testid="cashflow-date-source-note"
                  title="报告日列表来源 /api/balance-analysis/dates"
                >
                  报告日取自资产负债分析可用日期；现金流桶按后端 date_basis 口径展示，前端不改数据逻辑。
                </div>
              </section>
            ) : null}

            <section className={styles.panel}>
              <SectionHead category="总览" title="现金流概览" numbered={false} />
              <div className={styles.metricStrip}>
                {kpis.map((item) => (
                  <div
                    key={item.key}
                    data-testid={item.testId}
                    className={`${styles.metricCell} ${styles[`metricCell_${item.priority}`]} ${
                      item.tone ? styles[`metricCell_${item.tone}`] : ""
                    }`}
                  >
                    <span>{item.title}</span>
                    <strong>{item.value.display}</strong>
                    <small>{item.detail}</small>
                  </div>
                ))}
              </div>
            </section>

            <section className={styles.projectionGrid}>
              <ChartCard
                testId="cashflow-monthly-chart"
                title="月度投影"
                question="24个月资产流入、负债流出和累计净现金流"
                unit="亿元"
                asOf={vm.reportDate}
                height={CHART_CARD_HEIGHTS.hero}
                legendRows={2}
                option={chartOption}
                emptyMessage="暂无分桶数据"
              />

              <aside
                className={`${styles.sidePanel} ${
                  riskReadout ? styles[`sidePanel_${riskReadout.tone}`] : ""
                }`}
                data-testid="cashflow-risk-readout"
              >
                {riskReadout ? (
                  <>
                    <div className={styles.riskHeader}>
                      <span>累计净流风险读数</span>
                      <strong>{riskReadout.summary}</strong>
                      <p>基于月度分桶的展示读数，不替代正式风险评级。</p>
                    </div>
                    <div className={styles.riskRows}>
                      <div className={styles.riskRow}>
                        <span>最弱累计月</span>
                        <strong>{riskReadout.worstCumulativeMonth}</strong>
                        <em title={riskReadout.worstCumulativeTitle ?? undefined}>
                          {riskReadout.worstCumulativeDisplay}
                        </em>
                      </div>
                      <div className={styles.riskRow}>
                        <span>最大负债流出</span>
                        <strong>{riskReadout.largestOutflowMonth}</strong>
                        <em title={riskReadout.largestOutflowTitle ?? undefined}>
                          {riskReadout.largestOutflowDisplay}
                        </em>
                      </div>
                      <div className={styles.riskRow}>
                        <span>期末累计净流</span>
                        <strong title={riskReadout.finalCumulativeTitle ?? undefined}>
                          {riskReadout.finalCumulativeDisplay}
                        </strong>
                        <em>
                          {riskReadout.negativeCumulativeMonths} 个负值月
                          {riskReadout.missingCumulativeMonths > 0
                            ? ` · ${riskReadout.missingCumulativeMonths} 个缺数月（未参与判定）`
                            : ""}
                        </em>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className={styles.riskEmpty}>暂无月度分桶，无法生成累计净流读数。</div>
                )}
              </aside>
            </section>

            <section className={styles.tablePanel}>
              <SectionHead
                category="到期"
                title="到期资产与提示"
                note="12 个月内到期资产按面值取前十，保留原始表格字段和金额展示。"
                numbered={false}
              />
              <DataTable<CashflowMaturingAssetVM>
                testId="cashflow-top-assets-table"
                rowKey="instrumentCode"
                rows={vm.topMaturingAssets}
                columns={TOP_MATURING_ASSETS_COLUMNS}
              />
            </section>

            {warningDisplays.length ? (
              <Alert
                type="warning"
                showIcon
                message="提示"
                description={
                  <div className={styles.warningBody}>
                    <ul className={styles.warningList}>
                      {warningDisplays.map((item) => (
                        <li key={item.original ?? item.summary}>{item.summary}</li>
                      ))}
                    </ul>
                    {warningOriginals.length ? (
                      <details
                        className={styles.warningOriginals}
                        data-testid="cashflow-warning-originals"
                      >
                        <summary>英文原文（{warningOriginals.length} 条）</summary>
                        <ul className={styles.warningList}>
                          {warningOriginals.map((original) => (
                            <li key={original}>{original}</li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </div>
                }
              />
            ) : null}
          </div>
        ) : null}
      </PageDataSection>
    </section>
  );
}
