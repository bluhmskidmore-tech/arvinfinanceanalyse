import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Radio, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import { useApiClient } from "../../../api/client";
import type {
  DV01ShockScenario,
  DV01TenorBucket,
  DV01TopBondItem,
  DV01TopIssuerItem,
  Numeric,
} from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";
import { tabularNumsStyle } from "../../../theme/designSystem";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { BondAnalyticsDV01AccountingClassFilter, DV01RiskResponse } from "../types";
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

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={styles.kpiCard}>
      <span className={styles.kpiLabel}>{label}</span>
      <span className={styles.kpiValue}>{value}</span>
    </div>
  );
}

export function DV01RiskView({ reportDate }: Props) {
  const client = useApiClient();
  const [accountingClass, setAccountingClass] =
    useState<BondAnalyticsDV01AccountingClassFilter>("OCI");
  const [topN, setTopN] = useState<number>(20);

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

  const data = query.data?.result ?? null;
  const hasData = data ? hasDv01RiskData(data) : false;

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
        </>
      )}
    </div>
  );
}

export default DV01RiskView;
