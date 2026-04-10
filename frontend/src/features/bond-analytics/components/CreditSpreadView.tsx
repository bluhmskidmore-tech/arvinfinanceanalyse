import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Table, Alert, Spin } from "antd";
import type { CreditSpreadMigrationResponse } from "../types";
import { formatWan, formatBp } from "../utils/formatters";

interface Props {
  reportDate: string;
}

const spreadColumns = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  { title: "利差变动 (bp)", dataIndex: "spread_change_bp", key: "spread_change_bp" },
  { title: "总影响", dataIndex: "pnl_impact", key: "pnl_impact", render: formatWan },
  { title: "OCI影响", dataIndex: "oci_impact", key: "oci_impact", render: formatWan },
  { title: "TPL影响", dataIndex: "tpl_impact", key: "tpl_impact", render: formatWan },
];

const migrationColumns = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  { title: "原评级", dataIndex: "from_rating", key: "from_rating" },
  { title: "目标评级", dataIndex: "to_rating", key: "to_rating" },
  { title: "涉及债券", dataIndex: "affected_bonds", key: "affected_bonds" },
  { title: "涉及市值", dataIndex: "affected_market_value", key: "affected_market_value", render: formatWan },
  { title: "损益影响", dataIndex: "pnl_impact", key: "pnl_impact", render: formatWan },
];

export function CreditSpreadView({ reportDate }: Props) {
  const [data, setData] = useState<CreditSpreadMigrationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ report_date: reportDate });
        const res = await fetch(`/api/bond-analytics/credit-spread-migration?${params}`);
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
            <Statistic title="信用债数量" value={data.credit_bond_count} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="信用债市值"
              value={formatWan(data.credit_market_value)}
              suffix={`(${(parseFloat(data.credit_weight) * 100).toFixed(1)}%)`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="Spread DV01 (万元/bp)" value={formatWan(data.spread_dv01)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="加权平均利差" value={formatBp(data.weighted_avg_spread)} />
          </Card>
        </Col>
      </Row>

      <Card title="OCI敏感度" size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="OCI信用债敞口" value={formatWan(data.oci_credit_exposure)} />
          </Col>
          <Col span={8}>
            <Statistic title="OCI Spread DV01" value={formatWan(data.oci_spread_dv01)} />
          </Col>
          <Col span={8}>
            <Statistic title="利差走阔25bp影响" value={formatWan(data.oci_sensitivity_25bp)} />
          </Col>
        </Row>
      </Card>

      {data.spread_scenarios.length > 0 && (
        <Card title="利差情景冲击" size="small">
          <Table
            dataSource={data.spread_scenarios}
            columns={spreadColumns}
            rowKey="scenario_name"
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {data.migration_scenarios.length > 0 && (
        <Card title="评级迁徙情景" size="small">
          <Table
            dataSource={data.migration_scenarios}
            columns={migrationColumns}
            rowKey="scenario_name"
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
