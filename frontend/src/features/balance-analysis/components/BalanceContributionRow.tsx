import "../../../lib/agGridSetup";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, RowStyle } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import "../../../styles/agGridInstitutional.css";

import { AlertList } from "../../../components/AlertList";
import { useBalanceAnalysisThreeColumnGridStyle } from "./balanceAnalysisLayout";
import { BalanceStageTerminalPanel } from "./BalanceStageTerminalPanel";
import rowStyles from "./balanceAnalysisStageRow.module.css";
import type {
  BalanceStageContributionModel,
  BalanceStageContributionRow,
} from "../pages/balanceAnalysisPageModel";

type BalanceContributionRowProps = {
  model: BalanceStageContributionModel;
  variant?: "default" | "terminal";
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
  borderRadius: 10,
  border: "1px solid #eef2f7",
  background: "#ffffff",
};

function getStageContributionRowStyle(row?: BalanceStageContributionRow): RowStyle | undefined {
  if (row?.rowKind === "gap") {
    return { background: "#fbf1f0", color: "#b94743", fontWeight: 700 };
  }
  if (row?.rowKind === "empty") {
    return { color: "#8a99af", fontStyle: "italic" };
  }
  return undefined;
}

export function BalanceContributionRow({
  model,
  variant = "default",
}: BalanceContributionRowProps) {
  const gridStyle = useBalanceAnalysisThreeColumnGridStyle();
  const isTerminal = variant === "terminal";

  const tablePanel = (
    <div
      className={`ag-theme-alpine ${isTerminal ? rowStyles.agGridTerminal : ""}`}
      style={isTerminal ? undefined : { ...tableShellStyle, height: 300, width: "100%" }}
    >
      <AgGridReact<BalanceStageContributionRow>
        theme="legacy"
        rowData={model.rows}
        columnDefs={contributionColDefs}
        defaultColDef={{ sortable: false, resizable: true }}
        getRowId={(p) => p.data.item}
        getRowStyle={(p) => getStageContributionRowStyle(p.data)}
      />
    </div>
  );

  return (
    <div
      data-testid="balance-analysis-contribution-row"
      className={
        isTerminal
          ? `${rowStyles.rowGrid} ${rowStyles.rowGridContributionTerminal}`
          : `${rowStyles.rowGrid} ${rowStyles.rowGridDefault}`
      }
      style={isTerminal ? undefined : gridStyle}
    >
      {isTerminal ? (
        <BalanceStageTerminalPanel title="资产/负债/缺口贡献">{tablePanel}</BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefaultCompact}>
          <div className={rowStyles.panelTitle}>资产/负债/缺口贡献</div>
          {tablePanel}
        </div>
      )}
      {isTerminal ? (
        <BalanceStageTerminalPanel title="待关注事项">
          <AlertList items={model.watchItems} />
        </BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefault}>
          <div className={rowStyles.panelTitle}>待关注事项</div>
          <AlertList items={model.watchItems} />
        </div>
      )}
      {isTerminal ? (
        <BalanceStageTerminalPanel title="预警与事件">
          <AlertList items={model.alertItems} />
        </BalanceStageTerminalPanel>
      ) : (
        <div className={rowStyles.panelDefault}>
          <div className={rowStyles.panelTitle}>预警与事件</div>
          <AlertList items={model.alertItems} />
        </div>
      )}
    </div>
  );
}
