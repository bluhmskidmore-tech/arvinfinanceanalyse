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
import { Alert, Button, DatePicker, Select, Typography, message } from "antd";
import dayjs from "dayjs";

import type {
  KpiFetchAndRecalcResponse,
  KpiMetric,
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
import { observeKpiWrite, type KpiStoppedWrite, type PendingKpiWrite } from "../components/pendingKpiWrite";
import { MetricTable } from "../components/MetricTable";
import { OwnerList } from "../components/OwnerList";
import "./KpiPerformancePage.css";

const { Text } = Typography;

type PeriodType = "DAILY" | "MONTH" | "QUARTER" | "YEAR";
type PendingRecalc = { contextKey: string; handedOff: boolean; handoff: () => void };

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
  const [messageApi, messageHolder] = message.useMessage();
  const [year, setYear] = React.useState<number>(() => new Date().getFullYear());
  const [asOfDate, setAsOfDate] = React.useState<Date>(() => new Date());
  const [owners, setOwners] = React.useState<KpiOwner[]>([]);
  const [ownersError, setOwnersError] = React.useState<Error | null>(null);
  const [ownersMeta, setOwnersMeta] = React.useState<KpiOwnerAuthorityMeta | null>(null);
  const [selectedOwner, setSelectedOwner] = React.useState<KpiOwner | null>(null);
  const [metrics, setMetrics] = React.useState<KpiMetricWithValue[]>([]);
  const [metricsContextKey, setMetricsContextKey] = React.useState<string | null>(null);

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
  const [managingMetric, setManagingMetric] = React.useState<KpiMetric | null>(null);
  const editContextKey = `${year}:${selectedOwner?.owner_id ?? "none"}:${periodType}:${periodValue}:${formatDate(asOfDate)}`;
  const currentPeriodLabel =
    periodType === "DAILY"
      ? `截止 ${formatDateCN(asOfDate)}`
      : periodType === "MONTH"
        ? `${year}年${periodValue}月`
        : periodType === "QUARTER"
          ? `${year}年Q${periodValue}`
          : `${year}年度汇总`;
  const metricsMatchContext = metricsContextKey === editContextKey;
  const contextSeqRef = React.useRef(0);
  const definitionRequestSeqRef = React.useRef(0);
  const fetchPendingRef = React.useRef<PendingRecalc | null>(null);
  const writeScopeKey = `${selectedOwner?.year ?? year}:${selectedOwner?.owner_id ?? "none"}`;
  const [stoppedWrites, setStoppedWrites] = React.useState<Record<string, KpiStoppedWrite>>({});
  const stoppedWriteSeq = React.useRef(Date.now());
  const stoppedWriteMounted = React.useRef(true);
  const currentStoppedWrite = stoppedWrites[writeScopeKey];
  const writePending = Boolean(currentStoppedWrite && !currentStoppedWrite.outcome?.confirmed && !currentStoppedWrite.released);
  const stoppedWriteMatchesContext = currentStoppedWrite?.contextKey === editContextKey;
  React.useEffect(() => {
    stoppedWriteMounted.current = true;
    return () => { stoppedWriteMounted.current = false; };
  }, []);


  React.useEffect(() => {
    contextSeqRef.current += 1;
    definitionRequestSeqRef.current += 1;
    setEditModalOpen(false);
    setEditingMetric(null);
    setMetricManageOpen(false);
    setManagingMetric(null);
    setBatchPasteOpen(false);
    setLastFetchResult(null);
    setFetchLoading(false);
    const pendingRecalc = fetchPendingRef.current;
    if (pendingRecalc && pendingRecalc.contextKey !== editContextKey) {
      pendingRecalc.handoff();
      if (fetchPendingRef.current === pendingRecalc) fetchPendingRef.current = null;
    }
    setStoppedWrites((old) => Object.values(old).some((write) => write.readbackDone)
      ? Object.fromEntries(Object.entries(old).map(([scope, write]) => [scope, { ...write, readbackDone: false }]))
      : old);
    return () => {
      contextSeqRef.current += 1;
      definitionRequestSeqRef.current += 1;
    };
  }, [editContextKey]);

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
      messageApi.error("加载考核对象失败");
      setOwnersError(e instanceof Error ? e : new Error(String(e)));
      setOwnersMeta(null);
      setOwners([]);
    } finally {
      if (requestId === ownersRequestSeqRef.current) {
        setLoadingOwners(false);
      }
    }
  }, [client, year, messageApi]);

  const loadMetrics = React.useCallback(async () => {
    const requestId = ++metricsRequestSeqRef.current;
    setMetrics([]);
    setPeriodSummary(null);
    if (!selectedOwner) {
      setLoadingMetrics(false);
      return false;
    }
    setLoadingMetrics(true);
    try {
      if (periodType === "DAILY") {
        const response = await client.getKpiValues({
          owner_id: selectedOwner.owner_id,
          as_of_date: formatDate(asOfDate),
          include_trace: true,
        });
        if (requestId !== metricsRequestSeqRef.current) return false;
        setMetrics(response.metrics);
        setMetricsContextKey(editContextKey);
        setPeriodSummary(null);
      } else {
        const response = await client.getKpiValuesSummary({
          owner_id: selectedOwner.owner_id,
          year,
          period_type: periodType,
          period_value: periodType !== "YEAR" ? periodValue : undefined,
        });
        if (requestId !== metricsRequestSeqRef.current) return false;
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
        setMetricsContextKey(editContextKey);
      }
      return true;
    } catch (e) {
      if (requestId !== metricsRequestSeqRef.current) return false;
      console.error(e);
      messageApi.error("加载指标失败");
      setMetrics([]);
      setPeriodSummary(null);
      return false;
    } finally {
      if (requestId === metricsRequestSeqRef.current) {
        setLoadingMetrics(false);
      }
    }
  }, [client, selectedOwner, asOfDate, periodType, periodValue, year, editContextKey, messageApi]);

  React.useEffect(() => {
    void loadOwners();
  }, [loadOwners]);

  React.useEffect(() => {
    void loadMetrics();
    return () => { metricsRequestSeqRef.current += 1; };
  }, [loadMetrics]);

  const currentReadback = React.useRef({ context: editContextKey, refresh: loadMetrics });
  React.useEffect(() => { currentReadback.current = { context: editContextKey, refresh: loadMetrics }; }, [editContextKey, loadMetrics]);
  const handleUnconfirmedWrite = React.useCallback((write: PendingKpiWrite, notice?: string) => {
    if (!stoppedWriteMounted.current) return;
    const context = editContextKey;
    const scope = writeScopeKey;
    const id = ++stoppedWriteSeq.current;
    const contextLabel = `${selectedOwner?.owner_name ?? "未选择考核对象"} · ${currentPeriodLabel}`;
    setStoppedWrites((old) => {
      const previous = old[scope];
      const retainPrevious = previous && !previous.released && !previous.outcome?.confirmed;
      return {
        ...old,
        [scope]: retainPrevious
          ? { ...previous, id, writes: { ...previous.writes, [id]: undefined }, outcome: undefined, readbackDone: false,
            notice: [previous.notice, notice].filter((value, index, values) => value && values.indexOf(value) === index).join("；") || undefined }
          : { id, contextKey: context, contextLabel, notice, writes: { [id]: undefined } },
      };
    });
    void write.then((outcome) => {
      if (!stoppedWriteMounted.current) return;
      setStoppedWrites((old) => {
        const entry = old[scope];
        if (!entry || !(id in entry.writes)) return old;
        const writes = { ...entry.writes, [id]: outcome };
        const results = Object.values(writes);
        const combinedOutcome = results.some((result) => !result) ? undefined : {
          changed: results.some((result) => result?.changed),
          confirmed: results.every((result) => result?.confirmed),
          error: results.map((result) => result?.error).filter(Boolean).join("；") || undefined,
        };
        return { ...old, [scope]: { ...entry, writes, outcome: combinedOutcome, readbackDone: false } };
      });
      // The old write must never close a newly opened modal or refresh a different scope.
      if (outcome.changed && currentReadback.current.context === context) void currentReadback.current.refresh();
    });
  }, [editContextKey, writeScopeKey, selectedOwner, currentPeriodLabel]);

  const handleVerifyStoppedWrite = React.useCallback(async () => {
    if (!currentStoppedWrite || !stoppedWriteMatchesContext) return;
    const id = currentStoppedWrite?.id;
    const scope = writeScopeKey;
    const resultWasUnknown = Boolean(currentStoppedWrite?.outcome && !currentStoppedWrite.outcome.confirmed);
    if (id !== undefined) setStoppedWrites((old) => old[scope]?.id === id
      ? { ...old, [scope]: { ...old[scope], readbackDone: false, released: false } } : old);
    const pendingRecalc = fetchPendingRef.current;
    if (pendingRecalc?.contextKey === editContextKey) pendingRecalc.handoff();
    const readSucceeded = await loadMetrics();
    if (readSucceeded && resultWasUnknown && id !== undefined) setStoppedWrites((old) => old[scope]?.id === id
      ? { ...old, [scope]: { ...old[scope], readbackDone: true } } : old);
  }, [currentStoppedWrite, stoppedWriteMatchesContext, loadMetrics, writeScopeKey, editContextKey]);

  const handleFetchAndRecalc = React.useCallback(async () => {
    if (!selectedOwner || periodType !== "DAILY" || fetchPendingRef.current || writePending) return;
    const contextId = contextSeqRef.current;
    let write: PendingKpiWrite | undefined;
    const request: PendingRecalc = {
      contextKey: editContextKey,
      handedOff: false,
      handoff: () => {
        if (!write || request.handedOff) return;
        request.handedOff = true;
        handleUnconfirmedWrite(write, "抓取并重算请求结果未知，请核实后再操作。");
      },
    };
    fetchPendingRef.current = request;
    setFetchLoading(true);
    setLastFetchResult(null);
    try {
      const operation = client.fetchAndRecalcKpi(selectedOwner.owner_id, formatDate(asOfDate));
      write = observeKpiWrite(operation);
      const result = await operation;
      if (request.handedOff || contextId !== contextSeqRef.current) return;
      setLastFetchResult(result);
      const readSucceeded = await loadMetrics();
      if (request.handedOff || contextId !== contextSeqRef.current) return;
      if (readSucceeded) messageApi.success("抓取并重算已完成");
      else messageApi.warning("抓取并重算请求已成功，但当前页面刷新失败，请刷新核实数据。");
    } catch (e) {
      if (request.handedOff || contextId !== contextSeqRef.current) return;
      console.error(e);
      request.handoff();
      messageApi.error("抓取并重算结果尚未确认，请刷新核实。");
    } finally {
      if (fetchPendingRef.current === request) {
        fetchPendingRef.current = null;
        if (contextId === contextSeqRef.current) setFetchLoading(false);
      }
    }
  }, [client, selectedOwner, asOfDate, loadMetrics, periodType, writePending, messageApi, handleUnconfirmedWrite, editContextKey]);

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
      messageApi.error("导出失败");
    } finally {
      setExportLoading(false);
    }
  }, [client, year, selectedOwner, asOfDate, messageApi]);

  const handleOpenEditModal = React.useCallback((metric: KpiMetricWithValue) => {
    if (periodType !== "DAILY" && !metric.as_of_date) return;
    setEditingMetric(metric);
    setEditModalOpen(true);
  }, [periodType]);

  const handleCloseEditModal = React.useCallback(() => {
    setEditModalOpen(false);
    setEditingMetric(null);
  }, []);

  const handleAddMetric = React.useCallback(() => {
    definitionRequestSeqRef.current += 1;
    setMetricManageMode("create");
    setManagingMetric(null);
    setMetricManageOpen(true);
  }, []);

  const handleEditMetricDef = React.useCallback(async (metric: KpiMetricWithValue) => {
    const requestId = ++definitionRequestSeqRef.current;
    setMetricManageOpen(false);
    try {
      // 汇总行没有完整定义，不将其合成的来源、规则和空备注写回。
      const definition = await client.getKpiMetricById(metric.metric_id);
      if (requestId !== definitionRequestSeqRef.current) return;
      if (!selectedOwner || definition.metric_id !== metric.metric_id || definition.owner_id !== selectedOwner.owner_id || definition.year !== selectedOwner.year) {
        throw new Error("指标与当前考核对象不一致");
      }
      setMetricManageMode("edit");
      setManagingMetric(definition);
      setMetricManageOpen(true);
    } catch (error) {
      if (requestId !== definitionRequestSeqRef.current) return;
      messageApi.error(error instanceof Error ? error.message : "加载指标定义失败");
    }
  }, [client, selectedOwner, messageApi]);

  const handleCloseMetricManage = React.useCallback(() => {
    definitionRequestSeqRef.current += 1;
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

  const currentOwnerLabel = selectedOwner
    ? `${selectedOwner.owner_name} · ${selectedOwner.org_unit}`
    : "未选择考核对象";

  const ownerGateTitle = selectedOwner ? undefined : "请先在左侧选择考核对象";
  const dailyWriteGateTitle = ownerGateTitle ?? (periodType !== "DAILY" ? "请切换到日视图选择写入日期" : undefined);

  return (
    <div
      className="moss-page-v2-shell kpi-performance-page"
      data-moss-theme-scope="kpi"
      data-testid="kpi-performance-page"
    >
      {messageHolder}
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
              disabled={!selectedOwner || loadingMetrics || !metricsMatchContext || periodType !== "DAILY"}
              title={dailyWriteGateTitle}
              onClick={() => setBatchPasteOpen(true)}
            >
              批量导入
            </Button>
            <Button
              type="primary"
              icon={<SyncOutlined aria-hidden="true" />}
              loading={fetchLoading}
              disabled={!selectedOwner || periodType !== "DAILY" || writePending}
              title={dailyWriteGateTitle}
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

      {currentStoppedWrite ? (
        <Alert type={writePending || currentStoppedWrite.outcome?.error ? "warning" : "info"} showIcon
          message={writePending ? "写入结果尚未确认，请勿重复提交。"
            : currentStoppedWrite.released ? "已核实当前数据；原写入结果仍未知，请谨慎编辑。"
            : currentStoppedWrite.outcome?.changed ? "写入已返回成功结果，请核对最新数据。" : "写入未确认成功，请刷新核实后再操作。"}
          description={[`原提交口径：${currentStoppedWrite.contextLabel}`, currentStoppedWrite.outcome?.error, currentStoppedWrite.notice,
            !stoppedWriteMatchesContext ? "请回到原提交日期和视图后刷新核实。" : undefined,
            "刷新核实只读取数据，不会重新提交。未知请求仍可能有迟到写入。"].filter(Boolean).join("；")}
          action={<>
            <Button disabled={!stoppedWriteMatchesContext} loading={loadingMetrics} onClick={() => void handleVerifyStoppedWrite()}>刷新核实</Button>
            {stoppedWriteMatchesContext && currentStoppedWrite.outcome && !currentStoppedWrite.outcome.confirmed && currentStoppedWrite.readbackDone && !currentStoppedWrite.released ? (
              <Button onClick={() => setStoppedWrites((old) => ({ ...old, [writeScopeKey]: { ...old[writeScopeKey], released: true } }))}>已核实，继续编辑</Button>
            ) : null}
          </>}
        />
      ) : null}

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
                onChange={(v) => {
                  setSelectedOwner(null);
                  setYear(v);
                }}
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
                    {metricsMatchContext && periodSummary ? (
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
                key={editContextKey}
                metrics={metricsMatchContext ? metrics : []}
                loading={loadingMetrics}
                writeDisabled={writePending}
                onUnconfirmedWrite={handleUnconfirmedWrite}
                onRefresh={() => void loadMetrics()}
                onAddMetric={handleAddMetric}
                onEditMetricDef={handleEditMetricDef}
                valueAsOfDate={periodType === "DAILY" ? formatDate(asOfDate) : undefined}
                onFullEdit={handleOpenEditModal}
                backendSummary={
                  metricsMatchContext && periodSummary
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
        key={`value:${editContextKey}`}
        open={editModalOpen}
        onClose={handleCloseEditModal}
        metric={editingMetric}
        asOfDate={periodType === "DAILY" ? formatDate(asOfDate) : undefined}
        onSaveSuccess={handleSaveSuccess}
        onUnconfirmedWrite={handleUnconfirmedWrite}
        writePending={writePending}
      />

      <MetricManageModal
        key={`definition:${editContextKey}`}
        open={metricManageOpen}
        onClose={handleCloseMetricManage}
        mode={metricManageMode}
        metric={managingMetric}
        owner={selectedOwner}
        onSuccess={handleMetricManageSuccess}
        onUnconfirmedWrite={handleUnconfirmedWrite}
        writePending={writePending}
      />

      <BatchPasteModal
        key={`batch:${editContextKey}`}
        open={batchPasteOpen}
        onClose={() => setBatchPasteOpen(false)}
        owner={selectedOwner}
        asOfDate={formatDate(asOfDate)}
        metrics={metricsMatchContext ? metrics : []}
        onSuccess={handleBatchPasteSuccess}
        onUnconfirmedWrite={handleUnconfirmedWrite}
        writePending={writePending}
      />
    </div>
  );
}
