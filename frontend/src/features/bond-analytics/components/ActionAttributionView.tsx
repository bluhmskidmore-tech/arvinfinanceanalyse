import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Table, Tag, Alert, Spin } from "antd";
import { useApiClient } from "../../../api/client";
import type { PeriodType, ActionAttributionResponse } from "../types";
import { ACTION_TYPE_NAMES } from "../types";
import { formatWan } from "../utils/formatters";

interface Props {
  reportDate: string;
  periodType: PeriodType;
}

const ACTION_COLORS: Record<string, string> = {
  ADD_DURATION: "#1890ff",
  REDUCE_DURATION: "#faad14",
  SWITCH: "#722ed1",
  CREDIT_DOWN: "#eb2f96",
  CREDIT_UP: "#52c41a",
  TIMING_BUY: "#13c2c2",
  TIMING_SELL: "#fa541c",
  HEDGE: "#8c8c8c",
};

const detailColumns = [
  { title: "日期", dataIndex: "action_date", key: "action_date", width: 100 },
  {
    title: "类型",
    dataIndex: "action_type",
    key: "action_type",
    width: 100,
    render: (type: string) => (
      <Tag color={ACTION_COLORS[type] || "default"}>
        {ACTION_TYPE_NAMES[type] || type}
      </Tag>
    ),
  },
  { title: "描述", dataIndex: "description", key: "description", ellipsis: true },
  {
    title: "损益贡献",
    dataIndex: "pnl_economic",
    key: "pnl_economic",
    width: 120,
    render: (v: string) => {
      const num = parseFloat(v);
      const color = num >= 0 ? "#cf1322" : "#3f8600";
      return <span style={{ color, fontVariantNumeric: "tabular-nums" }}>{formatWan(v)}</span>;
    },
  },
  {
    title: "Δ久期",
    dataIndex: "delta_duration",
    key: "delta_duration",
    width: 80,
    render: (v: string) => parseFloat(v).toFixed(4),
  },
];

export function ActionAttributionView({ reportDate, periodType }: Props) {
  const client = useApiClient();
  const [data, setData] = useState<ActionAttributionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const envelope = await client.getBondAnalyticsActionAttribution(reportDate, periodType);
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
  }, [client, reportDate, periodType]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="动作数量" value={data.total_actions} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="动作贡献损益" value={formatWan(data.total_pnl_from_actions)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="久期变化"
              value={`${parseFloat(data.period_start_duration).toFixed(2)} → ${parseFloat(data.period_end_duration).toFixed(2)}`}
              suffix={`Δ ${parseFloat(data.duration_change_from_actions).toFixed(2)}`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="DV01变化"
              value={`${formatWan(data.period_start_dv01)} → ${formatWan(data.period_end_dv01)}`}
            />
          </Card>
        </Col>
      </Row>

      {data.by_action_type.length > 0 && (
        <Card title="按动作类型汇总" size="small">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.by_action_type.map((item) => {
              const pnl = parseFloat(item.total_pnl_economic);
              const totalPnl = parseFloat(data.total_pnl_from_actions);
              const pct = totalPnl !== 0 ? (pnl / totalPnl) * 100 : 0;
              return (
                <div key={item.action_type} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <Tag color={ACTION_COLORS[item.action_type] || "default"} style={{ width: 80, textAlign: "center" }}>
                    {item.action_type_name}
                  </Tag>
                  <span style={{ width: 50, textAlign: "right", fontSize: 12, color: "#5c6b82" }}>
                    {item.action_count}次
                  </span>
                  <div style={{ flex: 1, height: 20, background: "#f0f0f0", borderRadius: 4, overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(Math.abs(pct), 100)}%`,
                        background: ACTION_COLORS[item.action_type] || "#8c8c8c",
                        borderRadius: 4,
                      }}
                    />
                  </div>
                  <span
                    style={{
                      width: 100,
                      textAlign: "right",
                      fontVariantNumeric: "tabular-nums",
                      color: pnl >= 0 ? "#cf1322" : "#3f8600",
                      fontSize: 13,
                    }}
                  >
                    {formatWan(item.total_pnl_economic)}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {data.action_details.length > 0 && (
        <Card title="动作明细" size="small">
          <Table
            dataSource={data.action_details}
            columns={detailColumns}
            rowKey="action_id"
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
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
