import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Alert, Spin, Select, Space } from "antd";
import type { PeriodType, BenchmarkExcessResponse } from "../types";
import { formatBp } from "../utils/formatters";

interface Props {
  reportDate: string;
  periodType: PeriodType;
}

const BENCHMARK_OPTIONS = [
  { value: "TREASURY_INDEX", label: "中债国债总指数" },
  { value: "CDB_INDEX", label: "中债国开债总指数" },
  { value: "AAA_CREDIT_INDEX", label: "中债AAA信用债指数" },
];

export function BenchmarkExcessView({ reportDate, periodType }: Props) {
  const [data, setData] = useState<BenchmarkExcessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [benchmarkId, setBenchmarkId] = useState("CDB_INDEX");

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          report_date: reportDate,
          period_type: periodType,
          benchmark_id: benchmarkId,
        });
        const res = await fetch(`/api/bond-analytics/benchmark-excess?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json.result);
      } catch (e: unknown) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (reportDate) fetchData();
    return () => { cancelled = true; };
  }, [reportDate, periodType, benchmarkId]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  const excessNum = parseFloat(data.excess_return);
  const excessColor = excessNum >= 0 ? "#cf1322" : "#3f8600";

  const decomp = [
    { label: "久期效应", value: data.duration_effect },
    { label: "曲线效应", value: data.curve_effect },
    { label: "利差效应", value: data.spread_effect },
    { label: "选券效应", value: data.selection_effect },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Space>
          <span style={{ color: "#5c6b82", fontSize: 13 }}>基准</span>
          <Select
            value={benchmarkId}
            onChange={setBenchmarkId}
            options={BENCHMARK_OPTIONS}
            style={{ width: 200 }}
            size="small"
          />
        </Space>
      </div>

      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="组合收益率" value={formatBp(data.portfolio_return)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="基准收益率" value={formatBp(data.benchmark_return)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="超额收益"
              value={formatBp(data.excess_return)}
              valueStyle={{ color: excessColor }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="久期偏离"
              value={parseFloat(data.duration_diff).toFixed(2)}
            />
          </Card>
        </Col>
      </Row>

      <Card title="超额收益分解" size="small">
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          {decomp.map((d) => {
            const num = parseFloat(d.value);
            const color = num >= 0 ? "#cf1322" : "#3f8600";
            return (
              <div key={d.label} style={{ textAlign: "center", minWidth: 100 }}>
                <div style={{ fontSize: 12, color: "#8090a8" }}>{d.label}</div>
                <div style={{ fontSize: 18, fontWeight: 600, color, fontVariantNumeric: "tabular-nums" }}>
                  {formatBp(d.value)}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {data.excess_sources && data.excess_sources.length > 0 && (
        <Card title="超额来源明细" size="small">
          {data.excess_sources.map((s) => (
            <div key={s.source} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
              <span>{s.source}</span>
              <span style={{ fontVariantNumeric: "tabular-nums" }}>{formatBp(s.contribution)}</span>
            </div>
          ))}
        </Card>
      )}

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
