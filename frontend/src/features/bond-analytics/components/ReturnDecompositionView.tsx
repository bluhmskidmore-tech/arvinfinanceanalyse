import { useEffect, useMemo, useState } from "react";
import ReactECharts from "../../../lib/echarts";
import { Card, Statistic, Row, Col, Table, Alert, Spin, Collapse } from "antd";
import { useApiClient } from "../../../api/client";
import type { ResultMeta } from "../../../api/contracts";
import { FormalResultMetaPanel } from "../../../components/page/FormalResultMetaPanel";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  PeriodType,
  ReturnDecompositionResponse,
} from "../types";
import {
  bondNumericRaw,
  returnDecompositionWaterfallDisplayStrings,
  returnDecompositionWaterfallRawSteps,
} from "../adapters/bondAnalyticsAdapter";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { formatWan, formatYi } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

const CN_MARKET_UP = designTokens.color.danger[500];
const CN_MARKET_DOWN = designTokens.color.success[600];
const CHART_ACCENT = designTokens.color.info[500];
const CHART_AXIS = { color: designTokens.color.neutral[700], fontSize: designTokens.fontSize[11] };

const WATERFALL_CATEGORIES = [
  "票息",
  "骑乘",
  "利率效应",
  "利差效应",
  "外汇效应",
  "凸性",
  "交易",
  "合计",
] as const;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "rgba(0,0,0,0)",
  borderWidth: 0,
} as const;

function describeMetaIssues(meta: ResultMeta | null): string[] {
  if (!meta) return [];
  const issues: string[] = [];
  if (meta.quality_flag !== "ok") issues.push(`质量标记=${meta.quality_flag}`);
  if (meta.vendor_status !== "ok") issues.push(`供应商状态=${meta.vendor_status}`);
  if (meta.fallback_mode !== "none") issues.push(`降级模式=${meta.fallback_mode}`);
  return issues;
}

