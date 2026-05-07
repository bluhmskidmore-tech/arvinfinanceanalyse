import * as React from "react";
import {
  CalendarOutlined,
  CloudDownloadOutlined,
  PlusOutlined,
  SettingOutlined,
  SyncOutlined,
  TeamOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Row, Select, Space, Typography, message } from "antd";

import type {
  KpiFetchAndRecalcResponse,
  KpiMetricWithValue,
  KpiOwner,
  KpiPeriodSummaryResponse,
} from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import { BatchPasteModal } from "../components/BatchPasteModal";
import { MetricEditModal } from "../components/MetricEditModal";
import { MetricManageModal } from "../components/MetricManageModal";
import { MetricTable } from "../components/MetricTable";
import { OwnerList } from "../components/OwnerList";

const { Title, Text } = Typography;

type PeriodType = "DAILY" | "MONTH" | "QUARTER" | "YEAR";

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function formatDateCN(d: Date): string {
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

export default function KpiPerformancePage() {
  const client = useApiClient();
  const [year, setYear] = React.useState<number>(() => new Date().getFullYear());
  const [asOfDate, setAsOfDate] = React.useState<Date>(() => new Date());
  const [owners, setOwners] = React.useState<KpiOwner[]>([]);
  const [selectedOwner, setSelectedOwner] = React.useState<KpiOwner | null>(null);
  const [metrics, setMetrics] = React.useState<KpiMetricWithValue[]>([]);

  const [periodType, setPeriodType] = React.useState<PeriodType>("DAILY");
  const [periodValue, setPeriodValue] = React.useState<number>(() => new Date().getMonth() + 1);
  const [periodSummary, setPeriodSummary] = React.useState<KpiPeriodSummaryResponse | null>(null);

  const [loadingOwners, setLoadingOwners] = React.useState(false);
  const [loadingMetrics, setLoadingMetrics] = React.useState(false);
  const [fetchLoading, setFetchLoading] = React.useState(false);
  const [exportLoading, setExportLoading] = React.useState(false);

  const [lastFetchResult, setLastFetchResult] = React.useState<KpiFetchAndRecalcResponse | null>(null);

  const [editModalOpen, setEditModalOpen] = React.useState(false);
  const [editingMetric, setEditingMetric] = React.useState<KpiMetricWithValue | null>(null);
  const [batchPasteOpen, setBatchPasteOpen] = React.useState(false);

  const [metricManageOpen, setMetricManageOpen] = React.useState(false);
  const [metricManageMode, setMetricManageMode] = React.useState<"create" | "edit">("create");
  const [managingMetric, setManagingMetric] = React.useState<KpiMetricWithValue | null>(null);

  const yearOptions = React.useMemo(
    () => Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i),
    [],
  );

  const monthOptions = React.useMemo(
    () => Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1}月` })),
    [],
  );

  const quarterOptions = React.useMemo(
    () => [
      { value: 1, label: "Q1 (1-3月)" },
      { value: 2, label: "Q2 (4-6月)" },
      { value: 3, label: "Q3 (7-9月)" },
      { value: 4, label: "Q4 (10-12月)" },
    ],
    [],
  );

  const loadOwners = React.useCallback(async () => {
    setLoadingOwners(true);
    try {
      const response = await client.getKpiOwners({ year, is_active: true });
      setOwners(response.owners);
      setSelectedOwner((prev) => {
        if (prev && !response.owners.some((o) => o.owner_id === prev.owner_id)) {
          return null;
        }
        return prev;
      });
    } catch (e) {
      console.error(e);
      message.error("加载考核对象失败");
      setOwners([]);
    } finally {
      setLoadingOwners(false);
    }
  }, [client, year]);

  const loadMetrics = React.useCallback(async () => {
    if (!selectedOwner) {
      setMetrics([]);
      setPeriodSummary(null);
      return;
    }
    setLoadingMetrics(true);
    try {
      if (periodType === "DAILY") {
        const response = await client.getKpiValues({
          owner_id: selectedOwner.owner_id,
          as_of_date: formatDate(asOfDate),
          include_trace: true,
        });
        setMetrics(response.metrics);
        setPeriodSummary(null);
      } else {
        const response = await client.getKpiValuesSummary({
          owner_id: selectedOwner.owner_id,
          year,
          period_type: periodType,
          period_value: periodType !== "YEAR" ? periodValue : undefined,
        });
        setPeriodSummary(response);
        const converted: KpiMetricWithValue[] = response.metrics.map((m) => ({
          metric_id: m.metric_id,
          metric_code: m.metric_code,
          metric_name: m.metric_name,
          owner_id: selectedOwner.owner_id,
          year,
          major_category: m.major_category,
          indicator_category: m.indicator_category,
          target_value: m.target_value ?? null,
          target_text: undefined,
          score_weight: m.score_weight,
          unit: m.unit,
          scoring_text: undefined,
          scoring_rule_type: "LINEAR_RATIO",
          scoring_rule_params: undefined,
          data_source_type: "MANUAL",
          data_source_params: undefined,
          progress_plan: undefined,
          remarks: undefined,
          is_active: true,
          value_id: undefined,
          as_of_date: m.data_date,
          actual_value: m.period_actual_value,
          actual_text: undefined,
          completion_ratio: m.period_completion_ratio,
          progress_pct: m.period_progress_pct,
          score_value: m.period_score_value,
          fetch_status: undefined,
          fetch_trace: undefined,
          score_calc_trace: undefined,
          source: undefined,
        }));
        setMetrics(converted);
      }
    } catch (e) {
      console.error(e);
      message.error("加载指标失败");
      setMetrics([]);
      setPeriodSummary(null);
    } finally {
      setLoadingMetrics(false);
    }
  }, [client, selectedOwner, asOfDate, periodType, periodValue, year]);

  React.useEffect(() => {
    void loadOwners();
  }, [loadOwners]);

  React.useEffect(() => {
    void loadMetrics();
  }, [loadMetrics]);

  const handleFetchAndRecalc = React.useCallback(async () => {
    if (!selectedOwner) return;
    setFetchLoading(true);
    setLastFetchResult(null);
    try {
      const result = await client.fetchAndRecalcKpi(selectedOwner.owner_id, formatDate(asOfDate));
      setLastFetchResult(result);
      await loadMetrics();
      message.success("抓取并重算已完成");
    } catch (e) {
      console.error(e);
      message.error("抓取并重算失败");
    } finally {
      setFetchLoading(false);
    }
  }, [client, selectedOwner, asOfDate, loadMetrics]);

  const handleExportCSV = React.useCallback(async () => {
    setExportLoading(true);
    try {
      await client.downloadKpiReportCSV({
        year,
        owner_id: selectedOwner?.owner_id,
        as_of_date: formatDate(asOfDate),
      });
    } catch (e) {
      console.error(e);
      message.error("导出失败");
    } finally {
      setExportLoading(false);
    }
  }, [client, year, selectedOwner, asOfDate]);

  const handleOpenEditModal = React.useCallback((metric: KpiMetricWithValue) => {
    setEditingMetric(metric);
    setEditModalOpen(true);
  }, []);

  const handleCloseEditModal = React.useCallback(() => {
    setEditModalOpen(false);
    setEditingMetric(null);
  }, []);

  const handleAddMetric = React.useCallback(() => {
    setMetricManageMode("create");
    setManagingMetric(null);
    setMetricManageOpen(true);
  }, []);

  const handleEditMetricDef = React.useCallback((metric: KpiMetricWithValue) => {
    setMetricManageMode("edit");
    setManagingMetric(metric);
    setMetricManageOpen(true);
  }, []);

  const handleCloseMetricManage = React.useCallback(() => {
    setMetricManageOpen(false);
    setManagingMetric(null);
  }, []);

  const handleMetricManageSuccess = React.useCallback(() => {
    handleCloseMetricManage();
    void loadMetrics();
  }, [handleCloseMetricManage, loadMetrics]);

  const handleSaveSuccess = React.useCallback(() => {
    handleCloseEditModal();
    void loadMetrics();
  }, [handleCloseEditModal, loadMetrics]);

  const handleBatchPasteSuccess = React.useCallback(() => {
    setBatchPasteOpen(false);
    void loadMetrics();
  }, [loadMetrics]);

  return (
    <div style={{ display: "grid", gap: 20 }} data-testid="kpi-performance-page">
      <div>
        <Title level={3} style={{ marginBottom: 4 }}>
          绩效考核
        </Title>
        <Text type="secondary">
          KPI 指标与完成情况 · 截止 {formatDateCN(asOfDate)}
        </Text>
      </div>

      <Card>
        <Row gutter={[16, 16]} align="middle" justify="space-between">
          <Col flex="auto">
            <Space wrap size="middle">
              <div>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>考核年度</div>
                <Select
                  style={{ width: 120 }}
                  value={year}
                  options={yearOptions.map((y) => ({ label: `${y} 年`, value: y }))}
                  onChange={(v) => setYear(v)}
                />
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>时间维度</div>
                <Select
                  style={{ width: 120 }}
                  value={periodType}
                  options={[
                    { label: "按日期", value: "DAILY" },
                    { label: "月度", value: "MONTH" },
                    { label: "季度", value: "QUARTER" },
                    { label: "年度", value: "YEAR" },
                  ]}
                  onChange={(v) => {
                    setPeriodType(v as PeriodType);
                    if (v === "MONTH") {
                      setPeriodValue(new Date().getMonth() + 1);
                    } else if (v === "QUARTER") {
                      setPeriodValue(Math.ceil((new Date().getMonth() + 1) / 3));
                    }
                  }}
                />
              </div>
              {periodType === "MONTH" ? (
                <div>
                  <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>月份</div>
                  <Select
                    style={{ width: 100 }}
                    value={periodValue}
                    options={monthOptions}
                    onChange={(v) => setPeriodValue(v)}
                  />
                </div>
              ) : null}
              {periodType === "QUARTER" ? (
                <div>
                  <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>季度</div>
                  <Select
                    style={{ width: 140 }}
                    value={periodValue}
                    options={quarterOptions}
                    onChange={(v) => setPeriodValue(v)}
                  />
                </div>
              ) : null}
              {periodType === "DAILY" ? (
                <div>
                  <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>截止日期</div>
                  <input
                    type="date"
                    value={formatDate(asOfDate)}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v) setAsOfDate(new Date(`${v}T12:00:00`));
                    }}
                    style={{
                      width: 180,
                      padding: "6px 10px",
                      borderRadius: 8,
                      border: "1px solid #d9d9d9",
                      fontSize: 14,
                    }}
                  />
                </div>
              ) : null}
            </Space>
          </Col>
          <Col>
            <Space wrap>
              <Button icon={<PlusOutlined />} disabled={!selectedOwner} onClick={handleAddMetric}>
                新增指标
              </Button>
              <Button icon={<UploadOutlined />} disabled={!selectedOwner} onClick={() => setBatchPasteOpen(true)}>
                批量导入
              </Button>
              <Button
                type="primary"
                icon={<SyncOutlined />}
                loading={fetchLoading}
                disabled={!selectedOwner}
                onClick={() => void handleFetchAndRecalc()}
              >
                抓取并重算
              </Button>
              <Button
                icon={<CloudDownloadOutlined />}
                loading={exportLoading}
                onClick={() => void handleExportCSV()}
              >
                导出 CSV
              </Button>
            </Space>
          </Col>
        </Row>
        {lastFetchResult ? (
          <div
            style={{
              marginTop: 16,
              padding: 12,
              background: "#f8fafc",
              borderRadius: 8,
              fontSize: 13,
            }}
          >
            <Space wrap>
              <Text>共 {lastFetchResult.total_metrics} 个指标</Text>
              <Text type="success">成功抓取 {lastFetchResult.fetched_count}</Text>
              <Text type="secondary">成功计分 {lastFetchResult.scored_count}</Text>
              {lastFetchResult.failed_count > 0 ? (
                <Text type="danger">失败 {lastFetchResult.failed_count}</Text>
              ) : null}
              {lastFetchResult.skipped_count > 0 ? (
                <Text type="secondary">跳过 {lastFetchResult.skipped_count}</Text>
              ) : null}
            </Space>
          </div>
        ) : null}
      </Card>

      <Row gutter={20}>
        <Col xs={24} lg={7}>
          <OwnerList
            owners={owners}
            selectedOwnerId={selectedOwner?.owner_id ?? null}
            onSelect={(o) => {
              setSelectedOwner(o);
              setLastFetchResult(null);
            }}
            loading={loadingOwners}
          />
        </Col>
        <Col xs={24} lg={17}>
          {selectedOwner ? (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Card>
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
                  <div>
                    <Title level={4} style={{ marginBottom: 4 }}>
                      {selectedOwner.owner_name}
                    </Title>
                    <Text type="secondary">
                      {selectedOwner.org_unit} · {year} 年度
                      {periodType === "DAILY" ? ` · 截止 ${formatDateCN(asOfDate)}` : null}
                      {periodType === "MONTH" ? ` · ${year}年${periodValue}月` : null}
                      {periodType === "QUARTER" ? ` · ${year}年Q${periodValue}` : null}
                      {periodType === "YEAR" ? ` · ${year}年度汇总` : null}
                    </Text>
                  </div>
                  <Space wrap>
                    {periodSummary ? (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "6px 12px",
                          background: "#e6f4ff",
                          borderRadius: 8,
                          fontSize: 13,
                        }}
                      >
                        <CalendarOutlined style={{ color: "#1677ff" }} />
                        <Text strong style={{ color: "#0958d9" }}>
                          {periodSummary.period_label}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          ({periodSummary.period_start_date} ~ {periodSummary.period_end_date})
                        </Text>
                      </div>
                    ) : null}
                    <Button icon={<SettingOutlined />} onClick={handleAddMetric}>
                      管理指标
                    </Button>
                  </Space>
                </div>
              </Card>
              <MetricTable
                metrics={metrics}
                loading={loadingMetrics}
                onRefresh={() => void loadMetrics()}
                onAddMetric={handleAddMetric}
                onEditMetricDef={handleEditMetricDef}
                valueAsOfDate={formatDate(asOfDate)}
                onFullEdit={handleOpenEditModal}
              />
            </Space>
          ) : (
            <Card style={{ minHeight: 420, display: "grid", placeItems: "center" }}>
              <div style={{ textAlign: "center", color: "#94a3b8" }}>
                <TeamOutlined style={{ fontSize: 48, marginBottom: 12 }} />
                <Title level={4} type="secondary">
                  请选择考核对象
                </Title>
                <Text type="secondary">从左侧列表选择部室，查看绩效指标明细</Text>
              </div>
            </Card>
          )}
        </Col>
      </Row>

      <MetricEditModal
        open={editModalOpen}
        onClose={handleCloseEditModal}
        metric={editingMetric}
        asOfDate={formatDate(asOfDate)}
        onSaveSuccess={handleSaveSuccess}
      />

      <MetricManageModal
        open={metricManageOpen}
        onClose={handleCloseMetricManage}
        mode={metricManageMode}
        metric={managingMetric}
        owner={selectedOwner}
        onSuccess={handleMetricManageSuccess}
      />

      <BatchPasteModal
        open={batchPasteOpen}
        onClose={() => setBatchPasteOpen(false)}
        owner={selectedOwner}
        asOfDate={formatDate(asOfDate)}
        metrics={metrics}
        onSuccess={handleBatchPasteSuccess}
      />
    </div>
  );
}
