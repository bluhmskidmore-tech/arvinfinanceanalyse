import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import type { PeriodType, ReturnDecompositionResponse } from "../types";
import { formatWan } from "../utils/formatters";

interface Props {
  reportDate: string;
  periodType: PeriodType;
}

const effectColumns = [
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class" },
  { title: "Carry（票息）", dataIndex: "carry", key: "carry", render: formatWan },
  { title: "Roll-down（骑乘）", dataIndex: "roll_down", key: "roll_down", render: formatWan },
  { title: "利率效应", dataIndex: "rate_effect", key: "rate_effect", render: formatWan },
  { title: "利差效应", dataIndex: "spread_effect", key: "spread_effect", render: formatWan },
  { title: "交易", dataIndex: "trading", key: "trading", render: formatWan },
  { title: "合计", dataIndex: "total", key: "total", render: formatWan },
  { title: "债券数", dataIndex: "bond_count", key: "bond_count" },
];

export function ReturnDecompositionView({ reportDate, periodType }: Props) {
  const [data, setData] = useState<ReturnDecompositionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          report_date: reportDate,
          period_type: periodType,
        });
        const res = await fetch(`/api/bond-analytics/return-decomposition?${params}`);
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
  }, [reportDate, periodType]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  const effects = [
    { label: "Carry（票息）", value: data.carry },
    { label: "Roll-down（骑乘）", value: data.roll_down },
    { label: "利率效应", value: data.rate_effect },
    { label: "利差效应", value: data.spread_effect },
    { label: "交易", value: data.trading },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
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
