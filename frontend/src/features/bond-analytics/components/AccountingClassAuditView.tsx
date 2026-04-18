import { useEffect, useState } from "react";
import { Card, Statistic, Row, Col, Table, Tag, Alert, Spin } from "antd";
import { useApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import type { AccountingClassAuditResponse } from "../types";
import { formatPct, formatWan } from "../utils/formatters";
import { SectionLead } from "./SectionLead";

interface Props {
  reportDate: string;
}

const auditColumns = [
  { title: "资产类别", dataIndex: "asset_class", key: "asset_class", width: 200 },
  { title: "持仓数", dataIndex: "position_count", key: "position_count", width: 80 },
  { title: "市值", dataIndex: "market_value", key: "market_value", width: 120, render: formatWan },
  {
    title: "权重",
    dataIndex: "market_value_weight",
    key: "market_value_weight",
    width: 80,
    render: (v: Numeric) => formatPct(v),
  },
  { title: "推断分类", dataIndex: "infer_accounting_class", key: "infer_accounting_class", width: 90 },
  { title: "映射分类", dataIndex: "map_accounting_class", key: "map_accounting_class", width: 90 },
  { title: "推断规则", dataIndex: "infer_rule_id", key: "infer_rule_id", width: 80 },
  { title: "映射规则", dataIndex: "map_rule_id", key: "map_rule_id", width: 80 },
  {
    title: "状态",
    key: "flags",
    width: 140,
    render: (_: unknown, row: { is_divergent: boolean; is_map_unclassified: boolean }) => (
      <>
        {row.is_divergent && <Tag color="error">分歧</Tag>}
        {row.is_map_unclassified && <Tag color="warning">未分类</Tag>}
        {!row.is_divergent && !row.is_map_unclassified && <Tag color="success">一致</Tag>}
      </>
    ),
  },
];

export function AccountingClassAuditView({ reportDate }: Props) {
  const client = useApiClient();
  const [data, setData] = useState<AccountingClassAuditResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const envelope = await client.getBondAnalyticsAccountingClassAudit(reportDate);
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
  }, [client, reportDate]);

  if (loading) return <Spin style={{ display: "block", margin: "40px auto" }} />;
  if (error) return <Alert type="error" message={`加载失败：${error}`} />;
  if (!data) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SectionLead
        eyebrow="Accounting Class"
        title="会计分类审计概览"
        description="按报告日读取后端 accounting class audit read model；页面只对比推断路径与映射路径，不在前端重写会计分类。"
        testId="accounting-class-audit-shell-lead"
      />
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="资产类别数（去重）" value={data.distinct_asset_classes} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="分歧分类"
              value={data.divergent_asset_classes}
              valueStyle={data.divergent_asset_classes > 0 ? { color: "#cf1322" } : undefined}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="映射为其他（other）"
              value={data.map_unclassified_asset_classes}
              valueStyle={data.map_unclassified_asset_classes > 0 ? { color: "#faad14" } : undefined}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="覆盖市值" value={formatWan(data.total_market_value)} />
          </Card>
        </Col>
      </Row>

      <SectionLead
        eyebrow="Rules"
        title="分类路径说明"
        description="说明 infer_accounting_class 与 map_accounting_class 的来源和分歧含义，保留后端规则版本边界。"
        testId="accounting-class-audit-rules-lead"
      />
      <Card size="small">
        <div style={{ fontSize: 13, color: "#5c6b82", marginBottom: 12 }}>
          <p style={{ margin: "0 0 8px" }}>
            本审计对比两条会计分类路径：
          </p>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li><code>infer_accounting_class</code> — Campisi/归因使用的推断路径</li>
            <li><code>map_accounting_class</code> — 收益拆解/KRD/利差使用的映射路径</li>
          </ul>
          <p style={{ margin: "8px 0 0" }}>
            「分歧」表示两条路径对同一资产类别（asset_class）给出不同结果，需要人工确认。
          </p>
        </div>
      </Card>

      <SectionLead
        eyebrow="Details"
        title="会计分类审计明细"
        description="明细表继续展示后端 rows，保留分歧、未分类和一致状态标记。"
        testId="accounting-class-audit-detail-lead"
      />
      {data.rows.length > 0 && (
        <Card title="审计明细" size="small">
          <Table
            dataSource={data.rows}
            columns={auditColumns}
            rowKey="asset_class"
            pagination={false}
            size="small"
            scroll={{ x: 1000 }}
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
