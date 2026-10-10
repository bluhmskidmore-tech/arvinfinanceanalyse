import { KpiCard } from "../../components/KpiCard";
import { type PnlByBusinessMonthlyAdjustmentBridgeModel, formatYuanAsWanUnit, toneFromSigned } from "./pnlByBusinessPageModel";
import { numeric, formatFtpRatePct } from "./pnlByBusinessDisplay";

export function MonthlyAdjustmentFtpBridgePanel({
  bridge,
  approvedAdjustmentCount,
  approvedReasons,
  pendingAdjustmentCount,
  auditLoading,
  auditError,
  auditDateMismatch,
  auditReturnedReportDate,
  requestedReportDate,
  auditReportDate,
}: {
  bridge: PnlByBusinessMonthlyAdjustmentBridgeModel | undefined;
  approvedAdjustmentCount: number;
  approvedReasons: string[];
  pendingAdjustmentCount: number;
  auditLoading: boolean;
  auditError: boolean;
  auditDateMismatch: boolean;
  auditReturnedReportDate?: string;
  requestedReportDate: string;
  auditReportDate: string;
}) {
  if (!bridge) {
    return null;
  }

  const { row } = bridge;
  const ftpNetPnl = numeric(row.ftp_net_pnl);
  const bridgeClosed = bridge.pnlReconciled && bridge.ftpReconciled;
  const outcome =
    ftpNetPnl === null
      ? "FTP后收益未返回，暂不能判断是否覆盖FTP成本。"
      : ftpNetPnl < 0
        ? `调整后合计损益仍未覆盖FTP成本，缺口 ${formatYuanAsWanUnit(Math.abs(ftpNetPnl))}。`
        : `调整后合计损益已覆盖FTP成本，FTP后收益 ${formatYuanAsWanUnit(ftpNetPnl)}。`;
  const auditSummary = auditLoading
    ? "审批记录读取中"
    : auditError
      ? "审批记录读取失败，当前仅展示月报已入账金额"
      : auditDateMismatch
        ? `审批记录报表日 ${auditReturnedReportDate ?? "未返回"} 与实际展示日 ${auditReportDate} 不一致，未采用该审批证据`
        : approvedAdjustmentCount > 0
          ? `${approvedAdjustmentCount} 条已批准；审批理由：${approvedReasons.join("；") || "未填写"}`
          : "未匹配到已批准记录，税务口径待核对";

  return (
    <section
      className="pnl-by-business-analysis-block"
      data-testid="pnl-by-business-monthly-adjustment-bridge"
    >
      <div className="pnl-by-business-analysis-heading">
        <div>
          <h2>{row.business_type} · {bridge.monthKey} 损益桥</h2>
          <p>金额为万元；补数前损益仅作分项对账，FTP成本与FTP后收益直接使用月报接口字段。</p>
          {auditReportDate !== requestedReportDate ? (
            <p>月报已回退至 {auditReportDate}，审批记录同步按该实际展示日核对，未使用所选日 {requestedReportDate}。</p>
          ) : null}
          {bridge.adjustedParentRowCount > 1 ? (
            <p>当月共有 {bridge.adjustedParentRowCount} 个父级业务含手工调整，本桥展示调整绝对额最大的一项。</p>
          ) : null}
        </div>
      </div>
      <div className="pnl-by-business-analysis-kpis">
        <KpiCard
          label="补数前损益（对账值）"
          value={formatYuanAsWanUnit(bridge.preAdjustmentPnl)}
          detail="利息收入 + 公允价值变动 + 资本利得"
        />
        <KpiCard
          label="已入账手工调整"
          value={formatYuanAsWanUnit(row.manual_adjustment)}
          detail="月报接口已生效金额"
        />
        <KpiCard
          label="调整后合计损益"
          value={formatYuanAsWanUnit(row.total_pnl)}
          detail="补数前损益 + 手工调整"
        />
        <KpiCard
          label="FTP成本"
          value={formatYuanAsWanUnit(row.ftp_cost)}
          detail={`月度日均 × ${formatFtpRatePct(row.ftp_rate_pct)} × 当月自然日/365`}
        />
        <KpiCard
          label="FTP后收益"
          value={formatYuanAsWanUnit(row.ftp_net_pnl)}
          detail="调整后合计损益 - FTP成本"
          tone={toneFromSigned(row.ftp_net_pnl)}
        />
      </div>
      <div
        className={
          bridgeClosed
            ? "pnl-by-business-monthly-reconciliation pnl-by-business-monthly-reconciliation--closed"
            : "pnl-by-business-monthly-reconciliation pnl-by-business-monthly-reconciliation--warning"
        }
        data-testid="pnl-by-business-monthly-adjustment-bridge-reconciliation"
      >
        <span>
          利息 {formatYuanAsWanUnit(row.interest_income)} + 公允价值 {formatYuanAsWanUnit(row.fair_value_change)} +
          资本利得 {formatYuanAsWanUnit(row.capital_gain)} = 补数前 {formatYuanAsWanUnit(bridge.preAdjustmentPnl)}
        </span>
        <span>
          补数前 {formatYuanAsWanUnit(bridge.preAdjustmentPnl)} + 手工调整 {formatYuanAsWanUnit(row.manual_adjustment)} =
          合计 {formatYuanAsWanUnit(row.total_pnl)}
        </span>
        <span>
          合计 {formatYuanAsWanUnit(row.total_pnl)} - FTP成本 {formatYuanAsWanUnit(row.ftp_cost)} = FTP后
          {" "}{formatYuanAsWanUnit(row.ftp_net_pnl)}
        </span>
        <span>
          损益对账差异 {formatYuanAsWanUnit(bridge.pnlReconciled ? 0 : bridge.pnlReconciliationDelta)} ·
          {bridge.pnlReconciled ? "已闭合" : "待核对"}；FTP对账差异
          {" "}{formatYuanAsWanUnit(bridge.ftpReconciled ? 0 : bridge.ftpReconciliationDelta)} ·
          {bridge.ftpReconciled ? "已闭合" : "待核对"}
        </span>
        <span>{outcome}</span>
        <span>
          {auditSummary}；系统暂无结构化税前额、增值税额或税后净额字段，审批理由未明确时不得推断税务口径。
        </span>
        {pendingAdjustmentCount > 0 ? (
          <span>{pendingAdjustmentCount} 条待确认记录未计入本桥。</span>
        ) : null}
      </div>
    </section>
  );
}
