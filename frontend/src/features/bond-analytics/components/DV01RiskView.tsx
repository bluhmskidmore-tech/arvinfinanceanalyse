import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Radio, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useApiClient } from "../../../api/client";
import type {
  DV01MovementAttributionItem,
  DV01MovementBondItem,
  DV01ReconciliationRow,
  DV01ShockScenario,
  DV01TenorBucket,
  DV01TopBondItem,
  DV01TopIssuerItem,
  Numeric,
} from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type {
  BondAnalyticsDV01AccountingClassFilter,
  DV01MovementResponse,
  DV01ReconciliationResponse,
  DV01RiskResponse,
} from "../types";
import { formatPct, formatYi } from "../utils/formatters";
import { SectionLead } from "./SectionLead";
import styles from "./DV01RiskView.module.css";

const DEFAULT_SHOCK_BPS = "1,10,25,50";
const TOP_N_OPTIONS = [10, 20, 30, 50, 100] as const;

type DV01AccountingOption = {
  label: string;
  value: BondAnalyticsDV01AccountingClassFilter;
};

const ACCOUNTING_CLASS_OPTIONS: DV01AccountingOption[] = [
  { label: "AC", value: "AC" },
  { label: "OCI", value: "OCI" },
  { label: "TPL", value: "TPL" },
  { label: "全部", value: "all" },
];

interface Props {
  reportDate: string;
}

function formatNumeric(value: Numeric | null | undefined): string {
  return value?.display || "—";
}

function formatMoneyYi(value: Numeric | null | undefined): string {
  return value ? formatYi(value) : "—";
}

function formatSignedMoneyYi(value: Numeric | null | undefined): string {
  if (!value) return "—";
  const raw = bondNumericRaw(value);
  if (!Number.isFinite(raw)) return value.display || "—";
  const absYi = Math.abs(raw) / 100_000_000;
  const sign = raw > 0 ? "+" : raw < 0 ? "-" : "";
  return `${sign}${absYi.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 亿`;
}

function formatDurationYears(value: Numeric | null | undefined): string {
  const display = formatNumeric(value);
  return display === "—" ? display : `${display} 年`;
}

function formatCount(value: number): string {
  return value.toLocaleString("zh-CN");
}

function nullableText(value: string | null | undefined): string {
  return value?.trim() || "—";
}

function hasDv01RiskData(data: DV01RiskResponse): boolean {
  return (
    data.position_count > 0 ||
    data.tenor_buckets.length > 0 ||
    data.top_bonds.length > 0 ||
    data.top_issuers.length > 0
  );
}

