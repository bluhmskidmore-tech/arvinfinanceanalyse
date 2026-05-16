import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Select, Spin, Table, Typography } from "antd";

import type { Numeric } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { DataSection } from "../../../components/DataSection";
import type { DataSectionState } from "../../../components/DataSection.types";
import { modeBadgeStyle } from "../../../components/page/pageStyles";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";
import { displayTokens } from "../../../theme/displayTokens";
import { adaptCashflowProjection } from "../adapters/cashflowProjectionAdapter";
import { selectCashflowMonthlyProjectionSeries } from "./cashflowProjectionPageModel";
import styles from "./CashflowProjectionPage.module.css";

type ConclusionTone = "positive" | "negative" | "neutral" | "pending";

type Conclusion = {
  title: string;
  body: string;
  tone: ConclusionTone;
};

type KpiSpec = {
  key: string;
  testId: string;
  title: string;
  value: Numeric;
  detail: string;
  tone?: "default" | "positive" | "negative" | "warning";
};

type RailPoint = {
  label: string;
  height: number;
  tone: "positive" | "negative" | "neutral";
};

function buildConclusion(durationGap: Numeric | undefined): Conclusion {
  const raw = durationGap?.raw;
  if (raw === null || raw === undefined) {
    return {
      title: "当前结论",
      body: "久期缺口待确认，先核对报告日与上游现金流分桶是否齐备。",
      tone: "pending",
    };
  }
  if (raw > 0.05) {
    return {
      title: "当前结论",
      body: "资产久期长于负债，当前为正久期缺口。",
      tone: "positive",
    };
  }
  if (raw < -0.05) {
    return {
      title: "当前结论",
      body: "负债久期长于资产，当前为负久期缺口。",
      tone: "negative",
    };
  }
  return {
    title: "当前结论",
    body: "资产与负债久期基本匹配，缺口已收敛到接近平衡区间。",
    tone: "neutral",
  };
}

function trendLabel(value: Numeric | undefined): string {
  const raw = value?.raw;
  if (raw === null || raw === undefined) return "待确认";
  if (raw > 0) return "正缺口";
  if (raw < 0) return "负缺口";
  return "接近平衡";
}

function toYi(raw: number): number {
  return raw / 100_000_000;
}

function axisYiLabel(value: number): string {
  if (!Number.isFinite(value)) return "";
  return `${toYi(value).toFixed(1)}亿`;
}

function tooltipYi(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return `${toYi(value).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿`;
}

