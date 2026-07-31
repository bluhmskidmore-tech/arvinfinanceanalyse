import { AlertList } from "../../../components/AlertList";
import dhStyles from "../../workbench/dashboard-home/dashboardHome.module.css";
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

const contributionColumns = [
  { field: "item", headerName: "项目" },
  { field: "assetBal", headerName: "资产余额(亿元)" },
  { field: "assetPct", headerName: "占比" },
  { field: "liabBal", headerName: "负债余额(亿元)" },
  { field: "liabPct", headerName: "占比" },
  { field: "netGap", headerName: "净缺口(亿元)" },
] as const satisfies ReadonlyArray<{
  field: keyof Pick<
    BalanceStageContributionRow,
    "item" | "assetBal" | "assetPct" | "liabBal" | "liabPct" | "netGap"
  >;
  headerName: string;
}>;

function contributionRowClass(row: BalanceStageContributionRow): string | undefined {
  if (row.rowKind === "gap") {
    return rowStyles.contributionRowGap;
  }
  if (row.rowKind === "empty") {
    return rowStyles.contributionRowEmpty;
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
    <div className={rowStyles.contributionTableShell}>
      <table
        className={`${dhStyles.dhTerminalTable} ${rowStyles.contributionTable}`}
        data-testid="balance-analysis-contribution-table"
      >
        <thead>
          <tr>
            {contributionColumns.map((column) => (
              <th key={column.field}>{column.headerName}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {model.rows.map((row) => (
            <tr key={row.item} className={contributionRowClass(row)}>
              {contributionColumns.map((column) => (
                <td key={column.field}>{row[column.field]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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
