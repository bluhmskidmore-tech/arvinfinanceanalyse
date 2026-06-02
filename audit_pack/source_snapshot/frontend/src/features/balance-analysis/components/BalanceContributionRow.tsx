import "../../../lib/agGridSetup";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, RowStyle } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";

import { AlertList } from "../../../components/AlertList";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";
import type {
  BalanceStageContributionModel,
  BalanceStageContributionRow,
} from "../pages/balanceAnalysisPageModel";

type BalanceContributionRowProps = {
  model: BalanceStageContributionModel;
};

const contributionColDefs: ColDef<BalanceStageContributionRow>[] = [
  { field: "item", headerName: "项目", flex: 1, minWidth: 110 },
  { field: "assetBal", headerName: "资产余额(亿元)", flex: 1, minWidth: 116 },
  { field: "assetPct", headerName: "占比", width: 72 },
  { field: "liabBal", headerName: "负债余额(亿元)", flex: 1, minWidth: 116 },
  { field: "liabPct", headerName: "占比", width: 72 },
  { field: "netGap", headerName: "净缺口(亿元)", flex: 1, minWidth: 108 },
];

const tableShellStyle = {
  overflowX: "auto" as const,
  borderRadius: 16,
  border: "1px solid #e4ebf5",
  background: "#ffffff",
};

function getStageContributionRowStyle(row?: BalanceStageContributionRow): RowStyle | undefined {
  if (row?.rowKind === "gap") {
    return { background: "#fff1f0", color: "#cf1322", fontWeight: 600 };
  }
  if (row?.rowKind === "empty") {
    return { color: "#64748b", fontStyle: "italic" };
  }
  return undefined;
}

export function BalanceContributionRow({ model }: BalanceContributionRowProps) {
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
          <AgGridReact<BalanceStageContributionRow>
            rowData={model.rows}
            columnDefs={contributionColDefs}
            defaultColDef={{ sortable: false, resizable: true }}
            getRowId={(p) => p.data.item}
            getRowStyle={(p) => getStageContributionRowStyle(p.data)}
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
        <AlertList items={model.watchItems} />
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
        <AlertList items={model.alertItems} />
      </div>
    </div>
  );
}
