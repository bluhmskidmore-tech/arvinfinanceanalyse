import { useEffect, useState } from "react";
import { Spin } from "antd";

import { useApiClient } from "../../../api/client";
import type { YieldByPeriodPayload } from "../../../api/contracts";
import "./yieldAnalysis.css";

type PeriodType = "monthly" | "quarterly" | "yearly";

function fmtYi(raw: number): string {
  return (raw / 1e8).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtWan(raw: number): string {
  return (raw / 1e4).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) {
    return "—";
  }
  return `${v.toFixed(2)}%`;
}

export function YieldByPeriodPanel() {
  const client = useApiClient();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [periodType, setPeriodType] = useState<PeriodType>("monthly");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<YieldByPeriodPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const payload = await client.getYieldByPeriod({ year, periodType });
        if (!cancelled) {
          setData(payload);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setData(null);
          setError(e instanceof Error ? e.message : "加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [client, year, periodType]);

  const periods = data?.periods ?? [];

  return (
    <div className="yield-analysis-card yield-analysis-card--padded" data-testid="yield-by-period-panel">
      <div className="yield-analysis-header">
        <div>
          <h2 className="yield-analysis-title">期间收益</h2>
          <p className="yield-analysis-description">
            按月度、季度或年度汇总正式口径「业务种类 × 报告日」损益与月末规模；收益率 = 总损益 ÷ 规模 × 100%，年化按日历天数比例外推。
          </p>
        </div>
        <div className="yield-analysis-pill">Position + PnL</div>
      </div>

      <div className="yield-analysis-form-row">
        <label className="yield-analysis-field">
          <span className="yield-analysis-label">年份</span>
          <select
            aria-label="期间收益-年份"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="yield-analysis-control"
          >
            {[0, 1, 2, 3, 4].map((d) => (
              <option key={d} value={currentYear - d}>
                {currentYear - d}
              </option>
            ))}
          </select>
        </label>
        <label className="yield-analysis-field">
          <span className="yield-analysis-label">周期</span>
          <select
            aria-label="期间收益-周期"
            value={periodType}
            onChange={(e) => setPeriodType(e.target.value as PeriodType)}
            className="yield-analysis-control yield-analysis-control--wide"
          >
            <option value="monthly">月度</option>
            <option value="quarterly">季度</option>
            <option value="yearly">年度</option>
          </select>
        </label>
      </div>

      {loading ? (
        <div className="yield-analysis-loading">
          <Spin />
        </div>
      ) : error ? (
        <div className="yield-analysis-error">{error}</div>
      ) : periods.length === 0 ? (
        <div className="yield-analysis-empty">
          所选年份暂无可用正式损益按业务汇总数据（或 DuckDB 中该年无报告日）。请确认已跑 PnL 物化任务，或换一年份。
        </div>
      ) : (
        <>
          <div className="yield-analysis-period-table-wrap">
            <table className="yield-analysis-period-table">
              <thead>
                <tr>
                  <th>期间</th>
                  <th>起止日</th>
                  <th>天数</th>
                  <th>规模（亿元）</th>
                  <th>损益（万元）</th>
                  <th>收益率</th>
                  <th>年化收益率</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((p) => (
                  <tr key={p.period}>
                    <td>{p.period}</td>
                    <td>
                      {p.start_date} ~ {p.end_date}
                    </td>
                    <td>{p.num_days}</td>
                    <td>{fmtYi(p.total_avg_balance)}</td>
                    <td>{fmtWan(p.total_pnl)}</td>
                    <td>{fmtPct(p.overall_yield)}</td>
                    <td>{fmtPct(p.overall_annualized_yield)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="yield-analysis-period-note">
            口径与「损益按业务种类」页一致：来自 fact_formal_pnl_fi / fact_nonstd_pnl_bridge 与 fact_formal_zqtz_balance_daily
            联结汇总；规模列为各报告日业务种类月末市值合计（元折亿元），非日均。
          </p>
        </>
      )}
    </div>
  );
}
