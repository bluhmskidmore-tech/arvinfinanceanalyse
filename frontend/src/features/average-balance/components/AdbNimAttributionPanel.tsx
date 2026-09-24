import { Alert, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { AdbInsightsWindow, AdbNimAttribution, AdbNimSideAttribution } from "../../../api/contracts";
import { EM_DASH, formatBp, formatPercent } from "../../../utils/format";
import AdbKpiStrip, { type AdbKpiStripItem } from "./AdbKpiStrip";
import AdbSectionHead from "./AdbSectionHead";
import { formatAlreadyPercent, kpiToneForSign, toneClassForSign } from "./adbDeepAnalysisFormat";

import "./AverageBalanceView.css";

type AdbNimAttributionPanelProps = {
  nim: AdbNimAttribution | null;
  reason: string | null;
  qoqWindow: AdbInsightsWindow;
};

type NimCategoryRow = AdbNimSideAttribution["by_category"][number];

function buildByCategoryColumns(): ColumnsType<NimCategoryRow> {
  return [
    { title: "分类", dataIndex: "category", key: "category", ellipsis: true },
    {
      title: "占比(本期)",
      dataIndex: "share_current",
      key: "share_current",
      align: "right",
      render: (value: number | null) => formatPercent(value, false),
    },
    {
      title: "占比(上期)",
      dataIndex: "share_prior",
      key: "share_prior",
      align: "right",
      render: (value: number | null) => formatPercent(value, false),
    },
    {
      title: "利率(本期)",
      dataIndex: "rate_current",
      key: "rate_current",
      align: "right",
      render: (value: number | null) => formatAlreadyPercent(value, false),
    },
    {
      title: "利率(上期)",
      dataIndex: "rate_prior",
      key: "rate_prior",
      align: "right",
      render: (value: number | null) => formatAlreadyPercent(value, false),
    },
    {
      title: "利率效应(bp)",
      dataIndex: "rate_effect_bp",
      key: "rate_effect_bp",
      align: "right",
      render: (value: number) => <span className={toneClassForSign(value)}>{formatBp(value, true)}</span>,
    },
    {
      title: "结构效应(bp)",
      dataIndex: "mix_effect_bp",
      key: "mix_effect_bp",
      align: "right",
      render: (value: number) => <span className={toneClassForSign(value)}>{formatBp(value, true)}</span>,
    },
  ];
}

function unavailableMessage(reason: string | null): string {
  if (reason === "rate_unavailable") return "利率覆盖不足，无法计算NIM量价归因";
  if (reason === "comparison_unavailable") return "对比期无数据，无法计算NIM量价归因";
  if (reason === "insufficient_window") return "区间过短，无法计算NIM量价归因";
  return `NIM量价归因不可用（${EM_DASH}）`;
}

/**
 * NIM 量价归因（环比）：利率效应/结构效应/残差均为后端已算好的 bp 数值，
 * 前端仅格式化展示，残差原样披露（不隐藏、不归零）。
 */
export default function AdbNimAttributionPanel({ nim, reason, qoqWindow }: AdbNimAttributionPanelProps) {
  return (
    <section className="adb-sec" data-testid="adb-nim-attribution-panel">
      <AdbSectionHead
        title="NIM 量价归因（环比）"
        meta="rate+mix+residual=该侧总效应；nim_delta_bp=资产端效应−负债端效应"
      />
      <p className="adb-note">
        口径：利率效应=份额×利率变动，结构效应=份额变动×基准利率，残差原样披露（利率覆盖不足时残差会变大）。
      </p>
      {!qoqWindow.available ? (
        <Alert
          type="info"
          showIcon
          message={`对比期无数据（${qoqWindow.start_date || EM_DASH}～${qoqWindow.end_date || EM_DASH}）`}
        />
      ) : !nim ? (
        <p className="adb-note">{unavailableMessage(reason)}</p>
      ) : (
        <div className="adb-panel">
          <AdbKpiStrip
            columns={5}
            items={
              [
                {
                  key: "nim-delta",
                  label: "NIM环比",
                  value: formatBp(nim.nim_delta_bp, true),
                  tone: kpiToneForSign(nim.nim_delta_bp),
                },
                { key: "nim-current", label: "本期NIM", value: formatAlreadyPercent(nim.nim_current, false) },
                { key: "nim-prior", label: "上期NIM", value: formatAlreadyPercent(nim.nim_prior, false) },
                {
                  key: "asset-effect",
                  label: "资产端效应",
                  value: formatBp(nim.asset_side.total_effect_bp, true),
                  tone: kpiToneForSign(nim.asset_side.total_effect_bp),
                },
                {
                  key: "liability-effect",
                  label: "负债端效应",
                  value: formatBp(nim.liability_side.total_effect_bp, true),
                  tone: kpiToneForSign(nim.liability_side.total_effect_bp),
                },
              ] satisfies AdbKpiStripItem[]
            }
          />
          <div className="adb-two-col">
            <div className="adb-table-group">
              <div className="adb-subhead">资产端量价归因</div>
              <Table<NimCategoryRow>
                size="small"
                pagination={false}
                rowKey={(row) => `asset-${row.category}`}
                columns={buildByCategoryColumns()}
                dataSource={nim.asset_side.by_category}
                locale={{ emptyText: "暂无数据" }}
              />
              <p className="adb-note">残差 {formatBp(nim.asset_side.residual_bp, true)}</p>
            </div>
            <div className="adb-table-group">
              <div className="adb-subhead">负债端量价归因</div>
              <Table<NimCategoryRow>
                size="small"
                pagination={false}
                rowKey={(row) => `liability-${row.category}`}
                columns={buildByCategoryColumns()}
                dataSource={nim.liability_side.by_category}
                locale={{ emptyText: "暂无数据" }}
              />
              <p className="adb-note">残差 {formatBp(nim.liability_side.residual_bp, true)}</p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