function rowMatchesSearch(row: DV01ReconciliationRow, search: string): boolean {
  const normalized = search.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [row.instrument_code, row.instrument_name, row.issuer_name]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

const shockColumns: ColumnsType<DV01ShockScenario> = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  {
    title: "利率冲击",
    dataIndex: "shock_bp",
    key: "shock_bp",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "估算损益影响",
    dataIndex: "estimated_pnl",
    key: "estimated_pnl",
    render: formatSignedMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const tenorColumns: ColumnsType<DV01TenorBucket> = [
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket" },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01 占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "加权久期",
    dataIndex: "face_weighted_modified_duration",
    key: "face_weighted_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "持仓数",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const topBondColumns: ColumnsType<DV01TopBondItem> = [
  { title: "代码", dataIndex: "instrument_code", key: "instrument_code" },
  {
    title: "名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
  },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
  },
  { title: "评级", dataIndex: "rating", key: "rating", render: nullableText },
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket" },
  { title: "分类", dataIndex: "accounting_class", key: "accounting_class" },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "修正久期",
    dataIndex: "modified_duration",
    key: "modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const topIssuerColumns: ColumnsType<DV01TopIssuerItem> = [
  { title: "发行人", dataIndex: "issuer_name", key: "issuer_name" },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "加权久期",
    dataIndex: "face_weighted_modified_duration",
    key: "face_weighted_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "持仓数",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const reconciliationColumns: ColumnsType<DV01ReconciliationRow> = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code", fixed: "left", width: 120 },
  {
    title: "债券名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
    width: 160,
  },
  { title: "会计分类", dataIndex: "accounting_class", key: "accounting_class", width: 90 },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
    width: 140,
  },
  { title: "评级", dataIndex: "rating", key: "rating", render: nullableText, width: 80 },
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket", width: 90 },
  {
    title: "面值",
    dataIndex: "face_value",
    key: "face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "修正久期",
    dataIndex: "modified_duration",
    key: "modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
  {
    title: "DV01",
    dataIndex: "dv01",
    key: "dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "DV01 占比",
    dataIndex: "dv01_share",
    key: "dv01_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
  { title: "source_version", dataIndex: "source_version", key: "source_version", width: 150 },
  { title: "rule_version", dataIndex: "rule_version", key: "rule_version", width: 130 },
  { title: "trace_id", dataIndex: "trace_id", key: "trace_id", width: 140 },
];

const movementAttributionColumns: ColumnsType<DV01MovementAttributionItem> = [
  { title: "解释项", dataIndex: "driver_label", key: "driver_label" },
  {
    title: "DV01 变动",
    dataIndex: "dv01_delta",
    key: "dv01_delta",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "变动占比",
    dataIndex: "dv01_delta_share",
    key: "dv01_delta_share",
    render: formatPct,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "涉及债券",
    dataIndex: "position_count",
    key: "position_count",
    render: formatCount,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const movementBondColumns: ColumnsType<DV01MovementBondItem> = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code", fixed: "left", width: 120 },
  {
    title: "债券名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
    width: 160,
  },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
    width: 140,
  },
  { title: "原因", dataIndex: "reason_label", key: "reason_label", width: 130 },
  { title: "上期分类", dataIndex: "previous_accounting_class", key: "previous_accounting_class", render: nullableText, width: 90 },
  { title: "本期分类", dataIndex: "current_accounting_class", key: "current_accounting_class", render: nullableText, width: 90 },
  {
    title: "上期 DV01",
    dataIndex: "previous_dv01",
    key: "previous_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期 DV01",
    dataIndex: "current_dv01",
    key: "current_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "DV01 变动",
    dataIndex: "dv01_delta",
    key: "dv01_delta",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期面值",
    dataIndex: "current_face_value",
    key: "current_face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期久期",
    dataIndex: "current_modified_duration",
    key: "current_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
];

const methodologyCheckColumns: ColumnsType<DV01MovementBondItem> = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code", fixed: "left", width: 120 },
  {
    title: "债券名称",
    dataIndex: "instrument_name",
    key: "instrument_name",
    render: nullableText,
    width: 160,
  },
  {
    title: "发行人",
    dataIndex: "issuer_name",
    key: "issuer_name",
    render: nullableText,
    width: 140,
  },
  {
    title: "系统 DV01",
    dataIndex: "current_dv01",
    key: "current_dv01",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "面值久期估算",
    dataIndex: "estimated_dv01_from_face_duration",
    key: "estimated_dv01_from_face_duration",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 140,
  },
  {
    title: "估算差异",
    dataIndex: "dv01_estimate_gap",
    key: "dv01_estimate_gap",
    render: formatNumeric,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期面值",
    dataIndex: "current_face_value",
    key: "current_face_value",
    render: formatMoneyYi,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 120,
  },
  {
    title: "本期久期",
    dataIndex: "current_modified_duration",
    key: "current_modified_duration",
    render: formatDurationYears,
    onCell: () => ({ style: tabularNumsStyle }),
    width: 110,
  },
];

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.kpiCard}>
      <span className={styles.kpiLabel}>{label}</span>
      <span className={styles.kpiValue}>{value}</span>
    </div>
  );
}