function buildProjectionRail(
  monthlySeries: ReturnType<typeof selectCashflowMonthlyProjectionSeries>,
): RailPoint[] {
  if (!monthlySeries) return [];
  const values = monthlySeries.cumulativeNet.slice(0, 24);
  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  return values.map((value, index) => ({
    label: monthlySeries.categories[index] ?? "",
    height: Math.max(10, Math.round((Math.abs(value) / maxAbs) * 42)),
    tone: value > 0 ? "positive" : value < 0 ? "negative" : "neutral",
  }));
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
  const conclusion = buildConclusion(vm?.kpis.durationGap);
  const monthlySeries = useMemo(() => selectCashflowMonthlyProjectionSeries(vm), [vm]);
  const projectionRail = useMemo(() => buildProjectionRail(monthlySeries), [monthlySeries]);
  const kpis = useMemo<KpiSpec[]>(() => {
    if (!vm) return [];
    return [
      {
        key: "duration-gap",
        testId: "cashflow-kpi-duration-gap",
        title: "久期缺口（年）",
        value: vm.kpis.durationGap,
        detail: "资产久期 - 负债久期",
        tone:
          vm.kpis.durationGap.raw === null || vm.kpis.durationGap.raw === undefined
            ? "warning"
            : vm.kpis.durationGap.raw < 0
              ? "negative"
              : "positive",
      },
      {
        key: "asset-duration",
        testId: "cashflow-kpi-asset-dur",
        title: "资产久期（年）",
        value: vm.kpis.assetDuration,
        detail: "资产侧久期",
      },
      {
        key: "liability-duration",
        testId: "cashflow-kpi-liability-dur",
        title: "负债久期（年）",
        value: vm.kpis.liabilityDuration,
        detail: "负债侧久期",
      },
      {
        key: "dv01",
        testId: "cashflow-kpi-dv01",
        title: "1bp 敏感度",
        value: vm.kpis.rateSensitivity1bp,
        detail: "利率敏感度",
      },
      {
        key: "equity-duration",
        testId: "cashflow-kpi-equity-dur",
        title: "权益久期（年）",
        value: vm.kpis.equityDuration,
        detail: "权益侧久期",
      },
      {
        key: "reinvest-risk",
        testId: "cashflow-kpi-reinvest",
        title: "再投资风险（12M）",
        value: vm.kpis.reinvestmentRisk12m,
        detail: "12 个月再投资风险",
        tone: "warning",
      },
    ];
  }, [vm]);

  const chartOption = useMemo((): EChartsOption | null => {
    if (!monthlySeries) {
      return null;
    }
    return {
      color: ["#2d8a5e", "#dc2626", "#1850a1"],
      animationDuration: 420,
      grid: { left: 64, right: 24, top: 54, bottom: 50 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value) => tooltipYi(Number(value)),
      },
      legend: {
        top: 8,
        right: 8,
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: designTokens.color.neutral[600], fontSize: 12 },
        data: ["资产流入", "负债流出", "累计净现金流"],
      },
      xAxis: {
        type: "category",
        data: monthlySeries.categories,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: designTokens.color.neutral[200] } },
        axisLabel: { color: designTokens.color.neutral[500], rotate: 30 },
      },
      yAxis: [
        {
          type: "value",
          name: "当月流量",
          nameTextStyle: { color: designTokens.color.neutral[500] },
          axisLabel: { color: designTokens.color.neutral[500], formatter: axisYiLabel },
          splitLine: { lineStyle: { color: designTokens.color.neutral[100] } },
        },
        {
          type: "value",
          name: "累计",
          nameTextStyle: { color: designTokens.color.neutral[500] },
          axisLabel: { color: designTokens.color.neutral[500], formatter: axisYiLabel },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "资产流入",
          type: "bar",
          data: monthlySeries.assetInflow,
          barMaxWidth: 22,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
        },
        {
          name: "负债流出",
          type: "bar",
          data: monthlySeries.liabilityOutflow,
          barMaxWidth: 22,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
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
    <section data-testid="cashflow-projection-page" className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroMain}>
          <div className={styles.eyebrowRow}>
            <span className={styles.eyebrow}>Cashflow projection</span>
            <span
              style={{
                ...modeBadgeStyle,
                background:
                  client.mode === "real" ? designTokens.color.success[50] : designTokens.color.primary[50],
                color:
                  client.mode === "real"
                    ? displayTokens.apiMode.realForeground
                    : displayTokens.apiMode.mockForeground,
              }}
            >
              {client.mode === "real" ? "真实只读链路" : "本地演示数据"}
            </span>
          </div>
          <Typography.Title level={2} className={styles.title} data-testid="cashflow-page-title">
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
          />
        </div>
      </div>

      <DataSection
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
                <p>{`报告日 ${vm.reportDate} · 久期缺口来自 /api/cashflow-projection`}</p>
              </div>
              <div className={styles.decisionMetric}>
                <span>{trendLabel(vm.kpis.durationGap)}</span>
                <strong>{vm.kpis.durationGap.display}</strong>
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
                  <strong>{vm.kpis.rateSensitivity1bp.display}</strong>
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
                        title={point.label}
                        className={`${styles.railBar} ${styles[`railBar_${point.tone}`]}`}
                        style={{ height: point.height }}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            <section className={styles.panel}>
              <div className={styles.sectionHeader}>
                <div>
                  <span className={styles.sectionEyebrow}>总览</span>
                  <h2>现金流概览</h2>
                </div>
                <p>核心缺口已经在首屏抬高；这里保留完整 KPI 便于复核。</p>
              </div>
              <div className={styles.metricStrip}>
                {kpis.map((item) => (
                  <div
                    key={item.key}
                    data-testid={item.testId}
                    className={`${styles.metricCell} ${item.tone ? styles[`metricCell_${item.tone}`] : ""}`}
                  >
                    <span>{item.title}</span>
                    <strong>{item.value.display}</strong>
                    <small>{item.detail}</small>
                  </div>
                ))}
              </div>
            </section>

            <section className={styles.projectionGrid}>
              <div className={styles.chartPanel} data-testid="cashflow-monthly-chart">
                <div className={styles.sectionHeader}>
                  <div>
                    <span className={styles.sectionEyebrow}>预测</span>
                    <h2>月度投影</h2>
                  </div>
                  <p>24 个月资产流入、负债流出和累计净现金流，单位按亿元显示。</p>
                </div>
                {chartOption ? (
                  <ReactECharts option={chartOption} className={styles.chart} />
                ) : (
                  <div className={styles.emptyChart}>暂无分桶数据</div>
                )}
              </div>

              <aside className={styles.sidePanel}>
                <div className={styles.sideMetric}>
                  <span>权益久期（年）</span>
                  <strong>{vm.kpis.equityDuration.display}</strong>
                  <p>权益侧久期</p>
                </div>
                <div className={styles.sideMetric}>
                  <span>再投资风险（12M）</span>
                  <strong>{vm.kpis.reinvestmentRisk12m.display}</strong>
                  <p>12 个月再投资风险</p>
                </div>
                <div className={styles.sideNote}>
                  指标定义仍以现金流预测接口返回为准，本页只调整展示层级。
                </div>
              </aside>
            </section>

            <section className={styles.tablePanel}>
              <div className={styles.sectionHeader}>
                <div>
                  <span className={styles.sectionEyebrow}>到期</span>
                  <h2>到期资产与提示</h2>
                </div>
                <p>12 个月内前十到期资产，保留原始表格字段和金额展示。</p>
              </div>
              <Table
                data-testid="cashflow-top-assets-table"
                size="small"
                pagination={false}
                rowKey={(r) => r.instrumentCode}
                dataSource={vm.topMaturingAssets}
                scroll={{ x: 760 }}
                columns={[
                  { title: "代码", dataIndex: "instrumentCode" },
                  { title: "名称", dataIndex: "instrumentName" },
                  { title: "到期日", dataIndex: "maturityDate" },
                  {
                    title: "面值",
                    dataIndex: "faceValue",
                    align: "right" as const,
                    render: (v: Numeric) => v.display,
                  },
                  {
                    title: "市值",
                    dataIndex: "marketValue",
                    align: "right" as const,
                    render: (v: Numeric) => v.display,
                  },
                ]}
              />
            </section>

            {vm.warnings?.length ? (
              <Alert
                type="warning"
                showIcon
                message="提示"
                description={
                  <ul className={styles.warningList}>
                    {vm.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                }
              />
            ) : null}
          </div>
        ) : null}
      </DataSection>
    </section>
  );
}
