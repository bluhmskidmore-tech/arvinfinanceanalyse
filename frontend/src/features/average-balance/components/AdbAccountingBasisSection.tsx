import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import type {
  AdbAccountingBasisDailyAvg,
  AdbAccountingBasisDailyAvgTrendItem,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import AdbAccountingBasisTrendChart from "./AdbAccountingBasisTrendChart";

import "./AverageBalanceView.css";

const YI = 100_000_000;

type Row = {
  key: string;
  basis_bucket: string;
  daily_avg_yi: number | null;
  daily_avg_pct: number | null;
};

const SQL_LIKE_PREFIX_PATTERN = /^\d+%$/;

/**
 * 控制项显示层清洗：后端把 SQL LIKE 前缀模式（如 "142%"）直出，
 * 尾部 % 是通配符而非百分比。全部条目均为前缀模式时读作「科目前缀 142 / …」，
 * 原始模式收进 title；出现未知形态则整组原样透出（不猜业务含义）。
 */
function describeAccountingControls(controls: string[]): { text: string; title?: string } {
  const allPrefixPatterns =
    controls.length > 0 && controls.every((item) => SQL_LIKE_PREFIX_PATTERN.test(item));
  if (!allPrefixPatterns) {
    return { text: `控制项：${controls.join("；")}` };
  }
  return {
    text: `控制项：科目前缀 ${controls.map((item) => item.replace(/%$/, "")).join(" / ")}`,
    title: `原始匹配模式（SQL LIKE）：${controls.join("；")}`,
  };
}

function buildSnapshotRows(snapshot: AdbAccountingBasisDailyAvg): Row[] {
  return snapshot.rows.map((r, i) => ({
    key: `${r.basis_bucket}-${i}`,
    basis_bucket: r.basis_bucket || EM_DASH,
    daily_avg_yi:
      r.daily_avg_balance === null || r.daily_avg_balance === undefined
        ? null
        : r.daily_avg_balance / YI,
    daily_avg_pct: r.daily_avg_pct,
  }));
}

const snapshotColumns: ColumnsType<Row> = [
  { title: "分桶", dataIndex: "basis_bucket", key: "basis_bucket" },
  {
    title: "日均（亿元）",
    dataIndex: "daily_avg_yi",
    key: "daily_avg_yi",
    align: "right",
    render: (v: number | null) =>
      v === null || v === undefined || Number.isNaN(v) ? EM_DASH : v.toFixed(2),
  },
  {
    title: "占比（%）",
    dataIndex: "daily_avg_pct",
    key: "daily_avg_pct",
    align: "right",
    render: (v: number | null) => (v === null || v === undefined ? EM_DASH : `${v.toFixed(2)}%`),
  },
];

type AdbAccountingBasisSectionProps = {
  /** 区间末附近一日的分桶结构（与 comparison 同包）。 */
  snapshot?: AdbAccountingBasisDailyAvg;
  /** 按日或按月的分桶序列（后端非空时展示）。 */
  trend?: AdbAccountingBasisDailyAvgTrendItem[];
  titleSuffix?: string;
};

/**
 * IFRS9 会计分桶日均：仅展示后端已算字段，不在前端重算正式口径。
 */
export default function AdbAccountingBasisSection({
  snapshot,
  trend,
  titleSuffix = "",
}: AdbAccountingBasisSectionProps) {
  if (!snapshot && !(trend && trend.length)) return null;

  const title = titleSuffix
    ? `会计计量分桶 · 日均结构（${titleSuffix}）`
    : "会计计量分桶 · 日均结构";

  return (
    <section className="adb-panel" data-testid="adb-accounting-basis-section">
      <div className="adb-subhead">{title}</div>
      <div className="adb-note">
        与「债券+同业」大类日均并列阅读；分桶口径以后端 rule_version / source_version 为准。
      </div>
      {snapshot && snapshot.rows.length > 0 ? (
        <div>
          <div className="adb-subhead">
            参考日 {snapshot.report_date || EM_DASH}
            {snapshot.currency_basis ? ` · ${snapshot.currency_basis}` : ""}
          </div>
          {snapshot.accounting_controls.length > 0 ? (
            <div className="adb-note" title={describeAccountingControls(snapshot.accounting_controls).title}>
              {describeAccountingControls(snapshot.accounting_controls).text}
            </div>
          ) : null}
          <Table<Row>
            size="small"
            pagination={false}
            rowKey={(r) => r.key}
            columns={snapshotColumns}
            dataSource={buildSnapshotRows(snapshot)}
          />
        </div>
      ) : null}
      {trend && trend.length > 1 ? (
        <div data-testid="adb-accounting-basis-trend-chart">
          <div className="adb-subhead">分桶日均走势（亿元）</div>
          <AdbAccountingBasisTrendChart trend={trend} />
        </div>
      ) : null}
    </section>
  );
}