function DV01MovementPanel({
  data,
  isLoading,
  isError,
  error,
}: {
  data: DV01MovementResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}) {
  return (
    <section className={styles.panel} data-testid="dv01-movement-panel">
      <div className={styles.reconciliationHeader}>
        <div>
          <h3 className={styles.panelTitle}>较上一报告日变化</h3>
          <div className={styles.reconciliationMeta}>
            上一报告日 {data?.previous_report_date ?? "—"} · 本期 DV01 {formatNumeric(data?.current_total_dv01)} · 上期 DV01{" "}
            {formatNumeric(data?.previous_total_dv01)} · 变动 {formatNumeric(data?.delta_dv01)}
          </div>
        </div>
        <span className={styles.reconciliationCount}>
          本期 {formatCount(data?.current_position_count ?? 0)} / 上期 {formatCount(data?.previous_position_count ?? 0)}
        </span>
      </div>

      {isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 变化加载失败"
          description={error instanceof Error ? error.message : String(error)}
        />
      ) : isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-movement-loading">
          <Spin />
        </div>
      ) : !data || data.source_status === "empty" ? (
        <div className={styles.emptyState} data-testid="dv01-movement-empty-state">
          该报告日/分类暂无可对比的 DV01 变化数据
        </div>
      ) : (
        <>
          {data.warnings.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              message="DV01 变化提示"
              description={data.warnings.map((warning, index) => (
                <div key={index}>{warning}</div>
              ))}
            />
          ) : null}
          <div className={styles.movementSummaryGrid}>
            <KpiCard label="本期总 DV01" value={formatNumeric(data.current_total_dv01)} />
            <KpiCard label="上期总 DV01" value={formatNumeric(data.previous_total_dv01)} />
            <KpiCard label="DV01 变动" value={formatNumeric(data.delta_dv01)} />
            <KpiCard label="本期加权久期" value={formatDurationYears(data.current_face_weighted_modified_duration)} />
          </div>
          <Table<DV01MovementAttributionItem>
            data-testid="dv01-movement-attribution-table"
            dataSource={data.attribution}
            columns={movementAttributionColumns}
            rowKey={(row) => row.driver_key}
            pagination={false}
            size="small"
            scroll={{ x: true }}
          />
          <div className={styles.twoColumnGrid}>
            <section className={styles.subPanel}>
              <h4 className={styles.subPanelTitle}>异常单券</h4>
              <Table<DV01MovementBondItem>
                data-testid="dv01-movement-anomaly-table"
                dataSource={data.anomaly_bonds}
                columns={movementBondColumns}
                rowKey={(row) => `anomaly-${row.instrument_code}`}
                pagination={false}
                size="small"
                scroll={{ x: 1300, y: 360 }}
              />
            </section>
            <section className={styles.subPanel}>
              <h4 className={styles.subPanelTitle}>口径核验</h4>
              <Table<DV01MovementBondItem>
                data-testid="dv01-methodology-check-table"
                dataSource={data.methodology_checks}
                columns={methodologyCheckColumns}
                rowKey={(row) => `methodology-${row.instrument_code}`}
                pagination={false}
                size="small"
                scroll={{ x: 1200, y: 360 }}
              />
            </section>
          </div>
        </>
      )}
    </section>
  );
}

