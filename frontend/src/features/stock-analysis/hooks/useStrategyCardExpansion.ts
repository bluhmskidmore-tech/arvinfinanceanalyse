import { useState } from "react";

export function useStrategyCardExpansion() {
  const [expandedStrategyCardIds, setExpandedStrategyCardIds] = useState<string[]>([]);

  const toggleStrategyCard = (id: string) => {
    setExpandedStrategyCardIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  const isStrategyCardExpanded = (id: string) => expandedStrategyCardIds.includes(id);

  return {
    expandedStrategyCardIds,
    toggleStrategyCard,
    isStrategyCardExpanded,
  };
}