function buildWaterfallOption(d: ReturnDecompositionResponse) {
  const rawSteps = returnDecompositionWaterfallRawSteps(d);
  const stepValues = rawSteps.slice(0, -1);
  const explained = rawSteps[rawSteps.length - 1] ?? 0;

  const helperRaw: number[] = [];
  const valueRaw: number[] = [];
  const barColors: string[] = [];

  let running = 0;
  for (const v of stepValues) {
    if (v >= 0) {
      helperRaw.push(running);
      valueRaw.push(v);
      barColors.push(CN_MARKET_UP);
      running += v;
    } else {
      helperRaw.push(running + v);
      valueRaw.push(-v);
      barColors.push(CN_MARKET_DOWN);
      running += v;
    }
  }

  helperRaw.push(0);
  valueRaw.push(Number.isFinite(explained) ? explained : 0);
  barColors.push(CHART_ACCENT);

  const displayStrings = returnDecompositionWaterfallDisplayStrings(d);

  return {
    backgroundColor: "transparent",
    textStyle: { color: designTokens.color.neutral[700] },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((x: { seriesName?: string }) => x.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = WATERFALL_CATEGORIES[idx];
        return `${label}<br/>${displayStrings[idx] ?? "-"}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32, containLabel: true },
    xAxis: {
      type: "category",
      data: [...WATERFALL_CATEGORIES],
      axisLabel: { interval: 0, rotate: 0, ...CHART_AXIS },
      axisLine: { lineStyle: { color: designTokens.color.neutral[200] } },
    },
    yAxis: {
      type: "value",
      axisLabel: CHART_AXIS,
      splitLine: { lineStyle: { color: designTokens.color.neutral[200], type: "dashed" } },
    },
    series: [
      {
        name: "辅助",
        type: "bar",
        stack: "waterfall",
        silent: true,
        itemStyle: TRANSPARENT_BAR,
        emphasis: { itemStyle: TRANSPARENT_BAR },
        data: helperRaw,
      },
      {
        name: "效应",
        type: "bar",
        stack: "waterfall",
        data: valueRaw.map((val, i) => ({
          value: val,
          itemStyle: { color: barColors[i] },
        })),
      },
    ],
  };
}

interface Props {
  reportDate: string;
  periodType: PeriodType;
  assetClass?: BondAnalyticsAssetClassFilter;
  accountingClass?: BondAnalyticsAccountingClassFilter;
}

const effectColumns = [
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "票息", dataIndex: "carry", key: "carry", render: formatWan },
  { title: "骑乘", dataIndex: "roll_down", key: "roll_down", render: formatWan },
  { title: "利率效应", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
  { title: "利差效应", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
  {
    title: "凸性",
    dataIndex: "convexity_effect",
    key: "convexity_effect",
    render: (v: ReturnDecompositionResponse["by_asset_class"][number]["convexity_effect"]) =>
      v ? formatWan(v) : "-",
  },
  { title: "交易", dataIndex: "trading", key: "trading", render: formatWan },
  { title: "合计", dataIndex: "total", key: "total", render: formatWan },
  { title: "债券只数", dataIndex: "bond_count", key: "bond_count" },
];

const accountingClassEffectColumns = effectColumns.map((col, i) =>
  i === 0 ? { ...col, title: "会计分类", key: "accounting_slice" } : col,
);

const bondDetailColumns = [
  { title: "债券代码", dataIndex: "bond_code", key: "bond_code" },
  {
    title: "债券名称",
    dataIndex: "bond_name",
    key: "bond_name",
    render: (v: string | null) => v ?? "-",
  },
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "会计分类", dataIndex: "accounting_class", key: "accounting_class" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatYi },
  { title: "票息", dataIndex: "carry", key: "carry", render: formatWan },
  { title: "骑乘", dataIndex: "roll_down", key: "roll_down", render: formatWan },
  { title: "利率效应", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
  { title: "利差效应", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
  {
    title: "凸性",
    dataIndex: "convexity_effect",
    key: "convexity_effect",
    render: (v: ReturnDecompositionResponse["bond_details"][number]["convexity_effect"]) =>
      v ? formatWan(v) : "-",
  },
  { title: "交易", dataIndex: "trading", key: "trading", render: formatWan },
  { title: "合计", dataIndex: "total", key: "total", render: formatWan },
  {
    title: "解释项（对账）",
    dataIndex: "explained_for_recon",
    key: "explained_for_recon",
    render: formatWan,
  },
  {
    title: "仅经济口径效应",
    dataIndex: "economic_only_effects",
    key: "economic_only_effects",
    render: formatWan,
  },
];

export function ReturnDecompositionView({
  reportDate,
  periodType,
  assetClass = "all",
  accountingClass = "all",
}: Props) {
  const client = useApiClient();
  const [data, setData] = useState<ReturnDecompositionResponse | null>(null);
  const [meta, setMeta] = useState<ResultMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      setMeta(null);
      try {
        const envelope =
          assetClass === "all" && accountingClass === "all"
            ? await client.getBondAnalyticsReturnDecomposition(reportDate, periodType)
            : await client.getBondAnalyticsReturnDecomposition(reportDate, periodType, {
                ...(assetClass !== "all" ? { assetClass } : {}),
                ...(accountingClass !== "all" ? { accountingClass } : {}),
              });
        if (!cancelled) {
          setData(envelope.result);
          setMeta(envelope.result_meta);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError((e as Error).message);
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (reportDate) fetchData();
    return () => {
      cancelled = true;
    };
  }, [accountingClass, assetClass, client, periodType, reportDate]);

  const waterfallOption = useMemo(
    () => (data ? buildWaterfallOption(data) : null),
    [data],
  );

  if (loading) return <Spin style={{ display: "block", margin: `${designTokens.space[8]}px auto` }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  const metaIssues = describeMetaIssues(meta);
  const periodLabel = `${data.period_type} · ${data.period_start} 至 ${data.period_end}`;

  const effects = [
    { label: "票息", value: data.carry },
    { label: "骑乘", value: data.roll_down },
    { label: "利率效应", value: data.rate_effect },
    { label: "利差效应", value: data.spread_effect },
    { label: "外汇效应", value: data.fx_effect },
    { label: "凸性", value: data.convexity_effect },
    { label: "交易", value: data.trading },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: designTokens.space[4] }}>
      <SectionLead
        eyebrow="收益分解"
        title="收益分解概览"
        description="读取治理后的收益分解结果，展示经济、会计和 OCI 影响，不在前端重复计算。"
        testId="return-decomposition-shell-lead"
      />
      <Card size="small" title="报告期间" data-testid="return-decomposition-period">
        <div style={{ fontSize: designTokens.fontSize[13], color: designTokens.color.neutral[700] }}>{periodLabel}</div>
        {data.computed_at ? (
          <div
            style={{
              fontSize: designTokens.fontSize[12],
              color: designTokens.color.neutral[600],
              marginTop: designTokens.space[2],
            }}
            data-testid="return-decomposition-computed-at"
          >
            {data.computed_at}
          </div>
        ) : null}
      </Card>
      {metaIssues.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          message="证据链降级"
          description={metaIssues.join(" | ")}
          data-testid="return-decomposition-result-meta-alert"
        />
      ) : null}
      <Row gutter={16}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="经济口径合计" value={formatWan(data.explained_pnl_economic ?? data.explained_pnl)} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="OCI 储备影响" value={formatWan(data.oci_reserve_impact)} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="会计损益" value={formatWan(data.explained_pnl_accounting ?? data.explained_pnl)} />
          </Card>
        </Col>
      </Row>
      <Row gutter={16}>
        <Col span={12}>
          <Card size="small" data-testid="return-decomposition-bond-count">
            <Statistic title="债券只数（顶层）" value={data.bond_count} />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" data-testid="return-decomposition-total-mv">
            <Statistic title="总市值" value={formatYi(data.total_market_value)} />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="效应"
        title="收益效应瀑布"
        description="按后端结果展示票息、骑乘、利率、利差、外汇、凸性和交易效应。"
        testId="return-decomposition-effects-lead"
      />
      <Card title="收益效应分解" size="small">
        <div style={{ display: "flex", gap: designTokens.space[3], flexWrap: "wrap" }}>
          {effects.map((e) => {
            const num = bondNumericRaw(e.value);
            const color = num >= 0 ? CN_MARKET_UP : CN_MARKET_DOWN;
            return (
              <div key={e.label} style={{ textAlign: "center", minWidth: 100 }}>
                <div style={{ fontSize: designTokens.fontSize[12], color: designTokens.color.neutral[600] }}>{e.label}</div>
                <div style={{ fontSize: designTokens.fontSize[18], fontWeight: 600, color, ...tabularNumsStyle }}>
                  {formatWan(e.value)}
                </div>
              </div>
            );
          })}
        </div>
        {waterfallOption && (
          <div style={{ marginTop: designTokens.space[4] }}>
            <ReactECharts
              option={waterfallOption}
              style={{ height: 380, width: "100%" }}
              opts={{ renderer: "canvas" }}
            />
          </div>
        )}
      </Card>

      {data.by_asset_class && data.by_asset_class.length > 0 && (
        <Card title="按资产类别" size="small">
          <Table
            dataSource={data.by_asset_class}
            columns={effectColumns}
            rowKey="asset_class"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {data.by_accounting_class && data.by_accounting_class.length > 0 && (
        <Card title="按会计分类" size="small" data-testid="return-decomposition-by-accounting-class">
          <Table
            dataSource={data.by_accounting_class}
            columns={accountingClassEffectColumns}
            rowKey={(row) => `${row.asset_class}`}
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {data.bond_details && data.bond_details.length > 0 && (
        <Collapse
          bordered={false}
          data-testid="return-decomposition-bond-details-collapse"
          items={[
            {
              key: "bond-details",
              label: "券级拆解（按券明细）",
              children: (
                <Table
                  data-testid="return-decomposition-bond-details-table"
                  dataSource={data.bond_details}
                  columns={bondDetailColumns}
                  rowKey={(row) => row.bond_code}
                  pagination={false}
                  size="small"
                  scroll={{ x: "max-content" }}
                />
              ),
            },
          ]}
        />
      )}
      <SectionLead
        eyebrow="对账"
        title="收益分解对账"
        description="保持对账合计与残差遵循后端语义，不在前端做调整。"
        testId="return-decomposition-recon-lead"
      />
      <Card title="损益对账" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="解释损益" value={formatWan(data.explained_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic title="实际损益" value={formatWan(data.actual_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic
              title="对账差异"
              value={formatWan(data.recon_error)}
              suffix={data.recon_error_pct ? `(${data.recon_error_pct.display})` : ""}
            />
          </Col>
        </Row>
      </Card>

      {data.warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message="提示"
          description={data.warnings.map((w, i) => <div key={i}>{w}</div>)}
        />
      )}
      <FormalResultMetaPanel
        testId="return-decomposition-result-meta"
        title="收益分解证据"
        sections={[
          {
            key: "return-decomposition",
            title: "收益分解",
            meta,
          },
        ]}
      />
    </div>
  );
}
