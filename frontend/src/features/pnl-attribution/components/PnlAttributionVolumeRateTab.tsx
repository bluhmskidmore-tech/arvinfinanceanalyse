/**
 * 规模 / 利率效应页签容器。
 * 自 PnlAttributionView.tsx 纯搬移（2026-08-13 拆分）：VolumeRateBridgePanel
 * 与瀑布/明细图表区，仅做 props 接线，不改行为。
 */
import type { ResultMeta, VolumeRateAttributionPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { EM_DASH } from "../../../utils/format";
import { derivePnlDataSectionState } from "../adapters/pnlAttributionAdapter";
import { AttributionWaterfallChart } from "./AttributionWaterfallChart";
import { VolumeRateAnalysisChart } from "./VolumeRateAnalysisChart";
import { cx } from "./pnlAttributionClassNames";
import { formatYi, type VolumeRateBridgeSummary } from "./pnlAttributionViewModel";

function valueToneClassName(value: number | undefined) {
  if (value === undefined) return "pnl-attribution-tone--neutral";
  return value >= 0
    ? "pnl-attribution-tone--positive"
    : "pnl-attribution-tone--negative";
}

function formatPct(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(1)}%`;
}

export function VolumeRateBridgePanel(props: {
  data: VolumeRateAttributionPayload;
  summary: VolumeRateBridgeSummary;
}) {
  const { data, summary } = props;
  const residualIsMaterial =
    summary.unexplainedEffect !== undefined &&
    Math.abs(summary.unexplainedEffect) > 10_000;
  const denominator =
    summary.pnlChange !== undefined && Math.abs(summary.pnlChange) > 10_000
      ? summary.pnlChange
      : undefined;
  const bridgeRows = [
    {
      label: "规模效应",
      formula: "Δ规模 × 上期收益率",
      value: summary.volumeEffect,
      accentClass: "pnl-attribution-bridge-table__dot--volume",
    },
    {
      label: "利率效应",
      formula: "上期规模 × Δ收益率",
      value: summary.rateEffect,
      accentClass: "pnl-attribution-bridge-table__dot--rate",
    },
    {
      label: "交叉效应",
      formula: "Δ规模 × Δ收益率",
      value: summary.interactionEffect,
      accentClass: "pnl-attribution-bridge-table__dot--interaction",
    },
    {
      label: "未解释差额",
      formula: residualIsMaterial ? "缺规模或未匹配分类" : "闭合容差内",
      value: summary.unexplainedEffect,
      accentClass: residualIsMaterial
        ? "pnl-attribution-bridge-table__dot--residual"
        : "pnl-attribution-bridge-table__dot--neutral",
      isResidual: true,
    },
  ];

  return (
    <div
      data-testid="volume-rate-bridge-panel"
      className="pnl-attribution-bridge-panel"
    >
      <div
        className="pnl-attribution-bridge-panel__grid"
      >
        <div
          className="pnl-attribution-bridge-panel__summary"
        >
          <div>
            <div className="pnl-attribution-section-lead__eyebrow">规模 / 利率效应</div>
            <h3 className="pnl-attribution-bridge-panel__title">
              损益变动桥
            </h3>
            <div
              className={cx(
                "pnl-attribution-bridge-panel__value",
                valueToneClassName(summary.pnlChange),
              )}
            >
              {formatYi(summary.pnlChange)}
            </div>
            <div className="pnl-attribution-bridge-panel__periods">
              <span>
                {data.previous_period} {formatYi(summary.previousPnl)}
              </span>
              <span>→</span>
              <span>
                {data.current_period} {formatYi(summary.currentPnl)}
              </span>
            </div>
          </div>
          <div
            className="pnl-attribution-bridge-panel__status"
            data-status={summary.status}
          >
            <span>{summary.statusLabel}</span>
            <span className="pnl-attribution-tabular">
              解释覆盖 {formatPct(summary.coveragePct)}
            </span>
            <span data-testid="volume-rate-bridge-derived-note">
              解释覆盖与占变动为展示辅助计算（非正式指标）
            </span>
          </div>
        </div>

        <div className="pnl-attribution-bridge-panel__details">
          <div className="pnl-attribution-bridge-panel__details-header">
            <div className="pnl-attribution-bridge-panel__details-title">
              变动拆分
            </div>
            <div className="pnl-attribution-bridge-panel__unit">
              单位：亿元
            </div>
          </div>
          <div className="pnl-attribution-table-scroll">
            <table className="pnl-attribution-bridge-table">
              <thead>
                <tr>
                  <th className="pnl-attribution-bridge-table__left">
                    项目
                  </th>
                  <th className="pnl-attribution-bridge-table__left">
                    计算口径
                  </th>
                  <th className="pnl-attribution-bridge-table__num">
                    金额
                  </th>
                  <th className="pnl-attribution-bridge-table__num">
                    占变动
                  </th>
                </tr>
              </thead>
              <tbody>
                {bridgeRows.map((row) => {
                  const share =
                    denominator !== undefined && row.value !== undefined
                      ? Math.abs(row.value / denominator) * 100
                      : undefined;
                   return (
                     <tr
                       key={row.label}
                       className={cx(
                         row.isResidual &&
                           residualIsMaterial &&
                           "pnl-attribution-bridge-table__row--material-residual",
                       )}
                     >
                       <td className="pnl-attribution-bridge-table__label">
                         <span
                           className={cx(
                             "pnl-attribution-bridge-table__dot",
                             row.accentClass,
                           )}
                         />
                         {row.label}
                       </td>
                       <td className="pnl-attribution-bridge-table__formula">
                         {row.formula}
                       </td>
                       <td
                         className={cx(
                           "pnl-attribution-bridge-table__amount",
                           valueToneClassName(row.value),
                         )}
                       >
                         {formatYi(row.value)}
                       </td>
                       <td className="pnl-attribution-bridge-table__share">
                         {formatPct(share)}
                       </td>
                     </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="pnl-attribution-bridge-panel__footer">
        <span>损益变动 = 当期损益 - 上期损益</span>
        <span className="pnl-attribution-tabular">
          {formatYi(summary.volumeEffect)} + {formatYi(summary.rateEffect)} +{" "}
          {formatYi(summary.interactionEffect)} +{" "}
          {formatYi(summary.unexplainedEffect)} = {formatYi(summary.pnlChange)}
        </span>
      </div>
    </div>
  );
}

export function VolumeRateTabCharts(props: {
  data: VolumeRateAttributionPayload | null;
  meta: ResultMeta | null;
  isLoading: boolean;
  errorMessage: string | null;
  onRetry: () => void;
}) {
  const waterfallState: DataSectionState = derivePnlDataSectionState({
    meta: props.meta,
    isLoading: props.isLoading,
    isError: props.errorMessage !== null,
    errorMessage: props.errorMessage,
    isEmpty: false,
  });

  const volumeRateState: DataSectionState = derivePnlDataSectionState({
    meta: props.meta,
    isLoading: props.isLoading,
    isError: props.errorMessage !== null,
    errorMessage: props.errorMessage,
    isEmpty: !props.data || (props.data.items?.length ?? 0) === 0,
  });

  return (
    <>
      <AttributionWaterfallChart
        data={props.data}
        state={waterfallState}
        onRetry={props.onRetry}
      />
      <VolumeRateAnalysisChart
        data={props.data}
        state={volumeRateState}
        onRetry={props.onRetry}
      />
    </>
  );
}
