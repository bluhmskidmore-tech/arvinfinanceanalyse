import { Alert, Table } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { AdbAnomalyItem, AdbVolatilityBlock, AdbVolatilitySeries } from "../../../api/contracts";
import { EM_DASH, formatYi } from "../../../utils/format";
import AdbSectionHead from "./AdbSectionHead";
import { formatAlreadyPercent, toneClassForSign } from "./adbDeepAnalysisFormat";

import "./AverageBalanceView.css";

type AdbVolatilityPanelProps = {
  volatility: AdbVolatilityBlock | null;
};

type SeriesRow = {
  key: string;
  label: string;
  render: (series: AdbVolatilitySeries) => string;
};

const SERIES_ROWS: SeriesRow[] = [
  { key: "mean", label: "均值(亿元)", render: (s) => formatYi(s.mean, false) },
  { key: "std", label: "标准差(亿元)", render: (s) => formatYi(s.std, false) },
  { key: "cv", label: "变异系数(CV)", render: (s) => (s.cv === null ? EM_DASH : s.cv.toFixed(4)) },
  { key: "min", label: "区间最小值", render: (s) => `${formatYi(s.min.value, false)}（${s.min.date}）` },
  { key: "max", label: "区间最大值", render: (s) => `${formatYi(s.max.value, false)}（${s.max.date}）` },
  {
    key: "max-change",
    label: "最大单日变动",
    render: (s) =>
      s.max_daily_change
        ? `${formatYi(s.max_daily_change.delta, true)}（${s.max_daily_change.date}，${formatAlreadyPercent(
            s.max_daily_change.pct,
            true,
          )}）`
        : EM_DASH,
  },
];

function buildAnomalyColumns(): ColumnsType<AdbAnomalyItem> {
  return [
    { title: "日期", dataIndex: "date", key: "date" },
    {
      title: "方向",
      dataIndex: "side",
      key: "side",
      render: (value: "asset" | "liability") => (value === "asset" ? "资产" : "负债"),
    },
    {
      title: "余额(亿元)",
      dataIndex: "value",
      key: "value",
      align: "right",
      render: (value: number) => formatYi(value, false),
    },
    {
      title: "变动(亿元)",
      dataIndex: "delta",
      key: "delta",
      align: "right",
      render: (value: number) => <span className={toneClassForSign(value)}>{formatYi(value, true)}</span>,
    },
    {
      title: "z-score",
      dataIndex: "zscore",
      key: "zscore",
      align: "right",
      render: (value: number) => value.toFixed(2),
    },
    {
      title: "方向",
      dataIndex: "direction",
      key: "direction",
      render: (value: "up" | "down") => (value === "up" ? "上跳" : "下跳"),
    },
  ];
}

/**
 * 波动与异常：均值/标准差/CV/极值/最大单日变动、异常日 z-score 检测、月末效应。
 * 数值均来自后端 core_finance 计算结果，前端只格式化。
 */
export default function AdbVolatilityPanel({ volatility }: AdbVolatilityPanelProps) {
  return (
    <section className="adb-sec" data-testid="adb-volatility-panel">
      <AdbSectionHead title="波动与异常" meta="z-score 基于当期日变动序列自身均值/标准差" />
      <p className="adb-note">
        口径：仅统计本期观测日（缺失日不补0）；|z|≥2.5 判定为异常日；月末效应=月末余额相对月中均值的偏离。
      </p>
      {!volatility ? (
        <p className="adb-note">本期观测点不足，无法计算波动与异常指标。</p>
      ) : (
        <div className="adb-panel">
          <div className="adb-two-col">
            {(["assets", "liabilities"] as const).map((side) => {
              const series = volatility[side];
              return (
                <div className="adb-table-group" key={side} data-testid={`adb-volatility-series-${side}`}>
                  <div className="adb-subhead">{side === "assets" ? "资产日度波动" : "负债日度波动"}</div>
                  {series ? (
                    <div className="adb-lines">
                      {SERIES_ROWS.map((row) => (
                        <div key={row.key}>
                          {row.label}：<span className="adb-cell-strong">{row.render(series)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="adb-note">观测日不足 2 天，无法计算波动指标。</p>
                  )}
                </div>
              );
            })}
          </div>

          <div className="adb-table-group">
            <div className="adb-subhead">异常日（|z|≥2.5，按|z|降序，至多10条）</div>
            {volatility.anomaly_detection_available ? (
              <Table<AdbAnomalyItem>
                size="small"
                pagination={false}
                rowKey={(row) => `${row.side}-${row.date}`}
                columns={buildAnomalyColumns()}
                dataSource={volatility.anomalies}
                locale={{ emptyText: "区间内未检测到异常波动日" }}
              />
            ) : (
              <p className="adb-note">观测点不足或标准差为0，未执行异常检测。</p>
            )}
          </div>

          {volatility.month_end_effect ? (
            <div className="adb-table-group" data-testid="adb-month-end-effect">
              <div className="adb-subhead">月末效应（窗口粉饰深化）</div>
              {(["assets", "liabilities"] as const).map((side) => {
                const effect = volatility.month_end_effect![side];
                const label = side === "assets" ? "资产" : "负债";
                const detail = `${label}月末余额较月中均值平均${formatAlreadyPercent(effect.uplift_pct, true)}（覆盖 ${effect.months_observed} 个月）`;
                return effect.flagged ? (
                  <Alert key={side} type="warning" showIcon message={`${label}端存在月末冲高迹象`} description={detail} />
                ) : (
                  <p className="adb-note" key={side}>
                    {detail}
                  </p>
                );
              })}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
