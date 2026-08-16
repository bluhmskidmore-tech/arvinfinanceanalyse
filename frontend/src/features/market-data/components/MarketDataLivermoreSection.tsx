import { useState } from "react";
import type { ReactNode } from "react";
import { Collapse } from "antd";

import type { LivermoreGateSupplementRefreshAcceptance } from "../../../api/marketDataClient";
import type { LivermoreStrategyModel } from "../lib/livermoreStrategyModel";
import { LivermoreStrategyPanel } from "./LivermoreStrategyPanel";
import "./LivermoreStrategyPanel.css";

type MarketDataLivermoreSectionProps = {
  model: LivermoreStrategyModel | null;
  isLoading: boolean;
  isError: boolean;
  fetchErrorDetail: string | null;
  onRetry: () => void;
  onRefreshGateSupplement?: () => Promise<LivermoreGateSupplementRefreshAcceptance>;
  onExpandedChange: (expanded: boolean) => void;
};

type GateStateTone = "green" | "amber" | "red" | "muted";

function gateStateTone(state: LivermoreStrategyModel["marketGate"]["state"]): GateStateTone {
  if (state === "HOT") {
    return "green";
  }
  if (state === "WARM" || state === "OVERHEAT" || state === "STALE") {
    return "amber";
  }
  if (state === "OFF") {
    return "red";
  }
  return "muted";
}

function livermoreCollapseLabel(
  model: LivermoreStrategyModel | null,
  isLoading: boolean,
): ReactNode {
  const state = model?.marketGate.state ?? null;
  const hint = isLoading ? "加载中…" : "A股防守策略";
  return (
    <span className="livermore-collapse-label">
      <span className="livermore-collapse-label__title">Livermore 趋势门控</span>
      {state ? (
        <span className="livermore-collapse-label__state" data-tone={gateStateTone(state)}>
          门控 {state}
        </span>
      ) : null}
      <span className="livermore-collapse-label__hint">{hint}</span>
    </span>
  );
}

export function MarketDataLivermoreSection({
  model,
  isLoading,
  isError,
  fetchErrorDetail,
  onRetry,
  onRefreshGateSupplement,
  onExpandedChange,
}: MarketDataLivermoreSectionProps) {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const expanded = activeKeys.includes("livermore");

  return (
    <section className="market-data-section-block" data-testid="market-data-livermore-section">
      <Collapse
        className="market-data-livermore-collapse"
        data-testid="market-data-livermore-collapse"
        bordered={false}
        activeKey={activeKeys}
        onChange={(keys) => {
          const nextKeys = Array.isArray(keys) ? keys : [keys];
          const nextExpanded = nextKeys.includes("livermore");
          setActiveKeys(nextKeys);
          onExpandedChange(nextExpanded);
        }}
        items={[
          {
            key: "livermore",
            label: livermoreCollapseLabel(model, isLoading && expanded),
            children: expanded ? (
              <LivermoreStrategyPanel
                model={model}
                isLoading={isLoading}
                isError={isError}
                fetchErrorDetail={fetchErrorDetail}
                onRetry={() => void onRetry()}
                onRefreshGateSupplement={onRefreshGateSupplement}
              />
            ) : null,
          },
        ]}
      />
    </section>
  );
}
