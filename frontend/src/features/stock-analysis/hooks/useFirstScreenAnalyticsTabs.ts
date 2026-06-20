import { useState } from "react";

export type FirstScreenAnalyticsTab = "consensus" | "priority" | "optimization";

export function useFirstScreenAnalyticsTabs() {
  const [firstScreenAnalyticsTab, setFirstScreenAnalyticsTab] =
    useState<FirstScreenAnalyticsTab>("consensus");
  const [firstScreenAnalyticsRequested, setFirstScreenAnalyticsRequested] = useState(false);

  function handleFirstScreenAnalyticsTabChange(key: string) {
    const tab = key as FirstScreenAnalyticsTab;
    setFirstScreenAnalyticsTab(tab);
    if (tab === "priority" || tab === "optimization") {
      setFirstScreenAnalyticsRequested(true);
    }
  }

  return {
    firstScreenAnalyticsTab,
    firstScreenAnalyticsRequested,
    handleFirstScreenAnalyticsTabChange,
  };
}
