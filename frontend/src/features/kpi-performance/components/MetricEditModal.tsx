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
      rootClassName="kpi-modal-v2 kpi-modal-v2--edit"
      title={
        <div className="kpi-modal-v2__title">
          <div className="kpi-modal-v2__title-main">编辑指标完成情况</div>
          <Text type="secondary" className="kpi-modal-v2__title-subtitle">
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
      <div className="kpi-modal-v2__summary">
        <div className="kpi-modal-v2__summary-row">
          <Text type="secondary">指标代码 </Text>
          <Text code>{metric.metric_code}</Text>
        </div>
        <div className="kpi-modal-v2__summary-row">
          <Text type="secondary">单位 </Text>
          {metric.unit || "-"}
        </div>
        <div className="kpi-modal-v2__summary-row">
          <Text type="secondary">数据来源 </Text>
          {metric.data_source_type}
        </div>
        <div className="kpi-modal-v2__summary-row">
          <Text type="secondary">分值 </Text>
          <Text strong>{metric.score_weight}</Text>
        </div>
        {metric.scoring_text ? (
          <div className="kpi-modal-v2__summary-section">
            <Text type="secondary">评分标准</Text>
            <div className="kpi-modal-v2__summary-section-body">{metric.scoring_text}</div>
          </div>
        ) : null}
      </div>
      <div className="kpi-modal-v2__form">
        <div className="kpi-modal-v2__field">
          <Text strong>目标值{metric.unit ? `（${metric.unit}）` : ""}</Text>
          <Input className="kpi-modal-v2__control" value={targetValue} onChange={(e) => setTargetValue(e.target.value)} />
        </div>
        <div className="kpi-modal-v2__field">
          <Text strong>实际值{metric.unit ? `（${metric.unit}）` : ""}</Text>
          <Input className="kpi-modal-v2__control" value={actualValue} onChange={(e) => setActualValue(e.target.value)} />
          <Text type="secondary" className="kpi-modal-v2__help-text">
            AUTO 来源可留空，由系统抓取
          </Text>
        </div>
        <div className="kpi-modal-v2__field">
          <Text strong>序时进度（%）</Text>
          <Input className="kpi-modal-v2__control" value={progressPct} onChange={(e) => setProgressPct(e.target.value)} />
        </div>
        <div className="kpi-modal-v2__field">
          <Text strong>完成情况说明</Text>
          <Input.TextArea
            className="kpi-modal-v2__control"
            rows={3}
            value={actualText}
            onChange={(e) => setActualText(e.target.value)}
          />
        </div>
      </div>
      {error ? (
        <Alert type="error" showIcon className="kpi-modal-v2__alert" message={error} />
      ) : null}
    </Modal>
  );
}

export default MetricEditModal;
