import { Suspense, lazy } from "react";
import { Tabs } from "antd";
import type {
  BondAnalyticsAccountingClassFilter,
  BondAnalyticsAssetClassFilter,
  BondAnalyticsScenarioSetFilter,
  PeriodType,
} from "../types";
import {
  getBondAnalyticsModuleDefinition,
  type BondAnalyticsModuleKey,
} from "../lib/bondAnalyticsModuleRegistry";
import styles from "./BondAnalyticsDetailSection.module.css";

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
const PortfolioHeadlinesView = lazy(() =>
  import("./PortfolioHeadlinesView").then((module) => ({
    default: module.PortfolioHeadlinesView,
  })),
);
const TopHoldingsView = lazy(() =>
  import("./TopHoldingsView").then((module) => ({
    default: module.TopHoldingsView,
  })),
);

const TAB_ITEMS: Array<{ key: BondAnalyticsModuleKey; label: string }> = [
  { key: "return-decomposition", label: "收益分解" },
  { key: "benchmark-excess", label: "基准超额" },
  { key: "krd-curve-risk", label: "KRD 曲线风险" },
  { key: "credit-spread", label: "信用利差" },
  { key: "portfolio-headlines", label: "组合头条" },
  { key: "top-holdings", label: "重仓券" },
  { key: "action-attribution", label: "动作归因" },
  { key: "accounting-audit", label: "会计分类审计" },
];

interface BondAnalyticsDetailSectionProps {
  activeTab: BondAnalyticsModuleKey;
  onActiveTabChange: (key: BondAnalyticsModuleKey) => void;
  reportDate: string;
  periodType: PeriodType;
  assetClass: BondAnalyticsAssetClassFilter;
  accountingClass: BondAnalyticsAccountingClassFilter;
  scenarioSet: BondAnalyticsScenarioSetFilter;
  spreadScenarios: string;
}

function renderActiveModule(
  activeTab: BondAnalyticsModuleKey,
  reportDate: string,
  periodType: PeriodType,
  assetClass: BondAnalyticsAssetClassFilter,
  accountingClass: BondAnalyticsAccountingClassFilter,
  scenarioSet: BondAnalyticsScenarioSetFilter,
  spreadScenarios: string,
) {
  if (activeTab === "return-decomposition") {
    return (
      <ReturnDecompositionView
        reportDate={reportDate}
        periodType={periodType}
        assetClass={assetClass}
        accountingClass={accountingClass}
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
    return <KRDCurveRiskView reportDate={reportDate} scenarioSet={scenarioSet} />;
  }

  if (activeTab === "credit-spread") {
    return <CreditSpreadView reportDate={reportDate} spreadScenarios={spreadScenarios} />;
  }

  if (activeTab === "portfolio-headlines") {
    return <PortfolioHeadlinesView reportDate={reportDate} />;
  }

  if (activeTab === "top-holdings") {
    return <TopHoldingsView reportDate={reportDate} />;
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
  assetClass,
  accountingClass,
  scenarioSet,
  spreadScenarios,
}: BondAnalyticsDetailSectionProps) {
  const activeModule = getBondAnalyticsModuleDefinition(activeTab);

  return (
    <section
      className={styles.detailSection}
      data-testid="bond-analysis-detail-section"
      data-module-key={activeTab}
    >
      <div className={styles.header} data-testid="bond-analysis-detail-header">
        <div className={styles.headingStack}>
          <h3 className={styles.title}>分析明细</h3>
          <p className={styles.description}>{activeModule.description}</p>
        </div>
        <div className={styles.activeModule}>
          当前查看：{activeModule.label}
        </div>
      </div>

      <Tabs
        className={styles.tabRail}
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
            className={styles.loadingState}
            data-testid="bond-analysis-detail-loading"
          >
            正在加载面板...
          </div>
        }
      >
        <div className={styles.contentFrame} data-testid="bond-analysis-detail-content">
          {renderActiveModule(
            activeTab,
            reportDate,
            periodType,
            assetClass,
            accountingClass,
            scenarioSet,
            spreadScenarios,
          )}
        </div>
      </Suspense>
    </section>
  );
}

export default BondAnalyticsDetailSection;