function DV01ReconciliationPanel({
  data,
  isLoading,
  isError,
  error,
  search,
  onSearchChange,
}: {
  data: DV01ReconciliationResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  search: string;
  onSearchChange: (value: string) => void;
}) {
  const rows = data?.rows ?? [];
  const filteredRows = rows.filter((row) => rowMatchesSearch(row, search));

  return (
    <section className={styles.panel} data-testid="dv01-reconciliation-panel">
      <div className={styles.reconciliationHeader}>
        <div>
          <h3 className={styles.panelTitle}>单券明细对账</h3>
          <div className={styles.reconciliationMeta}>
            后端合计：面值 {formatMoneyYi(data?.total_face_value)} · 市值 {formatMoneyYi(data?.total_market_value)} · 久期{" "}
            {formatDurationYears(data?.face_weighted_modified_duration)} · DV01 {formatNumeric(data?.total_dv01)} · 持仓{" "}
            {formatCount(data?.position_count ?? 0)}
          </div>
        </div>
        <div className={styles.reconciliationControls}>
          <span className={styles.reconciliationCount}>
            当前筛选 {formatCount(filteredRows.length)} / {formatCount(rows.length)}
          </span>
          <input
            className={styles.searchInput}
            data-testid="dv01-reconciliation-search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="搜索代码/名称/发行人"
          />
        </div>
      </div>

      {isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 明细对账加载失败"
          description={error instanceof Error ? error.message : String(error)}
        />
      ) : isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-reconciliation-loading">
          <Spin />
        </div>
      ) : !data || rows.length === 0 ? (
        <div className={styles.emptyState} data-testid="dv01-reconciliation-empty-state">
          该报告日/分类暂无债券 DV01 明细数据
        </div>
      ) : (
        <Table<DV01ReconciliationRow>
          data-testid="dv01-reconciliation-table"
          dataSource={filteredRows}
          columns={reconciliationColumns}
          rowKey={(row) => `${row.report_date}-${row.instrument_code}-${row.accounting_class}`}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          size="small"
          scroll={{ x: 1600, y: 520 }}
        />
      )}
    </section>
  );
}

