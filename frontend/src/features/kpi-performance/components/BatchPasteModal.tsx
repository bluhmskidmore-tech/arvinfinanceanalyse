import * as React from "react";
import { InboxOutlined, UploadOutlined } from "@ant-design/icons";
import { Alert, Button, Input, Modal, Table, Tag, Typography } from "antd";

import type { KpiMetricWithValue, KpiOwner } from "../../../api/contracts";
import { useApiClient } from "../../../api/client";

const { Paragraph, Text } = Typography;

export type BatchPasteModalProps = {
  open: boolean;
  onClose: () => void;
  owner: KpiOwner | null;
  asOfDate: string;
  metrics: KpiMetricWithValue[];
  onSuccess: () => void;
  writeEnabled?: boolean;
  disabledReason?: string;
};

type ParsedRow = {
  rowIndex: number;
  metricCode: string;
  actualValue: string;
  progressPct: string;
  metric?: KpiMetricWithValue;
  error?: string;
  status: "pending" | "valid" | "invalid";
};

export function BatchPasteModal({
  open,
  onClose,
  owner,
  asOfDate,
  metrics,
  onSuccess,
  writeEnabled = true,
  disabledReason,
}: BatchPasteModalProps) {
  const client = useApiClient();
  const [pasteText, setPasteText] = React.useState("");
  const [parsedRows, setParsedRows] = React.useState<ParsedRow[]>([]);
  const [importing, setImporting] = React.useState(false);
  const [importResult, setImportResult] = React.useState<{
    success: number;
    failed: number;
    errors: string[];
  } | null>(null);

  const metricCodeMap = React.useMemo(() => {
    const map = new Map<string, KpiMetricWithValue>();
    metrics.forEach((m) => {
      map.set(m.metric_code.toLowerCase(), m);
    });
    return map;
  }, [metrics]);

  const handleParse = React.useCallback(() => {
    if (!writeEnabled) return;
    if (!pasteText.trim()) {
      setParsedRows([]);
      return;
    }
    const lines = pasteText.trim().split("\n");
    const rows: ParsedRow[] = [];
    lines.forEach((line, index) => {
      const trimmedLine = line.trim();
      if (!trimmedLine) return;
      const parts = trimmedLine.split(/\t+|\s{2,}/);
      if (parts.length < 2) {
        rows.push({
          rowIndex: index + 1,
          metricCode: parts[0] || "",
          actualValue: "",
          progressPct: "",
          error: "格式错误：至少需要指标代码和实际值",
          status: "invalid",
        });
        return;
      }
      const metricCode = parts[0].trim();
      const actualValue = parts[1]?.trim() || "";
      const progressPct = parts[2]?.trim() || "";
      const metric = metricCodeMap.get(metricCode.toLowerCase());
      if (!metric) {
        rows.push({
          rowIndex: index + 1,
          metricCode,
          actualValue,
          progressPct,
          error: `未找到指标代码: ${metricCode}`,
          status: "invalid",
        });
        return;
      }
      if (actualValue && Number.isNaN(parseFloat(actualValue))) {
        rows.push({
          rowIndex: index + 1,
          metricCode,
          actualValue,
          progressPct,
          metric,
          error: "实际值格式错误",
          status: "invalid",
        });
        return;
      }
      if (progressPct && Number.isNaN(parseFloat(progressPct))) {
        rows.push({
          rowIndex: index + 1,
          metricCode,
          actualValue,
          progressPct,
          metric,
          error: "序时进度格式错误",
          status: "invalid",
        });
        return;
      }
      rows.push({
        rowIndex: index + 1,
        metricCode,
        actualValue,
        progressPct,
        metric,
        status: "valid",
      });
    });
    setParsedRows(rows);
    setImportResult(null);
  }, [pasteText, metricCodeMap, writeEnabled]);

  const handleImport = React.useCallback(async () => {
    if (!writeEnabled) return;
    const validRows = parsedRows.filter((r) => r.status === "valid" && r.metric);
    if (validRows.length === 0) return;
    setImporting(true);
    setImportResult(null);
    try {
      const items = validRows.map((row) => ({
        metric_id: row.metric!.metric_id,
        actual_value: row.actualValue || undefined,
        progress_pct: row.progressPct || undefined,
      }));
      const response = await client.batchUpdateKpiValues(asOfDate, items);
      setImportResult({
        success: response.success_count,
        failed: response.failed_count,
        errors: response.errors || [],
      });
      if (response.success_count > 0) {
        setTimeout(() => onSuccess(), 1200);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "导入失败";
      setImportResult({
        success: 0,
        failed: validRows.length,
        errors: [msg],
      });
    } finally {
      setImporting(false);
    }
  }, [client, parsedRows, asOfDate, onSuccess, writeEnabled]);

  const handleClear = React.useCallback(() => {
    setPasteText("");
    setParsedRows([]);
    setImportResult(null);
  }, []);

  const stats = React.useMemo(() => {
    const valid = parsedRows.filter((r) => r.status === "valid").length;
    const invalid = parsedRows.filter((r) => r.status === "invalid").length;
    return { valid, invalid, total: parsedRows.length };
  }, [parsedRows]);

  if (!owner) return null;

  return (
    <Modal
      title={
        <span>
          <InboxOutlined style={{ marginRight: 8 }} />
          批量导入
        </span>
      }
      open={open}
      onCancel={onClose}
      width={880}
      footer={[
        <Button key="cancel" onClick={onClose} disabled={importing}>
          取消
        </Button>,
        <Button
          key="import"
          type="primary"
          loading={importing}
          icon={<UploadOutlined />}
          disabled={!writeEnabled || stats.valid === 0}
          onClick={() => void handleImport()}
          data-testid="kpi-batch-import-submit-button"
        >
          导入（{stats.valid} 条）
        </Button>,
      ]}
    >
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        {owner.owner_name} · {asOfDate}
      </Paragraph>
      {!writeEnabled ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Batch import is reserved."
          description={disabledReason ?? "KPI batch value import routes are not live yet."}
          data-testid="kpi-batch-import-reserved-alert"
        />
      ) : null}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="使用说明"
        description={
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>从 Excel 复制后粘贴到文本框</li>
            <li>
              格式：<Text code>指标代码 [Tab] 实际值 [Tab] 序时进度</Text>（序时进度可选）
            </li>
            <li>点击「解析」预览，再「导入」</li>
          </ul>
        }
      />
      <div style={{ marginBottom: 8 }}>
        <Text strong>粘贴数据</Text>
      </div>
      <Input.TextArea
        value={pasteText}
        onChange={(e) => setPasteText(e.target.value)}
        disabled={!writeEnabled}
        placeholder="从 Excel 粘贴…"
        rows={6}
        style={{ fontFamily: "monospace", marginBottom: 8 }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Text type="secondary">当前共 {metrics.length} 个指标</Text>
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={handleClear} disabled={!writeEnabled}>
            清空
          </Button>
          <Button type="primary" onClick={handleParse} disabled={!writeEnabled} data-testid="kpi-batch-import-parse-button">
            解析
          </Button>
        </div>
      </div>
      {parsedRows.length > 0 ? (
        <>
          <div style={{ marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
            <Text strong>预览</Text>
            <Text>
              <Text type="success">有效 {stats.valid}</Text>
              {" · "}
              <Text type="danger">无效 {stats.invalid}</Text>
              {" · "}共 {stats.total}
            </Text>
          </div>
          <Table
            size="small"
            pagination={false}
            scroll={{ y: 220 }}
            dataSource={parsedRows.map((r, i) => ({ ...r, key: i }))}
            columns={[
              { title: "#", dataIndex: "rowIndex", width: 48 },
              { title: "指标代码", dataIndex: "metricCode", render: (t: string) => <code>{t}</code> },
              {
                title: "指标名称",
                dataIndex: "metric",
                render: (_: unknown, row: ParsedRow) => row.metric?.metric_name || "-",
              },
              {
                title: "实际值",
                dataIndex: "actualValue",
                align: "right",
                render: (t: string) => t || "-",
              },
              {
                title: "序时进度",
                dataIndex: "progressPct",
                align: "right",
                render: (t: string) => (t ? `${t}%` : "-"),
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 88,
                align: "center",
                render: (s: string, row: ParsedRow) =>
                  s === "valid" ? (
                    <Tag color="success">有效</Tag>
                  ) : (
                    <Tag color="error" title={row.error}>
                      无效
                    </Tag>
                  ),
              },
            ]}
          />
          {stats.invalid > 0 ? (
            <Alert
              type="error"
              showIcon
              style={{ marginTop: 12 }}
              message="以下行将被跳过"
              description={
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {parsedRows
                    .filter((r) => r.status === "invalid")
                    .slice(0, 5)
                    .map((r) => (
                      <li key={r.rowIndex}>
                        行 {r.rowIndex}: {r.error}
                      </li>
                    ))}
                  {stats.invalid > 5 ? <li>… 另有 {stats.invalid - 5} 条</li> : null}
                </ul>
              }
            />
          ) : null}
        </>
      ) : null}
      {importResult ? (
        <Alert
          type={importResult.failed === 0 ? "success" : "warning"}
          showIcon
          style={{ marginTop: 16 }}
          message="导入结果"
          description={
            <>
              <div>
                成功 {importResult.success} 条，失败 {importResult.failed} 条
              </div>
              {importResult.errors.length > 0 ? (
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {importResult.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              ) : null}
            </>
          }
        />
      ) : null}
    </Modal>
  );
}

export default BatchPasteModal;
