import * as React from "react";
import { SaveOutlined } from "@ant-design/icons";
import { Alert, Button, Input, Modal, Typography } from "antd";

import type { KpiMetricWithValue } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";

const { Text } = Typography;

export type MetricEditModalProps = {
  open: boolean;
  onClose: () => void;
  metric: KpiMetricWithValue | null;
  asOfDate: string;
  onSaveSuccess: () => void;
};

export function MetricEditModal({
  open,
  onClose,
  metric,
  asOfDate,
  onSaveSuccess,
}: MetricEditModalProps) {
  const client = useApiClient();
  const [targetValue, setTargetValue] = React.useState("");
  const [actualValue, setActualValue] = React.useState("");
  const [progressPct, setProgressPct] = React.useState("");
  const [actualText, setActualText] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (metric && open) {
      setTargetValue(metric.target_value || "");
      setActualValue(metric.actual_value || "");
      setProgressPct(metric.progress_pct || "");
      setActualText(metric.actual_text || "");
      setError(null);
    }
  }, [metric, open]);

  const handleSave = React.useCallback(async () => {
    if (!metric) return;
    setSaving(true);
    setError(null);
    try {
      await client.updateKpiValue(metric.value_id || 0, metric.metric_id, asOfDate, {
        target_value: targetValue || undefined,
        actual_value: actualValue || undefined,
        progress_pct: progressPct || undefined,
        actual_text: actualText || undefined,
      });
      onSaveSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [client, metric, asOfDate, targetValue, actualValue, progressPct, actualText, onSaveSuccess]);

  if (!metric) return null;

  return (
    <Modal
      title={
        <div>
          <div>编辑指标完成情况</div>
          <Text type="secondary" style={{ fontSize: 13, fontWeight: 400 }}>
            {metric.metric_name}
          </Text>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose} disabled={saving}>
          取消
        </Button>,
        <Button key="s" type="primary" loading={saving} icon={<SaveOutlined />} onClick={() => void handleSave()}>
          保存
        </Button>,
      ]}
      width={560}
    >
      <div
        style={{
          background: "#f8fafc",
          padding: 12,
          borderRadius: 8,
          marginBottom: 16,
          fontSize: 13,
        }}
      >
        <div>
          <Text type="secondary">指标代码 </Text>
          <Text code>{metric.metric_code}</Text>
        </div>
        <div style={{ marginTop: 6 }}>
          <Text type="secondary">单位 </Text>
          {metric.unit || "-"}
        </div>
        <div style={{ marginTop: 6 }}>
          <Text type="secondary">数据来源 </Text>
          {metric.data_source_type}
        </div>
        <div style={{ marginTop: 6 }}>
          <Text type="secondary">分值 </Text>
          <Text strong>{metric.score_weight}</Text>
        </div>
        {metric.scoring_text ? (
          <div style={{ marginTop: 10, borderTop: "1px solid #e2e8f0", paddingTop: 10 }}>
            <Text type="secondary">评分标准</Text>
            <div style={{ marginTop: 4 }}>{metric.scoring_text}</div>
          </div>
        ) : null}
      </div>
      <div style={{ display: "grid", gap: 14 }}>
        <div>
          <Text strong>目标值{metric.unit ? `（${metric.unit}）` : ""}</Text>
          <Input style={{ marginTop: 6 }} value={targetValue} onChange={(e) => setTargetValue(e.target.value)} />
        </div>
        <div>
          <Text strong>实际值{metric.unit ? `（${metric.unit}）` : ""}</Text>
          <Input style={{ marginTop: 6 }} value={actualValue} onChange={(e) => setActualValue(e.target.value)} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            AUTO 来源可留空，由系统抓取
          </Text>
        </div>
        <div>
          <Text strong>序时进度（%）</Text>
          <Input style={{ marginTop: 6 }} value={progressPct} onChange={(e) => setProgressPct(e.target.value)} />
        </div>
        <div>
          <Text strong>完成情况说明</Text>
          <Input.TextArea
            style={{ marginTop: 6 }}
            rows={3}
            value={actualText}
            onChange={(e) => setActualText(e.target.value)}
          />
        </div>
      </div>
      {error ? (
        <Alert type="error" showIcon style={{ marginTop: 16 }} message={error} />
      ) : null}
    </Modal>
  );
}

export default MetricEditModal;
