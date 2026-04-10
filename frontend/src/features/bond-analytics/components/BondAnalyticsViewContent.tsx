import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import type { ActionAttributionResponse, PeriodType } from "../types";
import type { BondAnalyticsModuleKey } from "../lib/bondAnalyticsModuleRegistry";
import { buildBondAnalyticsOverviewModel } from "../lib/bondAnalyticsOverviewModel";

const BondAnalyticsOverviewPanels = lazy(() => import("./BondAnalyticsOverviewPanels"));

const BondAnalyticsDetailSection = lazy(() =>
  import("./BondAnalyticsDetailSection").then((module) => ({
    default: module.BondAnalyticsDetailSection,
  })),
);

function generateRecentDates(): { value: string; label: string }[] {
  const dates: { value: string; label: string }[] = [];
  const now = new Date();

  for (let i = 1; i <= 12; i += 1) {
    const date = new Date(now.getFullYear(), now.getMonth() - i + 1, 0);
    const value = date.toISOString().slice(0, 10);
    dates.push({
      value,
      label: value,
    });
  }

  return dates;
}

export function BondAnalyticsViewContent() {
  const dateOptions = useMemo(() => generateRecentDates(), []);
  const [reportDate, setReportDate] = useState(dateOptions[0]?.value ?? "");
  const [periodType, setPeriodType] = useState<PeriodType>("MoM");
  const [activeTab, setActiveTab] =
    useState<BondAnalyticsModuleKey>("return-decomposition");
  const [actionAttribution, setActionAttribution] =
    useState<ActionAttributionResponse | null>(null);
  const [actionAttributionLoading, setActionAttributionLoading] = useState(false);
  const [actionAttributionError, setActionAttributionError] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let cancelled = false;

    const fetchActionAttribution = async () => {
      setActionAttributionLoading(true);
      setActionAttributionError(null);

      try {
        const params = new URLSearchParams({
          report_date: reportDate,
          period_type: periodType,
        });
        const response = await fetch(
          `/api/bond-analytics/action-attribution?${params.toString()}`,
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const json = await response.json();
        if (!cancelled) {
          setActionAttribution(json.result as ActionAttributionResponse);
        }
      } catch (error: unknown) {
        if (!cancelled) {
          setActionAttribution(null);
          setActionAttributionError((error as Error).message);
        }
      } finally {
        if (!cancelled) {
          setActionAttributionLoading(false);
        }
      }
    };

    if (reportDate) {
      void fetchActionAttribution();
    }

    return () => {
      cancelled = true;
    };
  }, [periodType, reportDate]);

  const overviewModel = buildBondAnalyticsOverviewModel({
    reportDate,
    periodType,
    actionAttribution,
    actionAttributionLoading,
    actionAttributionError,
  });

  return (
    <div
      style={{ display: "flex", flexDirection: "column", gap: 16 }}
      data-testid="bond-analysis-overview"
    >
      <Suspense
        fallback={
          <div style={{ color: "#8090a8", fontSize: 13 }} data-testid="bond-analysis-overview-loading">
            Loading overview...
          </div>
        }
      >
        <BondAnalyticsOverviewPanels
          dateOptions={dateOptions}
          reportDate={reportDate}
          onReportDateChange={setReportDate}
          periodType={periodType}
          onPeriodTypeChange={setPeriodType}
          overviewModel={overviewModel}
          onOpenModuleDetail={setActiveTab}
        />
      </Suspense>

      <section
        style={{ display: "flex", flexDirection: "column", gap: 12 }}
      >
        <Suspense
          fallback={
            <div style={{ color: "#8090a8", fontSize: 13 }} data-testid="bond-analysis-detail-loading">
              Loading detail module...
            </div>
          }
        >
          <BondAnalyticsDetailSection
            activeTab={activeTab}
            onActiveTabChange={setActiveTab}
            reportDate={reportDate}
            periodType={periodType}
          />
        </Suspense>
      </section>
    </div>
  );
}

export default BondAnalyticsViewContent;
