import type { CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";

import { useApiClient } from "../../../api/client";
import { designTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { formatChoiceMacroDelta, formatChoiceMacroValue } from "../../../utils/choiceMacroFormat";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import {
  BOND_ANALYTICS_MACRO_BAR_SERIES,
  buildMacroPointForDeltaDisplay,
  coalesceMacroSeriesDelta,
} from "../lib/bondAnalyticsMacroSeries";

const dt = designTokens;
const c = dt.color;

const wrapStyle: CSSProperties = {
  borderRadius: dt.radius.md,
  border: `1px solid ${c.neutral[200]}`,
  background: c.neutral[50],
  padding: `${dt.space[2]}px ${dt.space[3]}px`,
};

const emptyStyle: CSSProperties = {
  ...wrapStyle,
  borderStyle: "dashed",
  color: c.neutral[500],
  fontSize: dt.fontSize[13],
  textAlign: "center",
  padding: dt.space[4],
};

export function BondAnalyticsMacroMarketBar() {
  const client = useApiClient();
  const q = useQuery({
    queryKey: [...bondAnalyticsQueryKeyRoot, "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    staleTime: 60_000,
  });

  if (q.isPending) {
    return (
      <div style={wrapStyle} data-testid="bond-analytics-macro-bar-loading">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: dt.space[2], minHeight: 56 }}>
          <Spin size="small" />
          <span style={{ color: c.neutral[600], fontSize: dt.fontSize[12] }}>加载宏观序列…</span>
        </div>
      </div>
    );
  }

  const series = q.data?.result.series ?? [];
  const byId = new Map(series.map((p) => [p.series_id, p]));

  if (q.isError || series.length === 0) {
    return (
      <div style={emptyStyle} data-testid="bond-analytics-macro-bar-empty">
        暂无宏观序列
      </div>
    );
  }

  const cells = BOND_ANALYTICS_MACRO_BAR_SERIES.map((def) => {
    const point = byId.get(def.series_id);
    const delta = coalesceMacroSeriesDelta(point);
    const forDisplay = point ? buildMacroPointForDeltaDisplay(point, delta) : null;
    return { def, point, forDisplay };
  });

  const hasAnyLevel = cells.some((x) => x.point);
  if (!hasAnyLevel) {
    return (
      <div style={emptyStyle} data-testid="bond-analytics-macro-bar-empty">
        暂无宏观序列
      </div>
    );
  }

  return (
    <div
      style={wrapStyle}
      data-testid="bond-analytics-macro-bar"
      aria-label="宏观市场条"
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "stretch",
          gap: dt.space[3],
          justifyContent: "space-between",
        }}
      >
        {cells.map(({ def, point, forDisplay }) => (
          <div
            key={def.series_id}
            style={{
              flex: "1 1 120px",
              minWidth: 108,
              display: "grid",
              gap: 2,
            }}
          >
            <div style={{ fontSize: dt.fontSize[11], color: c.neutral[600], fontWeight: 600 }}>{def.shortLabel}</div>
            {point && forDisplay ? (
              <>
                <div
                  style={{
                    fontSize: dt.fontSize[16],
                    fontWeight: 700,
                    color: c.primary[800],
                    ...tabularNumsStyle,
                  }}
                >
                  {formatChoiceMacroValue(point)}
                </div>
                <div
                  style={{
                    fontSize: dt.fontSize[11],
                    color:
                      forDisplay.latest_change == null
                        ? c.neutral[500]
                        : forDisplay.latest_change > 0
                          ? c.danger[600]
                          : forDisplay.latest_change < 0
                            ? c.success[700]
                            : c.neutral[600],
                    ...tabularNumsStyle,
                  }}
                >
                  {formatChoiceMacroDelta(forDisplay, { emptyDisplay: "—" })}
                </div>
              </>
            ) : (
              <div style={{ fontSize: dt.fontSize[12], color: c.neutral[500] }}>—</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
