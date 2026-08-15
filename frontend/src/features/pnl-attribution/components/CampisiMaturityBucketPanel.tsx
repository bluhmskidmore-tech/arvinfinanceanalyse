import type { CampisiMaturityBucketsPayload } from "../../../api/contracts";
import type { DataSectionState } from "../../../components/DataSection.types";
import { PageDataSection } from "../../../components/page/PageDataSection";
import "./campisiPanels.css";

// 本面板挂在 Nocturne 深色路由（theme-dh-api + pnl-attribution scope）下：
// 布局与面色收敛到共享 campisiPanels.css（--dh-api-* var 链），禁止浅色 hex、
// designTokens 浅色 neutral 或 --ib-*（路由边界已算成钢蓝字面值）直灌。

function toYi(value: number) {
  return (value / 100_000_000).toFixed(2);
}

type Props = {
  data: CampisiMaturityBucketsPayload | null;
  state: DataSectionState;
  onRetry: () => void;
};

export function CampisiMaturityBucketPanel({ data, state, onRetry }: Props) {
  const rows = Object.entries(data?.buckets ?? {});

  return (
    <PageDataSection title="Campisi 到期桶拆解" state={state} onRetry={onRetry}>
      <div className="campisi-panel">
        <p className="campisi-panel__intro">
          按剩余期限桶查看票息、国债曲线、利差和选券效应的分布，便于和久期结构联读。
        </p>
        <table className="campisi-table">
          <thead>
            <tr>
              <th>到期桶</th>
              <th className="campisi-table__numeric-head">票息(亿)</th>
              <th className="campisi-table__numeric-head">国债(亿)</th>
              <th className="campisi-table__numeric-head">利差(亿)</th>
              <th className="campisi-table__numeric-head">剩余/选券(亿)</th>
              <th className="campisi-table__numeric-head">总收益(亿)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([bucket, metrics]) => (
              <tr key={bucket}>
                <td>{bucket}</td>
                <td className="campisi-table__numeric-cell">
                  {toYi(metrics.income_return)}
                </td>
                <td className="campisi-table__numeric-cell">
                  {toYi(metrics.treasury_effect)}
                </td>
                <td className="campisi-table__numeric-cell">
                  {toYi(metrics.spread_effect)}
                </td>
                <td className="campisi-table__numeric-cell">
                  {toYi(metrics.selection_effect)}
                </td>
                <td className="campisi-table__numeric-cell">
                  {toYi(metrics.total_return)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageDataSection>
  );
}
