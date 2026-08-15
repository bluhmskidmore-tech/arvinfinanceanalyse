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
import { Button, DatePicker, Select, Typography, message } from "antd";
import dayjs from "dayjs";

import type {
  KpiFetchAndRecalcResponse,
  KpiMetricWithValue,
  KpiOwner,
  KpiOwnerAuthorityMeta,
  KpiPeriodSummaryResponse,
} from "../../../api/contracts";
import { useApiClient } from "../../../api/client";
import {
  DataStatusStrip,
  PageDecisionHero,
  PageFilterTray,
  PageStateSurface,
} from "../../../components/page/PagePrimitives";
import { BatchPasteModal } from "../components/BatchPasteModal";
import { MetricEditModal } from "../components/MetricEditModal";
import { MetricManageModal } from "../components/MetricManageModal";
import { MetricTable } from "../components/MetricTable";
import { OwnerList } from "../components/OwnerList";
import "./KpiPerformancePage.css";

const { Text } = Typography;

type PeriodType = "DAILY" | "MONTH" | "QUARTER" | "YEAR";

// 用本地日期分量而非 toISOString()：后者按 UTC 取日，会在 UTC+8 凌晨把
// “今天”算成昨天，导致页头（本地日）与筛选器/请求日期差一天。
function formatDate(d: Date): string {
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

function formatDateCN(d: Date): string {
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

/** 下拉弹层挂在页面容器内（不挂 body），保持 Nocturne scope 命中。 */
function resolvePopupContainer(trigger: HTMLElement): HTMLElement {
  return trigger.parentElement ?? document.body;
}

export default function KpiPerformancePage() {
  const client = useApiClient();
  const [year, setYear] = React.useState<number>(() => new Date().getFullYear());
  const [asOfDate, setAsOfDate] = React.useState<Date>(() => new Date());
  const [owners, setOwners] = React.useState<KpiOwner[]>([]);
  const [ownersError, setOwnersError] = React.useState<Error | null>(null);
  const [ownersMeta, setOwnersMeta] = React.useState<KpiOwnerAuthorityMeta | null>(null);
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

  // 请求序号守卫：快速切换部室/期间时，只允许最新一次请求落地，
  // 防止先发后至的响应覆盖新数据或提前复位 loading。
  const ownersRequestSeqRef = React.useRef(0);
  const metricsRequestSeqRef = React.useRef(0);

  const loadOwners = React.useCallback(async () => {
    const requestId = ++ownersRequestSeqRef.current;
    setLoadingOwners(true);
    try {
      const response = await client.getKpiOwners({ year, is_active: true });
      if (requestId !== ownersRequestSeqRef.current) return;
      setOwnersError(null);
      setOwnersMeta(response.meta ?? null);
      setOwners(response.owners);
      setSelectedOwner((prev) => {
        if (prev && !response.owners.some((o) => o.owner_id === prev.owner_id)) {
          return null;
        }
        return prev;
      });
    } catch (e) {
      if (requestId !== ownersRequestSeqRef.current) return;
      console.error(e);
      message.error("加载考核对象失败");
      setOwnersError(e instanceof Error ? e : new Error(String(e)));
      setOwnersMeta(null);
      setOwners([]);
    } finally {
      if (requestId === ownersRequestSeqRef.current) {
        setLoadingOwners(false);
      }
    }
  }, [client, year]);

  const loadMetrics = React.useCallback(async () => {
    const requestId = ++metricsRequestSeqRef.current;
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
        if (requestId !== metricsRequestSeqRef.current) return;
        setMetrics(response.metrics);
        setPeriodSummary(null);
      } else {
        const response = await client.getKpiValuesSummary({
          owner_id: selectedOwner.owner_id,
          year,
          period_type: periodType,
          period_value: periodType !== "YEAR" ? periodValue : undefined,
        });
        if (requestId !== metricsRequestSeqRef.current) return;
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
      if (requestId !== metricsRequestSeqRef.current) return;
      console.error(e);
      message.error("加载指标失败");
      setMetrics([]);
      setPeriodSummary(null);
    } finally {
      if (requestId === metricsRequestSeqRef.current) {
        setLoadingMetrics(false);
      }
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

  const currentPeriodLabel =
    periodType === "DAILY"
      ? `截止 ${formatDateCN(asOfDate)}`
      : periodType === "MONTH"
        ? `${year}年${periodValue}月`
        : periodType === "QUARTER"
          ? `${year}年Q${periodValue}`
          : `${year}年度汇总`;

  const currentOwnerLabel = selectedOwner
    ? `${selectedOwner.owner_name} · ${selectedOwner.org_unit}`
    : "未选择考核对象";

  const ownerGateTitle = selectedOwner ? undefined : "请先在左侧选择考核对象";

  return (
    <div
      className="moss-page-v2-shell kpi-performance-page"
      data-moss-theme-scope="kpi"
      data-testid="kpi-performance-page"
    >
      <PageDecisionHero
        testId="kpi-performance-header"
        className="kpi-performance-page__header"
        eyebrow="绩效治理"
        title="绩效考核"
        businessQuestion={`KPI 指标与完成情况 · ${currentPeriodLabel}`}
        reportDateSlot={<span>当前口径：{currentOwnerLabel}</span>}
        actions={
          <div className="kpi-performance-page__hero-actions" data-testid="kpi-performance-action-row">
            <Button
              icon={<PlusOutlined aria-hidden="true" />}
              disabled={!selectedOwner}
              title={ownerGateTitle}
              onClick={handleAddMetric}
            >
              新增指标
            </Button>
            <Button
              icon={<UploadOutlined aria-hidden="true" />}
              disabled={!selectedOwner}
              title={ownerGateTitle}
              onClick={() => setBatchPasteOpen(true)}
            >
              批量导入
            </Button>
            <Button
              type="primary"
              icon={<SyncOutlined aria-hidden="true" />}
              loading={fetchLoading}
              disabled={!selectedOwner}
              title={ownerGateTitle}
              onClick={() => void handleFetchAndRecalc()}
            >
              抓取并重算
            </Button>
            <Button
              icon={<CloudDownloadOutlined aria-hidden="true" />}
              loading={exportLoading}
              onClick={() => void handleExportCSV()}
            >
              导出 CSV
            </Button>
          </div>
        }
      >
        <DataStatusStrip
          testId="kpi-performance-data-status"
          className="kpi-performance-page__status-strip"
        >
          <span>{year} 年度</span>
          <span>{currentOwnerLabel}</span>
        </DataStatusStrip>
      </PageDecisionHero>

      <PageFilterTray testId="kpi-performance-filters">
        <div className="kpi-performance-page__filter-tray">
          <div className="kpi-performance-page__filter-row" data-testid="kpi-performance-filter-row">
            <div className="kpi-performance-page__field">
              <div className="kpi-performance-page__field-label">考核年度</div>
              <Select
                aria-label="KPI assessment year"
                className="kpi-performance-page__select kpi-performance-page__select--year"
                getPopupContainer={resolvePopupContainer}
                value={year}
                options={yearOptions.map((y) => ({ label: `${y} 年`, value: y }))}
                onChange={(v) => setYear(v)}
              />
            </div>
            <div className="kpi-performance-page__field">
              <div className="kpi-performance-page__field-label">时间维度</div>
              <Select
                aria-label="KPI period type"
                className="kpi-performance-page__select kpi-performance-page__select--period-type"
                getPopupContainer={resolvePopupContainer}
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
              <div className="kpi-performance-page__field">
                <div className="kpi-performance-page__field-label">月份</div>
                <Select
                  aria-label="KPI month"
                  className="kpi-performance-page__select kpi-performance-page__select--month"
                  getPopupContainer={resolvePopupContainer}
                  value={periodValue}
                  options={monthOptions}
                  onChange={(v) => setPeriodValue(v)}
                />
              </div>
            ) : null}
            {periodType === "QUARTER" ? (
              <div className="kpi-performance-page__field">
                <div className="kpi-performance-page__field-label">季度</div>
                <Select
                  aria-label="KPI quarter"
                  className="kpi-performance-page__select kpi-performance-page__select--quarter"
                  getPopupContainer={resolvePopupContainer}
                  value={periodValue}
                  options={quarterOptions}
                  onChange={(v) => setPeriodValue(v)}
                />
              </div>
            ) : null}
            {periodType === "DAILY" ? (
              <div className="kpi-performance-page__field">
                <div className="kpi-performance-page__field-label">截止日期</div>
                {/* antd DatePicker 固定 YYYY-MM-DD 展示；原生 date input 跟随
                    浏览器 locale（如 08/13/2026），与页头中文日期格式打架。 */}
                <DatePicker
                  aria-label="KPI as-of date"
                  className="kpi-performance-page__date-input"
                  allowClear={false}
                  format="YYYY-MM-DD"
                  value={dayjs(formatDate(asOfDate))}
                  getPopupContainer={resolvePopupContainer}
                  onChange={(v) => {
                    if (v) setAsOfDate(new Date(v.year(), v.month(), v.date(), 12));
                  }}
                />
              </div>
            ) : null}
          </div>
        </div>
      </PageFilterTray>

      {lastFetchResult ? (
        <DataStatusStrip
          testId="kpi-performance-fetch-result"
          className="kpi-performance-page__fetch-result"
        >
          <span>共 {lastFetchResult.total_metrics} 个指标</span>
          <span>成功抓取 {lastFetchResult.fetched_count}</span>
          <span>成功计分 {lastFetchResult.scored_count}</span>
          {lastFetchResult.failed_count > 0 ? <span>失败 {lastFetchResult.failed_count}</span> : null}
          {lastFetchResult.skipped_count > 0 ? <span>跳过 {lastFetchResult.skipped_count}</span> : null}
        </DataStatusStrip>
      ) : null}

      <div
        className="kpi-performance-page__main-grid"
        data-testid="kpi-performance-main-grid"
      >
        <OwnerList
          owners={owners}
          selectedOwnerId={selectedOwner?.owner_id ?? null}
          onSelect={(o) => {
            setSelectedOwner(o);
            setLastFetchResult(null);
          }}
          loading={loadingOwners}
          error={ownersError}
          onRetry={() => void loadOwners()}
          meta={ownersMeta}
        />
        <div className="kpi-performance-page__detail-stack">
          {selectedOwner ? (
            <>
              <section className="kpi-performance-page__detail-card">
                <div
                  className="kpi-performance-page__detail-header"
                  data-testid="kpi-performance-detail-header"
                >
                  <div className="kpi-performance-page__detail-copy">
                    <h2 className="kpi-performance-page__owner-title">
                      {selectedOwner.owner_name}
                    </h2>
                    <p className="kpi-performance-page__detail-subtitle">
                      {selectedOwner.org_unit} · {currentPeriodLabel}
                    </p>
                  </div>
                  <div className="kpi-performance-page__detail-actions">
                    {periodSummary ? (
                      <div className="kpi-performance-page__period-badge">
                        <CalendarOutlined className="kpi-performance-page__period-badge-icon" />
                        <Text strong className="kpi-performance-page__period-badge-text">
                          {periodSummary.period_label}
                        </Text>
                        <Text type="secondary" className="kpi-performance-page__period-badge-range">
                          ({periodSummary.period_start_date} ~ {periodSummary.period_end_date})
                        </Text>
                      </div>
                    ) : null}
                    <Button icon={<SettingOutlined aria-hidden="true" />} onClick={handleAddMetric}>
                      管理指标
                    </Button>
                  </div>
                </div>
              </section>
              <MetricTable
                metrics={metrics}
                loading={loadingMetrics}
                onRefresh={() => void loadMetrics()}
                onAddMetric={handleAddMetric}
                onEditMetricDef={handleEditMetricDef}
                valueAsOfDate={formatDate(asOfDate)}
                onFullEdit={handleOpenEditModal}
                backendSummary={
                  periodSummary
                    ? {
                        totalWeight: periodSummary.total_weight,
                        totalScore: periodSummary.total_score,
                      }
                    : null
                }
              />
            </>
          ) : (
            <PageStateSurface
              variant="empty"
              className="kpi-performance-page__empty-card kpi-performance-page__empty-state"
              testId="kpi-performance-empty-state"
            >
              <TeamOutlined className="kpi-performance-page__empty-icon" />
              <p className="kpi-performance-page__empty-title">请选择考核对象</p>
              <p className="kpi-performance-page__empty-description">
                从左侧列表选择部室，查看绩效指标明细
              </p>
            </PageStateSurface>
          )}
        </div>
      </div>

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
