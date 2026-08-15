import { Alert, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type {
  AdbInsightsWindow,
  AdbScaleAttribution,
  AdbScaleContributionRow,
} from "../../../api/contracts";
import { EM_DASH, formatYi } from "../../../utils/format";
import AdbKpiStrip, { type AdbKpiStripItem } from "./AdbKpiStrip";
import AdbSectionHead from "./AdbSectionHead";
import { formatAlreadyPercent, kpiToneForSign, toneClassForSign } from "./adbDeepAnalysisFormat";

import "./AverageBalanceView.css";

type AdbScaleAttributionPanelProps = {
  qoq: AdbScaleAttribution | null;
  yoy: AdbScaleAttribution | null;
  qoqWindow: AdbInsightsWindow;
  yoyWindow: AdbInsightsWindow;
};

function buildContributionColumns(): ColumnsType<AdbScaleContributionRow> {
  return [
    { title: "分类", dataIndex: "category", key: "category", ellipsis: true },
    {
      title: "本期日均(亿元)",
      dataIndex: "current_avg",
      key: "current_avg",
      align: "right",
      render: (value: number | null) => formatYi(value, false),
    },
    {
      title: "上期日均(亿元)",
      dataIndex: "prior_avg",
      key: "prior_avg",
      align: "right",
      render: (value: number | null) => formatYi(value, false),
    },
    {
      title: "变动(亿元)",
      dataIndex: "delta",
      key: "delta",
      align: "right",
      render: (value: number) => <span className={toneClassForSign(value)}>{formatYi(value, true)}</span>,
    },
    {
      title: "贡献率(%)",
      dataIndex: "contribution_pct",
      key: "contribution_pct",
      align: "right",
      render: (value: number | null) => (
        <span className={toneClassForSign(value)}>{formatAlreadyPercent(value, true)}</span>
      ),
    },
  ];
}

function ComparisonBlock({
  testKey,
  label,
  window,
  attribution,
}: {
  testKey: string;
  label: string;
  window: AdbInsightsWindow;
  attribution: AdbScaleAttribution | null;
}) {
  const columns = buildContributionColumns();
  const periodLabel = testKey === "yoy" ? "同比" : "环比";

  if (!window.available) {
    return (
      <div className="adb-panel" data-testid={`adb-scale-block-${testKey}`}>
        <div className="adb-subhead">{label}</div>
        <Alert
          type="info"
          showIcon
          message={`对比期无数据（${window.start_date || EM_DASH}～${window.end_date || EM_DASH}）`}
        />
      </div>
    );
  }

  if (!attribution) {
    return (
      <div className="adb-panel" data-testid={`adb-scale-block-${testKey}`}>
        <div className="adb-subhead">{label}</div>
        <p className="adb-note">{EM_DASH}</p>
      </div>
    );
  }

  const kpiItems: AdbKpiStripItem[] = [
    {
      key: "assets-delta",
      label: "资产日均变动",
      value: formatYi(attribution.side_totals.assets.delta, true),
      detail: `${periodLabel} ${formatAlreadyPercent(attribution.side_totals.assets.delta_pct, true)}`,
      tone: kpiToneForSign(attribution.side_totals.assets.delta),
    },
    {
      key: "liabilities-delta",
      label: "负债日均变动",
      value: formatYi(attribution.side_totals.liabilities.delta, true),
      detail: `${periodLabel} ${formatAlreadyPercent(attribution.side_totals.liabilities.delta_pct, true)}`,
      tone: kpiToneForSign(attribution.side_totals.liabilities.delta),
    },
  ];

  return (
    <div className="adb-panel" data-testid={`adb-scale-block-${testKey}`}>
      <div className="adb-subhead">{label}</div>
      <AdbKpiStrip columns={2} items={kpiItems} />
      <div className="adb-table-group">
        <div className="adb-subhead">资产贡献（按|变动|降序）</div>
        <Table<AdbScaleContributionRow>
          size="small"
          pagination={false}
          rowKey={(row) => `asset-${row.category}`}
          columns={columns}
          dataSource={attribution.asset_contributions}
          locale={{ emptyText: "暂无数据" }}
        />
      </div>
      <div className="adb-table-group">
        <div className="adb-subhead">负债贡献（按|变动|降序）</div>
        <Table<AdbScaleContributionRow>
          size="small"
          pagination={false}
          rowKey={(row) => `liability-${row.category}`}
          columns={columns}
          dataSource={attribution.liability_contributions}
          locale={{ emptyText: "暂无数据" }}
        />
      </div>
    </div>
  );
}

/**
 * 规模变动归因（环比/同比）：只格式化后端已计算好的分类贡献结果，
 * 闭合性（Σ分类变动=总变动）由后端保证，前端不重算。
 */
export default function AdbScaleAttributionPanel({
  qoq,
  yoy,
  qoqWindow,
  yoyWindow,
}: AdbScaleAttributionPanelProps) {
  return (
    <section className="adb-sec" data-testid="adb-scale-attribution-panel">
      <AdbSectionHead
        title="规模变动归因（环比/同比）"
        meta="贡献率=分类变动 / |总变动| ×100"
      />
      <p className="adb-note">
        口径：稀疏观测先沿用 comparison
        样本补齐，再按各区间自身日历天数计算；Σ分类变动=总变动（后端闭合性保证），本表仅展示归因结果。
      </p>
      <div className="adb-two-col">
        <ComparisonBlock testKey="qoq" label="环比（QoQ）" window={qoqWindow} attribution={qoq} />
        <ComparisonBlock testKey="yoy" label="同比（YoY）" window={yoyWindow} attribution={yoy} />
      </div>
    </section>
  );
}
