import { Suspense, lazy } from "react";
import { Tabs } from "antd";
import type { PeriodType } from "../types";
import {
  getBondAnalyticsModuleDefinition,
  type BondAnalyticsModuleKey,
} from "../lib/bondAnalyticsModuleRegistry";

const ReturnDecompositionView = lazy(() =>
  import("./ReturnDecompositionView").then((module) => ({
    default: module.ReturnDecompositionView,
  })),
);
const BenchmarkExcessView = lazy(() =>
  import("./BenchmarkExcessView").then((module) => ({
    default: module.BenchmarkExcessView,
  })),
);
const KRDCurveRiskView = lazy(() =>
  import("./KRDCurveRiskView").then((module) => ({
    default: module.KRDCurveRiskView,
  })),
);
const CreditSpreadView = lazy(() =>
  import("./CreditSpreadView").then((module) => ({
    default: module.CreditSpreadView,
  })),
);
const ActionAttributionView = lazy(() =>
  import("./ActionAttributionView").then((module) => ({
    default: module.ActionAttributionView,
  })),
);
const AccountingClassAuditView = lazy(() =>
  import("./AccountingClassAuditView").then((module) => ({
    default: module.AccountingClassAuditView,
  })),
);

const TAB_ITEMS: Array<{ key: BondAnalyticsModuleKey; label: string }> = [
  { key: "return-decomposition", label: "Return decomposition" },
  { key: "benchmark-excess", label: "Benchmark excess" },
  { key: "krd-curve-risk", label: "KRD curve risk" },
  { key: "credit-spread", label: "Credit spread" },
  { key: "action-attribution", label: "Action attribution" },
  { key: "accounting-audit", label: "Accounting audit" },
];

interface BondAnalyticsDetailSectionProps {
  activeTab: BondAnalyticsModuleKey;
  onActiveTabChange: (key: BondAnalyticsModuleKey) => void;
  reportDate: string;
  periodType: PeriodType;
}

function renderActiveModule(
  activeTab: BondAnalyticsModuleKey,
  reportDate: string,
  periodType: PeriodType,
) {
  if (activeTab === "return-decomposition") {
    return (
      <ReturnDecompositionView
        reportDate={reportDate}
        periodType={periodType}
      />
    );
  }

  if (activeTab === "benchmark-excess") {
    return (
      <BenchmarkExcessView
        reportDate={reportDate}
        periodType={periodType}
      />
    );
  }

  if (activeTab === "krd-curve-risk") {
    return <KRDCurveRiskView reportDate={reportDate} />;
  }

  if (activeTab === "credit-spread") {
    return <CreditSpreadView reportDate={reportDate} />;
  }

  if (activeTab === "action-attribution") {
    return (
      <ActionAttributionView
        reportDate={reportDate}
        periodType={periodType}
      />
    );
  }

  return <AccountingClassAuditView reportDate={reportDate} />;
}

export function BondAnalyticsDetailSection({
  activeTab,
  onActiveTabChange,
  reportDate,
  periodType,
}: BondAnalyticsDetailSectionProps) {
  const activeModule = getBondAnalyticsModuleDefinition(activeTab);

  return (
    <section
      style={{ display: "flex", flexDirection: "column", gap: 12 }}
      data-testid="bond-analysis-detail-section"
      data-module-key={activeTab}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>Analysis details</h3>
        <div style={{ color: "#8090a8", fontSize: 13 }}>
          Currently viewing: {activeModule.label}
        </div>
        <div style={{ color: "#5c6b82", fontSize: 13 }}>{activeModule.description}</div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => onActiveTabChange(key as BondAnalyticsModuleKey)}
        items={TAB_ITEMS.map((item) => ({
          key: item.key,
          label: item.label,
          children: null,
        }))}
      />

      <Suspense
        fallback={
          <div
            style={{ color: "#8090a8", fontSize: 13 }}
            data-testid="bond-analysis-detail-loading"
          >
            Loading panel...
          </div>
        }
      >
        <div>{renderActiveModule(activeTab, reportDate, periodType)}</div>
      </Suspense>
    </section>
  );
}

export default BondAnalyticsDetailSection;
