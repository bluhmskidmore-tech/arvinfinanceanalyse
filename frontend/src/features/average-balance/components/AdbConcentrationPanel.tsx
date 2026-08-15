import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { AdbConcentrationSide } from "../../../api/contracts";
import { EM_DASH, formatPercent } from "../../../utils/format";
import AdbSectionHead from "./AdbSectionHead";
import {
  formatAlreadyPercent,
  formatHhi,
  formatPercentagePoints,
  toneClassForSign,
} from "./adbDeepAnalysisFormat";

import "./AverageBalanceView.css";

type MoverRow = AdbConcentrationSide["movers"][number];

type AdbConcentrationPanelProps = {
  concentration: {
    assets: AdbConcentrationSide | null;
    liabilities: AdbConcentrationSide | null;
    reason: string | null;
  } | null;
};

function buildMoverColumns(): ColumnsType<MoverRow> {
  return [
    { title: "分类", dataIndex: "category", key: "category", ellipsis: true },
    {
      title: "期初占比",
      dataIndex: "share_start_pct",
      key: "share_start_pct",
      align: "right",
      render: (value: number) => formatAlreadyPercent(value, false),
    },
    {
      title: "期末占比",
      dataIndex: "share_end_pct",
      key: "share_end_pct",
      align: "right",
      render: (value: number) => formatAlreadyPercent(value, false),
    },
    {
      title: "变动(pp)",
      dataIndex: "delta_pp",
      key: "delta_pp",
      align: "right",
      render: (value: number) => (
        <span className={toneClassForSign(value)}>{formatPercentagePoints(value)}</span>
      ),
    },
  ];
}

function SideBlock({
  testKey,
  label,
  side,
}: {
  testKey: string;
  label: string;
  side: AdbConcentrationSide | null;
}) {
  if (!side) {
    return (
      <div className="adb-panel" data-testid={`adb-concentration-block-${testKey}`}>
        <div className="adb-subhead">{label}</div>
        <p className="adb-note">区间只有 1 个观测日，无法计算结构集中度。</p>
      </div>
    );
  }

  return (
    <div className="adb-panel" data-testid={`adb-concentration-block-${testKey}`}>
      <div className="adb-subhead">{label}</div>
      <div className="adb-lines">
        <div>
          观测日：{side.start_observation_date} → {side.end_observation_date}
        </div>
        <div>
          HHI：{formatHhi(side.hhi_start)} → <span className="adb-cell-strong">{formatHhi(side.hhi_end)}</span>
        </div>
        <div>
          Top3 占比：{formatPercent(side.top3_share_start, false)} → {formatPercent(side.top3_share_end, false)}
        </div>
        <div>
          Top5 占比：{formatPercent(side.top5_share_start, false)} → {formatPercent(side.top5_share_end, false)}
        </div>
      </div>
      <div className="adb-table-group">
        <div className="adb-subhead">份额迁移（按|Δ|降序，至多8条）</div>
        <Table<MoverRow>
          size="small"
          pagination={false}
          rowKey={(row) => row.category}
          columns={buildMoverColumns()}
          dataSource={side.movers}
          locale={{ emptyText: "暂无数据" }}
        />
      </div>
    </div>
  );
}

/**
 * 结构集中度与迁移：HHI/TopN 取本期首末观测日分类分布，movers 为份额迁移排行。
 */
export default function AdbConcentrationPanel({ concentration }: AdbConcentrationPanelProps) {
  return (
    <section className="adb-sec" data-testid="adb-concentration-panel">
      <AdbSectionHead title="结构集中度与迁移" meta="HHI=Σ份额²；movers 按 |Δ份额| 降序" />
      <p className="adb-note">
        口径：取本期首个与末个观测日的分类余额分布计算 HHI/Top3/Top5；只有 1 个观测日时无法比较，整块显示不可用原因。
      </p>
      {!concentration ? (
        <p className="adb-note">结构集中度不可用{EM_DASH}</p>
      ) : (
        <div className="adb-two-col">
          <SideBlock testKey="assets" label="资产端" side={concentration.assets} />
          <SideBlock testKey="liabilities" label="负债端" side={concentration.liabilities} />
        </div>
      )}
    </section>
  );
}
