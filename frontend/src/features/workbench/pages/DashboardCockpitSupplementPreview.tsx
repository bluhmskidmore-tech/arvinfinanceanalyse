import { useEffect, useRef, type MouseEvent as ReactMouseEvent } from "react";
import { Link } from "react-router-dom";

import type { DashboardCockpitPreviewSignal } from "../dashboard/dashboardCockpitModel";

const DASHBOARD_DRILLDOWN_HIGHLIGHT_MS = 1600;

export function DashboardCockpitSupplementPreview({
  signals,
}: {
  signals: readonly DashboardCockpitPreviewSignal[];
}) {
  const activeDrilldownTargetRef = useRef<HTMLElement | null>(null);
  const activeDrilldownTimerRef = useRef<number | null>(null);

  const clearDrilldownHighlight = () => {
    if (activeDrilldownTimerRef.current !== null) {
      window.clearTimeout(activeDrilldownTimerRef.current);
      activeDrilldownTimerRef.current = null;
    }
    if (activeDrilldownTargetRef.current) {
      activeDrilldownTargetRef.current.removeAttribute("data-drilldown-active");
      activeDrilldownTargetRef.current = null;
    }
  };

  useEffect(() => clearDrilldownHighlight, []);

  const handleSectionDrilldown = (
    event: ReactMouseEvent<HTMLButtonElement>,
    targetTestIds: readonly string[],
  ) => {
    event.preventDefault();
    event.stopPropagation();
    const target = targetTestIds
      .map((testId) => document.querySelector<HTMLElement>(`[data-testid="${testId}"]`))
      .find((element): element is HTMLElement => element !== null);
    if (!target) {
      return;
    }
    clearDrilldownHighlight();
    target.setAttribute("data-drilldown-active", "true");
    activeDrilldownTargetRef.current = target;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    activeDrilldownTimerRef.current = window.setTimeout(() => {
      target.removeAttribute("data-drilldown-active");
      if (activeDrilldownTargetRef.current === target) {
        activeDrilldownTargetRef.current = null;
      }
      activeDrilldownTimerRef.current = null;
    }, DASHBOARD_DRILLDOWN_HIGHLIGHT_MS);
  };

  return (
    <div
      data-testid="dashboard-cockpit-supplement-preview"
      className="dashboard-cockpit-supplement-preview"
    >
      {signals.map((signal) => {
        const action =
          signal.id === "coverage"
            ? {
                kind: "route" as const,
                to: "/platform-config",
                label: "查看治理与数据来源",
              }
            : signal.id === "net-change"
              ? {
                  kind: "section" as const,
                  targetTestIds: ["dashboard-business-detail-strip"],
                  label: "查看区间变动",
                }
              : signal.id === "concentration"
                ? {
                    kind: "section" as const,
                    targetTestIds: [
                      "dashboard-cockpit-account-row-account-risk-review",
                      "dashboard-cockpit-account-table",
                    ],
                    label: "查看组合结构与风险摘要",
                  }
                : {
                    kind: "route" as const,
                    to: "/risk-tensor",
                    label: "查看风险张量",
                  };

        const content = (
          <>
            <span className="dashboard-cockpit-supplement-preview__label">{signal.label}</span>
            <strong className="dashboard-cockpit-supplement-preview__value">{signal.value}</strong>
            <span className="dashboard-cockpit-supplement-preview__detail">{signal.detail}</span>
          </>
        );

        return (
          <article
            key={signal.id}
            data-testid={`dashboard-cockpit-preview-${signal.id}`}
            className="dashboard-cockpit-supplement-preview__item"
            data-status={signal.status}
            data-tone={signal.tone}
          >
            {action.kind === "route" ? (
              <Link
                to={action.to}
                className="dashboard-cockpit-supplement-preview__trigger"
                aria-label={action.label}
                title={action.label}
                onClick={(event) => event.stopPropagation()}
              >
                {content}
              </Link>
            ) : (
              <button
                type="button"
                className="dashboard-cockpit-supplement-preview__trigger"
                aria-label={action.label}
                title={action.label}
                onClick={(event) => handleSectionDrilldown(event, action.targetTestIds)}
              >
                {content}
              </button>
            )}
          </article>
        );
      })}
    </div>
  );
}