export function DV01RiskView({ reportDate }: Props) {
  const client = useApiClient();
  const [accountingClass, setAccountingClass] =
    useState<BondAnalyticsDV01AccountingClassFilter>("OCI");
  const [topN, setTopN] = useState<number>(20);
  const [reconciliationSearch, setReconciliationSearch] = useState("");

  const queryOptions = useMemo(
    () => ({
      accountingClass,
      topN,
      shockBps: DEFAULT_SHOCK_BPS,
    }),
    [accountingClass, topN],
  );

  const query = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Risk(
      client.mode,
      reportDate,
      accountingClass,
      topN,
      DEFAULT_SHOCK_BPS,
    ),
    queryFn: () => client.getBondAnalyticsDv01Risk(reportDate, queryOptions),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const reconciliationQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Reconciliation(
      client.mode,
      reportDate,
      accountingClass,
    ),
    queryFn: () =>
      client.getBondAnalyticsDv01Reconciliation(reportDate, {
        accountingClass,
      }),
    enabled: Boolean(reportDate),
    retry: false,
  });
  const movementQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsDv01Movement(
      client.mode,
      reportDate,
      accountingClass,
      topN,
    ),
    queryFn: () =>
      client.getBondAnalyticsDv01Movement(reportDate, {
        accountingClass,
        topN,
      }),
    enabled: Boolean(reportDate),
    retry: false,
  });

  const data = query.data?.result ?? null;
  const hasData = data ? hasDv01RiskData(data) : false;
  const reconciliationData = reconciliationQuery.data?.result ?? null;
  const movementData = movementQuery.data?.result ?? null;

  if (!reportDate) {
    return null;
  }

  return (
    <div className={styles.shell} data-testid="dv01-risk-view">
      <SectionLead
        eyebrow="DV01 风险"
        title="当前报告日利率风险横截面"
        description="读取后端 formal 债券分析事实表中的行级 DV01，展示会计分类、利率冲击、期限桶、债券和发行人集中度；页面不重新计算 DV01。"
        testId="dv01-risk-shell-lead"
      />

      <div className={styles.toolbar}>
        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>会计分类</span>
          <Radio.Group
            data-testid="dv01-risk-accounting-class"
            optionType="button"
            buttonStyle="solid"
            options={ACCOUNTING_CLASS_OPTIONS}
            value={accountingClass}
            onChange={(event) =>
              setAccountingClass(event.target.value as BondAnalyticsDV01AccountingClassFilter)
            }
          />
        </div>
        <div className={styles.controlGroup}>
          <label className={styles.controlLabel} htmlFor="dv01-risk-topn">
            Top N
          </label>
          <select
            id="dv01-risk-topn"
            className={styles.select}
            data-testid="dv01-risk-topn"
            value={topN}
            onChange={(event) => setTopN(Number(event.target.value))}
          >
            {TOP_N_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      {query.isLoading && !data ? (
        <div className={styles.loadingState} data-testid="dv01-risk-loading">
          <Spin />
        </div>
      ) : query.isError ? (
        <Alert
          type="error"
          showIcon
          message="DV01 风险加载失败"
          description={query.error instanceof Error ? query.error.message : String(query.error)}
        />
      ) : !data ? null : (
        <>
          {data.warnings.length > 0 ? (
            <Alert
              type="warning"
              showIcon
              message="提示"
              description={data.warnings.map((warning, index) => (
                <div key={index}>{warning}</div>
              ))}
            />
          ) : null}

          <div className={styles.kpiGrid}>
            <KpiCard label="总面值" value={formatMoneyYi(data.total_face_value)} />
            <KpiCard label="总市值" value={formatMoneyYi(data.total_market_value)} />
            <KpiCard
              label="面值加权修正久期"
              value={formatDurationYears(data.face_weighted_modified_duration)}
            />
            <KpiCard label="总 DV01" value={formatNumeric(data.total_dv01)} />
            <KpiCard label="持仓数" value={formatCount(data.position_count)} />
          </div>

          {!hasData ? (
            <div className={styles.emptyState} data-testid="dv01-risk-empty-state">
              该报告日/分类暂无债券 DV01 数据
            </div>
          ) : (
            <>
              {data.shock_scenarios.length > 0 ? (
                <section className={styles.panel}>
                  <h3 className={styles.panelTitle}>利率冲击表</h3>
                  <Table<DV01ShockScenario>
                    data-testid="dv01-risk-shocks-table"
                    dataSource={data.shock_scenarios}
                    columns={shockColumns}
                    rowKey={(row) => row.scenario_name}
                    pagination={false}
                    size="small"
                    scroll={{ x: true }}
                  />
                </section>
              ) : null}

              <section className={styles.panel}>
                <h3 className={styles.panelTitle}>期限桶 DV01</h3>
                <Table<DV01TenorBucket>
                  data-testid="dv01-risk-tenor-table"
                  dataSource={data.tenor_buckets}
                  columns={tenorColumns}
                  rowKey={(row) => row.tenor_bucket}
                  pagination={false}
                  size="small"
                  scroll={{ x: true }}
                />
              </section>

              <div className={styles.twoColumnGrid}>
                <section className={styles.panel}>
                  <h3 className={styles.panelTitle}>Top 债券</h3>
                  <Table<DV01TopBondItem>
                    data-testid="dv01-risk-top-bonds-table"
                    dataSource={data.top_bonds}
                    columns={topBondColumns}
                    rowKey={(row) => row.instrument_code}
                    pagination={false}
                    size="small"
                    scroll={{ x: true, y: 420 }}
                  />
                </section>

                <section className={styles.panel}>
                  <h3 className={styles.panelTitle}>Top 发行人</h3>
                  <Table<DV01TopIssuerItem>
                    data-testid="dv01-risk-top-issuers-table"
                    dataSource={data.top_issuers}
                    columns={topIssuerColumns}
                    rowKey={(row) => row.issuer_name}
                    pagination={false}
                    size="small"
                    scroll={{ x: true, y: 420 }}
                  />
                </section>
              </div>
            </>
          )}

          <DV01MovementPanel
            data={movementData}
            isLoading={movementQuery.isLoading}
            isError={movementQuery.isError}
            error={movementQuery.error}
          />

          <DV01ReconciliationPanel
            data={reconciliationData}
            isLoading={reconciliationQuery.isLoading}
            isError={reconciliationQuery.isError}
            error={reconciliationQuery.error}
            search={reconciliationSearch}
            onSearchChange={setReconciliationSearch}
          />
        </>
      )}
    </div>
  );
}

export default DV01RiskView;
