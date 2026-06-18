import { useState } from "react";
import { Collapse } from "antd";

import type { LivermoreStrategyModel } from "../lib/livermoreStrategyModel";
import { LivermoreStrategyPanel } from "./LivermoreStrategyPanel";

type MarketDataLivermoreSectionProps = {
  model: LivermoreStrategyModel | null;
  isLoading: boolean;
  isError: boolean;
  fetchErrorDetail: string | null;
  onRetry: () => void;
  onRefreshGateSupplement?: () => Promise<{ status: string; computed_rows: number; message?: string }>;
  onExpandedChange: (expanded: boolean) => void;
};

function livermoreCollapseLabel(model: LivermoreStrategyModel | null, isLoading: boolean): string {
  if (isLoading) {
    return "Livermore 趋势门控（加载中…）";
  }
  if (model?.marketGate.state) {
    return `Livermore 趋势门控 · 门控 ${model.marketGate.state}（点击展开）`;
  }
  return "Livermore 趋势门控（A股防守策略，点击展开）";
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
