import { useState } from "react";

export type FirstScreenAnalyticsTab = "consensus" | "priority" | "optimization";
type DeferredFirstScreenAnalyticsTab = Exclude<FirstScreenAnalyticsTab, "consensus">;

type FirstScreenAnalyticsRequests = Record<DeferredFirstScreenAnalyticsTab, boolean>;

const initialFirstScreenAnalyticsRequests: FirstScreenAnalyticsRequests = {
  priority: false,
  optimization: false,
};

export function useFirstScreenAnalyticsTabs() {
  const [firstScreenAnalyticsTab, setFirstScreenAnalyticsTab] =
    useState<FirstScreenAnalyticsTab>("consensus");
  const [firstScreenAnalyticsRequests, setFirstScreenAnalyticsRequests] =
    useState<FirstScreenAnalyticsRequests>(initialFirstScreenAnalyticsRequests);
  const firstScreenPriorityRequested = firstScreenAnalyticsRequests.priority;
  const firstScreenOptimizationRequested = firstScreenAnalyticsRequests.optimization;
  const firstScreenAnalyticsRequested =
    firstScreenPriorityRequested || firstScreenOptimizationRequested;

  function handleFirstScreenAnalyticsTabChange(key: string) {
    const tab = key as FirstScreenAnalyticsTab;
    setFirstScreenAnalyticsTab(tab);
    if (tab === "priority" || tab === "optimization") {
      setFirstScreenAnalyticsRequests((current) => ({ ...current, [tab]: true }));
    }
  }

  return {
    firstScreenAnalyticsTab,
    firstScreenAnalyticsRequested,
    firstScreenPriorityRequested,
    firstScreenOptimizationRequested,
    handleFirstScreenAnalyticsTabChange,
  };
}
