import type {
  PnlByBusinessMonthlyChangeRow,
  PnlByBusinessMonthlyManagementChange,
} from "../../api/contracts";

type PnlByBusinessManagementChangePanelProps = {
  managementChange: PnlByBusinessMonthlyManagementChange | null | undefined;
  expectedCurrentMonthKey: string | null;
  selectedRowKey: string | null;
  isLoading: boolean;
  isError: boolean;
};

type DeltaMetric = {
  label: string;
  value: string | null | undefined;
  scale: number;
  digits: number;
  unit: string;
  directional: boolean;
};

function finiteNumber(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") {
    return null;
  }
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function formatSignedDelta(
  raw: string | number | null | undefined,
  scale: number,
  digits: number,
  unit: string,
): string {
  const value = finiteNumber(raw);
  if (value === null) {
    return "—";
  }
  const scaled = value / scale;
  const sign = scaled > 0 ? "+" : "";
  return `${sign}${scaled.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} ${unit}`;
}

function formatMovement(
  raw: string | number | null | undefined,
  scale: number,
  digits: number,
  unit: string,
): string {
  const value = finiteNumber(raw);
  if (value === null) {
    return "不可比较";
  }
  if (value === 0) {
    return "持平";
  }
  const formatted = (Math.abs(value) / scale).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${value > 0 ? "增加" : "减少"} ${formatted} ${unit}`;
}

function formatPnlMovement(raw: string | number | null | undefined): string {
  return formatMovement(raw, 10_000, 2, "万元");
}

function balanceTimingInterpretation(
  avgBalanceDelta: string | number | null | undefined,
  currentBalanceDelta: string | number | null | undefined,
): string {
  const avgBalance = finiteNumber(avgBalanceDelta);
  const currentBalance = finiteNumber(currentBalanceDelta);
  const definition = "日均余额反映整月平均，期末余额反映月末时点";

  if (avgBalance === null || currentBalance === null) {
    return `${definition}；当前余额信息不足，暂不判断月末时点变化。`;
  }
  const directionsOppose =
    (avgBalance < 0 && currentBalance > 0) ||
    (avgBalance > 0 && currentBalance < 0);
  if (directionsOppose) {
    return "日均余额与期末余额环比方向相反；两者分别反映整月平均和月末时点，是否存在月末集中变化需结合日度余额确认。";
  }
  return `${definition}。`;
}

function deltaTone(raw: string | number | null | undefined): "positive" | "negative" | "neutral" {
  const value = finiteNumber(raw);
  if (value === null || value === 0) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}

function topPnlChangeRows(rows: PnlByBusinessMonthlyChangeRow[]): PnlByBusinessMonthlyChangeRow[] {
  return rows
    .filter((row) => {
      const value = finiteNumber(row.total_pnl_delta);
      return row.comparison_available && value !== null && value !== 0;
    })
    .sort((left, right) => {
      const rightDelta = Math.abs(finiteNumber(right.total_pnl_delta) ?? 0);
      const leftDelta = Math.abs(finiteNumber(left.total_pnl_delta) ?? 0);
      return rightDelta - leftDelta || left.sort_order - right.sort_order;
    })
    .slice(0, 3);
}

function ManagementChangeState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="pnl-by-business-management-change" data-testid="pnl-by-business-management-change">
      <div className="pnl-by-business-management-change__state" role="status" aria-live="polite">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
    </section>
  );
}

export function PnlByBusinessManagementChangePanel({
  managementChange,
  expectedCurrentMonthKey,
  selectedRowKey,
  isLoading,
  isError,
}: PnlByBusinessManagementChangePanelProps) {
  if (isLoading && !managementChange) {
    return <ManagementChangeState title="月度变化加载中" description="正在读取月度比较结果。" />;
  }
  if (isError && !managementChange) {
    return <ManagementChangeState title="月度变化读取失败" description="月报主数据未改变，请重新加载页面数据。" />;
  }
  if (!managementChange) {
    return <ManagementChangeState title="暂无月度变化" description="当前月报尚未生成月度比较结果。" />;
  }
  const cachedComparisonUsable =
    (!expectedCurrentMonthKey || managementChange.current_month_key === expectedCurrentMonthKey) &&
    managementChange.comparison_available &&
    managementChange.summary !== null;
  if (isError && !cachedComparisonUsable) {
    return (
      <ManagementChangeState
        title="月度变化刷新失败"
        description={`${managementChange.current_month_key} 的缓存状态可能已过期，可能未包含最新补数或手工调整，已停止用于正式汇报。`}
      />
    );
  }
  if (expectedCurrentMonthKey && managementChange.current_month_key !== expectedCurrentMonthKey) {
    return (
      <ManagementChangeState
        title="月度变化日期不一致"
        description={`月度比较结果为 ${managementChange.current_month_key}，当前页面月份为 ${expectedCurrentMonthKey}，已停止展示旧比较。`}
      />
    );
  }
  if (managementChange.comparison_status === "current_month_missing") {
    return (
      <ManagementChangeState
        title="当前月数据缺失"
        description={`${managementChange.current_month_key} 未形成完整月报，未展示环比。`}
      />
    );
  }
  if (managementChange.comparison_status === "previous_month_outside_request_scope") {
    return (
      <ManagementChangeState
        title="上月超出本年度范围"
        description={`${managementChange.previous_month_key} 不在 ${managementChange.current_month_key.slice(0, 4)} 年月报查询范围内，未跨年度拼接。`}
      />
    );
  }
  if (managementChange.comparison_status === "period_incomplete") {
    return (
      <ManagementChangeState
        title="月份尚未完整"
        description={`${managementChange.incomplete_months.join("、")} 尚未到自然月末，不与完整上月直接比较。`}
      />
    );
  }
  if (!managementChange.comparison_available || !managementChange.summary) {
    return (
      <ManagementChangeState
        title="暂无可比上月"
        description={`${managementChange.current_month_key} 未找到同年度上一自然月 ${managementChange.previous_month_key} 的完整月报，未按 0 补齐。`}
      />
    );
  }

  const summary = managementChange.summary;
  const metrics: DeltaMetric[] = [
    {
      label: "日均变化",
      value: summary.avg_balance_delta,
      scale: 100_000_000,
      digits: 2,
      unit: "亿元",
      directional: false,
    },
    {
      label: "已分类父级损益变化",
      value: summary.total_pnl_delta,
      scale: 10_000,
      digits: 2,
      unit: "万元",
      directional: true,
    },
    {
      label: "FTP净损益变化",
      value: summary.ftp_net_pnl_delta,
      scale: 10_000,
      digits: 2,
      unit: "万元",
      directional: true,
    },
    {
      label: "FTP后年化变化",
      value: summary.ftp_net_annualized_yield_delta_bp,
      scale: 1,
      digits: 2,
      unit: "bp",
      directional: true,
    },
  ];
  const componentMetrics = [
    { label: "利息收入", value: summary.interest_income_delta },
    { label: "公允价值变动", value: summary.fair_value_change_delta },
    { label: "资本利得", value: summary.capital_gain_delta },
    { label: "手工调整", value: summary.manual_adjustment_delta },
  ];
  const driverRows = topPnlChangeRows(managementChange.rows);
  const topDriver = driverRows[0];
  const unavailableRowCount = managementChange.rows.filter((row) => !row.comparison_available).length;

  return (
    <section className="pnl-by-business-management-change" data-testid="pnl-by-business-management-change">
      <header className="pnl-by-business-management-change__header">
        <div>
          <span className="pnl-by-business-management-change__eyebrow">月度经营环比</span>
          <h2>月度经营变化</h2>
          <p>
            {managementChange.current_month_key} 较 {managementChange.previous_month_key}，全部变化值由系统按两期月报统一计算。
          </p>
        </div>
        <span className="pnl-by-business-management-change__basis">自然月环比</span>
      </header>

      {isError ? (
        <div
          className="pnl-by-business-management-change__warning"
          role="status"
          aria-live="polite"
        >
          <strong>刷新失败，当前展示上次成功结果</strong>
          <span>该结果可能未包含最新补数或手工调整，重新加载成功后再用于正式汇报。</span>
        </div>
      ) : null}

      <div className="pnl-by-business-management-change__conclusion" role="note">
        <strong>
          {managementChange.current_month_key} 已分类父级损益较上月{formatPnlMovement(summary.total_pnl_delta)}
          ；日均余额{formatMovement(summary.avg_balance_delta, 100_000_000, 2, "亿元")}，期末余额
          {formatMovement(summary.current_balance_delta, 100_000_000, 2, "亿元")}。
        </strong>
        <span>
          {topDriver
            ? `最大波动业务为${topDriver.business_type}（${formatPnlMovement(topDriver.total_pnl_delta)}）。`
            : "未发现非零业务损益波动。"}
        </span>
        <span>{balanceTimingInterpretation(summary.avg_balance_delta, summary.current_balance_delta)}</span>
      </div>

      <div className="pnl-by-business-management-change__metrics">
        {metrics.map((metric) => (
          <article key={metric.label}>
            <span>{metric.label}</span>
            <strong
              data-delta-tone={metric.directional ? deltaTone(metric.value) : "neutral"}
            >
              {formatSignedDelta(metric.value, metric.scale, metric.digits, metric.unit)}
            </strong>
          </article>
        ))}
      </div>

      <div className="pnl-by-business-management-change__components">
        <div className="pnl-by-business-management-change__components-heading">
          <strong>损益构成变化</strong>
          <span>当前月减上一自然月</span>
        </div>
        <div className="pnl-by-business-management-change__components-grid">
          {componentMetrics.map((metric) => (
            <span key={metric.label}>
              <small>{metric.label}</small>
              <strong data-delta-tone={deltaTone(metric.value)}>
                {formatMovement(metric.value, 10_000, 2, "万元")}
              </strong>
            </span>
          ))}
        </div>
      </div>

      {managementChange.comparison_status === "data_quality_warning" ? (
        <div className="pnl-by-business-management-change__warning">
          <strong>数据质量提示</strong>
          <span>
            {managementChange.coverage_warning_months.length > 0
              ? `${managementChange.coverage_warning_months.join("、")} 存在样本补齐或日期覆盖不完整。`
              : ""}
            {managementChange.reconciliation_warning_months.length > 0
              ? `${managementChange.reconciliation_warning_months.join("、")} 存在未分类记录、对账差异或证据不完整。`
              : ""}
            环比值仍为系统计算的已分类父级口径，汇报时需保留该限制。
          </span>
        </div>
      ) : null}

      <div className="pnl-by-business-management-change__driver-heading">
        <div>
          <h3>业务波动前三项</h3>
          <p>优先展示已分类父级损益波动最大的业务，下方累计表保留完整分类。</p>
        </div>
        {unavailableRowCount > 0 ? <span>{unavailableRowCount} 项缺少可比行</span> : null}
      </div>

      {driverRows.length > 0 ? (
        <div
          className="pnl-by-business-management-change__table-shell"
          data-testid="pnl-by-business-management-change-drivers"
          tabIndex={0}
          aria-label="业务分项月度变化表，可横向滚动"
        >
          <table>
            <thead>
              <tr>
                <th>已分类业务</th>
                <th>损益变化（万元）</th>
                <th>FTP净损益变化（万元）</th>
                <th>日均变化（亿元）</th>
                <th>FTP后年化变化（bp）</th>
              </tr>
            </thead>
            <tbody>
              {driverRows.map((row) => (
                <tr key={row.row_key} data-selected={row.row_key === selectedRowKey ? "true" : "false"}>
                  <td>
                    <strong>{row.business_type}</strong>
                    {row.row_key === selectedRowKey ? <small>当前下钻业务</small> : null}
                  </td>
                  <td data-delta-tone={deltaTone(row.total_pnl_delta)}>
                    {formatSignedDelta(row.total_pnl_delta, 10_000, 2, "")}
                  </td>
                  <td data-delta-tone={deltaTone(row.ftp_net_pnl_delta)}>
                    {formatSignedDelta(row.ftp_net_pnl_delta, 10_000, 2, "")}
                  </td>
                  <td>{formatSignedDelta(row.avg_balance_delta, 100_000_000, 2, "")}</td>
                  <td data-delta-tone={deltaTone(row.ftp_net_annualized_yield_delta_bp)}>
                    {formatSignedDelta(row.ftp_net_annualized_yield_delta_bp, 1, 2, "")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="pnl-by-business-management-change__empty">暂无可展示的业务分项比较。</p>
      )}

      <p className="pnl-by-business-management-change__definition">
        口径：FTP后年化收益率环比变化（bp），不等同于全行生息资产利差。
      </p>
    </section>
  );
}
