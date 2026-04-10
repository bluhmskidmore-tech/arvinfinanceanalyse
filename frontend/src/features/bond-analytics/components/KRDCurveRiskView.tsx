import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import type { KRDCurveRiskResponse } from "../types";
import { formatWan } from "../utils/formatters";

interface Props {
  reportDate: string;
}

const scenarioColumns = [
  { title: "情景", dataIndex: "scenario_description", key: "scenario_description" },
  { title: "经济口径影响", dataIndex: "pnl_economic", key: "pnl_economic", render: formatWan },
  { title: "OCI影响", dataIndex: "pnl_oci", key: "pnl_oci", render: formatWan },
  { title: "TPL影响", dataIndex: "pnl_tpl", key: "pnl_tpl", render: formatWan },
];

const assetClassColumns = [
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "市值", dataIndex: "market_value", key: "market_value", render: formatWan },
  { title: "久期", dataIndex: "duration", key: "duration" },
  { title: "DV01", dataIndex: "dv01", key: "dv01", render: formatWan },
  { title: "权重", dataIndex: "weight", key: "weight" },
];

export function KRDCurveRiskView({ reportDate }: Props) {
  const [data, setData] = useState<KRDCurveRiskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ report_date: reportDate });
        const res = await fetch(`/api/bond-analytics/krd-curve-risk?${params}`);
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
  }, [reportDate]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="组合久期" value={parseFloat(data.portfolio_duration).toFixed(2)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="修正久期" value={parseFloat(data.portfolio_modified_duration).toFixed(2)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="DV01 (万元/bp)" value={formatWan(data.portfolio_dv01)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="凸性" value={parseFloat(data.portfolio_convexity).toFixed(2)} />
          </Card>
        </Col>
      </Row>

      {data.krd_buckets.length > 0 && (
        <Card title="KRD 分布" size="small">
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 160, padding: "0 8px" }}>
            {data.krd_buckets.map((b) => {
              const krd = parseFloat(b.krd);
              const maxKrd = Math.max(...data.krd_buckets.map((x) => Math.abs(parseFloat(x.krd))), 0.01);
              const height = Math.max((Math.abs(krd) / maxKrd) * 120, 4);
              return (
                <div key={b.tenor} style={{ flex: 1, textAlign: "center" }}>
                  <div
                    style={{
                      height,
                      background: krd >= 0 ? "#1f5eff" : "#ff4d4f",
                      borderRadius: 4,
                      marginBottom: 4,
                    }}
                  />
                  <div style={{ fontSize: 11, color: "#5c6b82" }}>{b.tenor}</div>
                  <div style={{ fontSize: 11, fontVariantNumeric: "tabular-nums" }}>{krd.toFixed(3)}</div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {data.scenarios.length > 0 && (
        <Card title="情景冲击" size="small">
          <Table
            dataSource={data.scenarios}
            columns={scenarioColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {data.by_asset_class.length > 0 && (
        <Card title="按资产类别拆分" size="small">
          <Table
            dataSource={data.by_asset_class}
            columns={assetClassColumns}
            rowKey="asset_class"
            pagination={false}
            size="small"
          />
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
