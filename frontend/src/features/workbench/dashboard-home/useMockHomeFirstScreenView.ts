import { useEffect, useState } from "react";

import type { DashboardHomeFirstScreenView } from "./dashboardHomeFirstScreenTypes";

export function useMockHomeFirstScreenView(enabled: boolean): DashboardHomeFirstScreenView | null {
  const [view, setView] = useState<DashboardHomeFirstScreenView | null>(null);

  useEffect(() => {
    if (!enabled) {
      setView(null);
      return undefined;
    }

    let isActive = true;
    void import("./dashboardHomeFirstScreenMockView").then((module) => {
      if (isActive) {
        setView(module.createMockHomeFirstScreenView());
      }
    });

    return () => {
      isActive = false;
    };
  }, [enabled]);

  return view;
}
