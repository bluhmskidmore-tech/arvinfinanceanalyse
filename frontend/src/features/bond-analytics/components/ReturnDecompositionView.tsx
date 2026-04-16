import { useEffect, useMemo, useState } from "react";
import ReactECharts from "../../../lib/echarts";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import { useApiClient } from "../../../api/client";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  PeriodType,
  ReturnDecompositionResponse,
} from "../types";
import { formatWan } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

const WATERFALL_CATEGORIES = [
  "Carry",
  "Roll-down",
  "利率效应",
  "利差效应",
  "FX效应",
  "凸性效应",
  "交易",
  "合计",
] as const;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "rgba(0,0,0,0)",
  borderWidth: 0,
} as const;

function buildWaterfallOption(d: ReturnDecompositionResponse) {
  const carry = parseFloat(d.carry);
  const rollDown = parseFloat(d.roll_down);
  const rateEffect = parseFloat(d.rate_effect);
  const spreadEffect = parseFloat(d.spread_effect);
  const trading = parseFloat(d.trading);
  const fxEffect = parseFloat(d.fx_effect);
  const convexityEffect = parseFloat(d.convexity_effect);
  const explained = parseFloat(d.explained_pnl);

  const stepValues = [carry, rollDown, rateEffect, spreadEffect, fxEffect, convexityEffect, trading].map((v) =>
    Number.isFinite(v) ? v : 0,
  );

  const helperRaw: number[] = [];
  const valueRaw: number[] = [];
  const barColors: string[] = [];

  let running = 0;
  for (const v of stepValues) {
    if (v >= 0) {
      helperRaw.push(running);
      valueRaw.push(v);
      barColors.push("#cf1322");
      running += v;
    } else {
      helperRaw.push(running + v);
      valueRaw.push(-v);
      barColors.push("#3f8600");
      running += v;
    }
  }

  helperRaw.push(0);
  valueRaw.push(Number.isFinite(explained) ? explained : 0);
  barColors.push("#1f5eff");

  const displayStrings = [
    d.carry,
    d.roll_down,
    d.rate_effect,
    d.spread_effect,
    d.fx_effect,
    d.convexity_effect,
    d.trading,
    d.explained_pnl,
  ];

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((x: { seriesName?: string }) => x.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = WATERFALL_CATEGORIES[idx];
        return `${label}<br/>${formatWan(displayStrings[idx] ?? "0")}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32, containLabel: true },
    xAxis: {
      type: "category",
      data: [...WATERFALL_CATEGORIES],
      axisLabel: { interval: 0, rotate: 0 },
    },
    yAxis: { type: "value" },
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
  { title: "Carry（票息）", dataIndex: "carry", key: "carry", render: formatWan },
  { title: "Roll-down（骑乘）", dataIndex: "roll_down", key: "roll_down", render: formatWan },
  { title: "利率效应", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
  { title: "利差效应", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
  { title: "FX效应", dataIndex: "fx_effect", key: "fx_effect", render: formatWan },
  { title: "凸性效应", dataIndex: "convexity_effect", key: "convexity_effect", render: formatWan },
  { title: "交易", dataIndex: "trading", key: "trading", render: formatWan },
  { title: "合计", dataIndex: "total", key: "total", render: formatWan },
  { title: "债券数", dataIndex: "bond_count", key: "bond_count" },
];

export function ReturnDecompositionView({
  reportDate,
  periodType,
  assetClass = "all",
  accountingClass = "all",
}: Props) {
  const client = useApiClient();
  const [data, setData] = useState<ReturnDecompositionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const envelope =
          assetClass === "all" && accountingClass === "all"
            ? await client.getBondAnalyticsReturnDecomposition(reportDate, periodType)
            : await client.getBondAnalyticsReturnDecomposition(reportDate, periodType, {
                ...(assetClass !== "all" ? { assetClass } : {}),
                ...(accountingClass !== "all" ? { accountingClass } : {}),
              });
        if (!cancelled) setData(envelope.result);
      } catch (e: unknown) {
        if (!cancelled) setError((e as Error).message);
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

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  const effects = [
    { label: "Carry（票息）", value: data.carry },
    { label: "Roll-down（骑乘）", value: data.roll_down },
    { label: "利率效应", value: data.rate_effect },
    { label: "利差效应", value: data.spread_effect },
    { label: "FX效应", value: data.fx_effect },
    { label: "凸性效应", value: data.convexity_effect },
    { label: "交易", value: data.trading },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SectionLead
        eyebrow="Return Decomposition"
        title="收益分解概览"
        description="按报告日、期间和筛选条件读取后端收益分解 read model；页面只展示经济口径、会计口径与 OCI 影响，不在前端重算正式损益。"
        testId="return-decomposition-shell-lead"
      />
      <Row gutter={16}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="经济口径合计" value={formatWan(data.explained_pnl_economic || data.explained_pnl)} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="OCI 未入表影响" value={formatWan(data.oci_reserve_impact || "0")} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="会计口径（损益表）" value={formatWan(data.explained_pnl_accounting || data.explained_pnl)} />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="Effects"
        title="收益效果瀑布"
        description="Carry、Roll-down、利率、利差、FX、凸性和交易效果沿用后端返回字段，仅做图表化展示。"
        testId="return-decomposition-effects-lead"
      />
      <Card title="收益效应分解" size="small">
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {effects.map((e) => {
            const num = parseFloat(e.value);
            const color = num >= 0 ? "#cf1322" : "#3f8600";
            return (
              <div key={e.label} style={{ textAlign: "center", minWidth: 100 }}>
                <div style={{ fontSize: 12, color: "#8090a8" }}>{e.label}</div>
                <div style={{ fontSize: 18, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>
                  {formatWan(e.value)}
                </div>
              </div>
            );
          })}
        </div>
        {waterfallOption && (
          <div style={{ marginTop: 16 }}>
            <ReactECharts
              option={waterfallOption}
              style={{ height: 380, width: "100%" }}
              opts={{ renderer: "canvas" }}
            />
          </div>
        )}
      </Card>

      {data.by_asset_class && data.by_asset_class.length > 0 && (
        <Card title="按资产类别拆分" size="small">
          <Table
            dataSource={data.by_asset_class}
            columns={effectColumns}
            rowKey="asset_class"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      <SectionLead
        eyebrow="Reconciliation"
        title="收益分解对账"
        description="按资产类别拆分和对账残差保留原有后端语义，前端不调整解释损益、实际损益或残差。"
        testId="return-decomposition-recon-lead"
      />
      <Card title="损益对账" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="可解释损益" value={formatWan(data.explained_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic title="实际损益" value={formatWan(data.actual_pnl)} />
          </Col>
          <Col span={8}>
            <Statistic
              title="对账残差"
              value={formatWan(data.recon_error)}
              suffix={data.recon_error_pct ? `(${parseFloat(data.recon_error_pct).toFixed(2)}%)` : ""}
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
    </div>
  );
}
