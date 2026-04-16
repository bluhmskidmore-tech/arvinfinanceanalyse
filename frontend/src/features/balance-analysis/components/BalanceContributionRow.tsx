import { AgGridReact } from "ag-grid-react";
import type { ColDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import { AlertList } from "../../../components/AlertList";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";

type ContributionMockRow = {
  item: string;
  assetBal: string;
  assetPct: string;
  liabBal: string;
  liabPct: string;
  netGap: string;
  rowKind: "body" | "gap";
};

const contributionMockRows: ContributionMockRow[] = [
  {
    item: "债券投资",
    assetBal: "3,289.4",
    assetPct: "93.3%",
    liabBal: "—",
    liabPct: "—",
    netGap: "3,289.4",
    rowKind: "body",
  },
  {
    item: "同业资产",
    assetBal: "235.6",
    assetPct: "6.7%",
    liabBal: "—",
    liabPct: "—",
    netGap: "235.6",
    rowKind: "body",
  },
  {
    item: "发行负债",
    assetBal: "—",
    assetPct: "—",
    liabBal: "1,206.2",
    liabPct: "66.3%",
    netGap: "-1,206.2",
    rowKind: "body",
  },
  {
    item: "同业负债",
    assetBal: "—",
    assetPct: "—",
    liabBal: "611.7",
    liabPct: "33.7%",
    netGap: "-611.7",
    rowKind: "body",
  },
  {
    item: "合计",
    assetBal: "3,525.0",
    assetPct: "100%",
    liabBal: "1,817.9",
    liabPct: "100%",
    netGap: "1,707.1",
    rowKind: "body",
  },
  {
    item: "1年内净缺口",
    assetBal: "—",
    assetPct: "—",
    liabBal: "—",
    liabPct: "—",
    netGap: "-373.0",
    rowKind: "gap",
  },
  {
    item: "1-3年净缺口",
    assetBal: "—",
    assetPct: "—",
    liabBal: "—",
    liabPct: "—",
    netGap: "-128.5",
    rowKind: "gap",
  },
  {
    item: "3年以上净缺口",
    assetBal: "—",
    assetPct: "—",
    liabBal: "—",
    liabPct: "—",
    netGap: "+96.2",
    rowKind: "gap",
  },
];

const contributionColDefs: ColDef<ContributionMockRow>[] = [
  { field: "item", headerName: "项目", flex: 1, minWidth: 110 },
  { field: "assetBal", headerName: "市场余额", flex: 1, minWidth: 96 },
  { field: "assetPct", headerName: "占比", width: 72 },
  { field: "liabBal", headerName: "负债余额", flex: 1, minWidth: 96 },
  { field: "liabPct", headerName: "占比", width: 72 },
  { field: "netGap", headerName: "净缺口", flex: 1, minWidth: 88 },
];

const watchItems = [
  { level: "danger" as const, title: "4月短端缺口压力较大" },
  { level: "warning" as const, title: "发行负债集中度偏高" },
  { level: "caution" as const, title: "短端缺口已覆盖率 81.8%" },
  { level: "info" as const, title: "异常资产跟踪" },
];

const alertItems = [
  { level: "danger" as const, title: "短端缺口预警", time: "10:15" },
  { level: "warning" as const, title: "03-02 大额到期", time: "09:20" },
  { level: "caution" as const, title: "发行负债滚续敏感", time: "09:05" },
  { level: "info" as const, title: "异常资产跟踪", time: "06:50" },
];

const tableShellStyle = {
  overflowX: "auto" as const,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
};

export function BalanceContributionRow() {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();

  return (
    <div data-testid="balance-analysis-contribution-row" style={gridStyle}>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 12,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 10 }}>资产/负债/缺口贡献</div>
        <div className="ag-theme-alpine" style={{ ...tableShellStyle, height: 300, width: "100%" }}>
          <AgGridReact<ContributionMockRow>
            rowData={contributionMockRows}
            columnDefs={contributionColDefs}
            defaultColDef={{ sortable: false, resizable: true }}
            getRowId={(p) => p.data.item}
            getRowStyle={(p) =>
              p.data?.rowKind === "gap"
                ? { background: "#fff1f0", color: "#cf1322", fontWeight: 600 }
                : undefined
            }
          />
        </div>
      </div>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 16,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 12 }}>待关注事项</div>
        <AlertList items={watchItems} />
      </div>
      <div
        style={{
          borderRadius: 16,
          border: "1px solid #e4ebf5",
          background: "#ffffff",
          padding: 16,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: "#162033", marginBottom: 12 }}>预警与事件</div>
        <AlertList items={alertItems} />
      </div>
    </div>
  );
}
