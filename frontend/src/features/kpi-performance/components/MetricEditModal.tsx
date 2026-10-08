import * as React from "react";
import { SaveOutlined } from "@ant-design/icons";
import { Alert, Button, Input, Modal, Typography } from "antd";

import type { KpiMetricWithValue } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { observeKpiWrite, type KpiPendingWriteProps, type PendingKpiWrite } from "./pendingKpiWrite";
import { EM_DASH } from "../../../utils/format";

const { Text } = Typography;

export type MetricEditModalProps = KpiPendingWriteProps & {
  open: boolean;
  onClose: () => void;
  metric: KpiMetricWithValue | null;
  asOfDate?: string;
  onSaveSuccess: () => void;
};

export function MetricEditModal({
  open,
  onClose,
  metric,
  asOfDate,
  onSaveSuccess,
  writePending = false,
  onUnconfirmedWrite,
}: MetricEditModalProps) {
  const client = useApiClient();
  const [targetValue, setTargetValue] = React.useState("");
  const [actualValue, setActualValue] = React.useState("");
  const [progressPct, setProgressPct] = React.useState("");
  const [actualText, setActualText] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const requestSeq = React.useRef(0);
  const pending = React.useRef(false);
  const pendingWrite = React.useRef<PendingKpiWrite | null>(null);
  const writeDate = metric?.as_of_date || asOfDate;

  React.useEffect(() => {
    requestSeq.current += 1;
    pending.current = false;
    pendingWrite.current = null;
    setSaving(false);
    if (metric && open) {
      setTargetValue(metric.target_value || "");
      setActualValue(metric.actual_value || "");
      setProgressPct(metric.progress_pct || "");
      setActualText(metric.actual_text || "");
      setError(null);
    }
    return () => { requestSeq.current += 1; };
  }, [metric, open, asOfDate]);

  const handleSave = React.useCallback(async () => {
    if (!open || !metric || !writeDate || pending.current || writePending) return;
    pending.current = true;
    const requestId = ++requestSeq.current;
    setSaving(true);
    setError(null);
    try {
      const operation = client.updateKpiValue(metric.value_id || 0, metric.metric_id, writeDate, {
        target_value: targetValue || undefined,
        actual_value: actualValue || undefined,
        progress_pct: progressPct || undefined,
        actual_text: actualText || undefined,
      });
      pendingWrite.current = observeKpiWrite(operation);
      await operation;
      if (requestId === requestSeq.current) onSaveSuccess();
    } catch (err: unknown) {
      if (requestId === requestSeq.current) {
        if (pendingWrite.current) onUnconfirmedWrite?.(pendingWrite.current);
        setError(err instanceof Error ? err.message : "保存结果尚未确认");
      }
    } finally {
      if (requestId === requestSeq.current) {
        pending.current = false;
        setSaving(false);
      }
    }
  }, [client, metric, writeDate, targetValue, actualValue, progressPct, actualText, onSaveSuccess, open, writePending, onUnconfirmedWrite]);

  const stopWaiting = () => {
    const write = pendingWrite.current;
    if (!write || !onUnconfirmedWrite) return;
    pendingWrite.current = null;
    requestSeq.current += 1;
    onUnconfirmedWrite(write);
    onClose();
  };

  if (!metric) return null;

  return (
    <Modal
      rootClassName="kpi-modal-v2 kpi-modal-v2--edit"
      /*
       * antd Modal 挂 body，不继承页根 scope（portal 主题逃逸）。照 positions
       * CustomerDetailModal 先例用 modalRender 包一层 Nocturne scope 容器，
       * 弹窗内 --ib-* 与 --dh-api-* 才解析为 scope 色板值。
       */
      modalRender={(node) => (
        <div className="theme-dh-api" data-moss-theme-scope="kpi">
          {node}
        </div>
      )}
      title={
        <div className="kpi-modal-v2__title">
          <div className="kpi-modal-v2__title-main">编辑指标完成情况</div>
          <Text type="secondary" className="kpi-modal-v2__title-subtitle">
            {metric.metric_name}
          </Text>
        </div>
      }
      open={open}
      closable={!saving}
      maskClosable={!saving}
      keyboard={!saving}
      onCancel={() => { if (!pending.current) onClose(); }}
      footer={[
        saving && onUnconfirmedWrite ? <Button key="stop" onClick={stopWaiting}>停止等待</Button> : null,
        <Button key="c" onClick={onClose} disabled={saving}>
          取消
        </Button>,
        <Button key="s" type="primary" loading={saving} disabled={!writeDate || writePending} icon={<SaveOutlined />} onClick={() => void handleSave()}>
          保存
        </Button>,
      ]}
      width={560}
    >
      {((saving) && onUnconfirmedWrite) || writePending ? (
        <Alert type="warning" showIcon message={writePending
          ? "前一笔写入结果尚未确认，请关闭窗口后刷新核实，勿重复提交。"
          : "停止等待只关闭窗口，不会取消服务端写入；结果仍需核实。"} />
      ) : null}
      <div className="kpi-modal-v2__summary">
        <div className="kpi-modal-v2__summary-row">
          <Text type="secondary">写入日期 </Text>
          <Text>{writeDate || "未确定，请切换到日视图选择日期"}</Text>
        </div>
        <div className="kpi-modal-v2__summary-row">
          <Text type="secondary">指标代码 </Text>
          <Text code>{metric.metric_code}</Text>
        </div>
        <div className="kpi-modal-v2__summary-row">
          <Text type="secondary">单位 </Text>
          {metric.unit || EM_DASH}
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
