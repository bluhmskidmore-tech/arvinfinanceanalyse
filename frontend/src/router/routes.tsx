import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { Navigate, type RouteObject } from "react-router-dom";

import { WorkbenchShell } from "../layouts/WorkbenchShell";
import {
  primaryWorkbenchNavigation,
  workbenchNavigation,
  type WorkbenchSection,
} from "../mocks/navigation";
import { WorkbenchRouteFallback } from "./WorkbenchRouteFallback";
import { WorkbenchNotFoundPage, WorkbenchRouteErrorBoundary } from "./WorkbenchRouteStatusPages";

const ThemedRouteBoundary = lazy(() => import("../app/ThemedRouteBoundary"));
const DashboardHomePage = lazy(
  () => import("../features/workbench/dashboard-home/DashboardHomePage"),
);
const ModuleWorkbenchHomePage = lazy(
  () => import("../features/workbench/module-home/ModuleWorkbenchHomePage"),
);
const RiskOverviewPage = lazy(
  () => import("../features/workbench/module-home/RiskOverviewPage"),
);
const PortfolioHomePage = lazy(
  () => import("../features/workbench/module-home/PortfolioHomePage"),
);
const MarketHomePage = lazy(
  () => import("../features/workbench/module-home/MarketHomePage"),
);
const OperationsAnalysisPage = lazy(
  () => import("../features/workbench/pages/OperationsAnalysisPage"),
);
const PnlPage = lazy(() => import("../features/pnl/PnlPage"));
const FormalPnlV1Page = lazy(() => import("../features/pnl/FormalPnlV1Page"));
const PnlByBusinessPage = lazy(() => import("../features/pnl/PnlByBusinessPage"));
const PnlByBusinessInsightsPage = lazy(
  () => import("../features/pnl-business-insights/PnlByBusinessInsightsPage"),
);
const PnlBridgePage = lazy(() => import("../features/pnl/PnlBridgePage"));
const PnlAttributionPage = lazy(
  () => import("../features/pnl-attribution/pages/PnlAttributionPage"),
);
const BalanceAnalysisPage = lazy(
  () => import("../features/balance-analysis/pages/BalanceAnalysisPage"),
);
const BalanceMovementAnalysisPage = lazy(
  () => import("../features/balance-movement-analysis/pages/BalanceMovementAnalysisPage"),
);
const LiabilityAnalyticsPage = lazy(
  () => import("../features/liability-analytics/pages/LiabilityAnalyticsPage"),
);
const ProductCategoryAdjustmentAuditPage = lazy(
  () => import("../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage"),
);
const ProductCategoryPnlPage = lazy(
  () => import("../features/product-category-pnl/pages/ProductCategoryPnlPage"),
);
const WorkbenchPlaceholderPage = lazy(
  () => import("../features/workbench/pages/WorkbenchPlaceholderPage"),
);
const RiskTensorPage = lazy(
  () => import("../features/risk-tensor/RiskTensorPage"),
);
const ConcentrationMonitorPage = lazy(
  () => import("../features/concentration-monitor/ConcentrationMonitorPage"),
);
const CashflowProjectionPage = lazy(
  () => import("../features/cashflow-projection/pages/CashflowProjectionPage"),
);
const BondAnalyticsView = lazy(
  () => import("../features/bond-analytics/components/BondAnalyticsView"),
);
const BondTradingDeskPage = lazy(
  () => import("../features/bond-trading-desk/pages/BondTradingDeskPage"),
);
const BondDashboardPage = lazy(
  () => import("../features/bond-dashboard/pages/BondDashboardPage"),
);
const PositionsPage = lazy(() => import("../features/positions/pages/PositionsPage"));
const AverageBalancePage = lazy(
  () => import("../features/average-balance/pages/AverageBalancePage"),
);
const LedgerPnlPage = lazy(
  () => import("../features/ledger-pnl/pages/LedgerPnlPage"),
);
const LedgerDashboardPage = lazy(
  () => import("../features/ledger-dashboard/pages/LedgerDashboardPage"),
);
const KpiPerformancePage = lazy(
  () => import("../features/kpi-performance/pages/KpiPerformancePage"),
);
const TeamPerformancePage = lazy(
  () => import("../features/team-performance/TeamPerformancePage"),
);
const PlatformConfigPage = lazy(
  () => import("../features/platform-config/PlatformConfigPage"),
);
const CrossAssetPage = lazy(() => import("../features/cross-asset/pages/CrossAssetPage"));
const MarketDataPage = lazy(
  () => import("../features/market-data/pages/MarketDataPage"),
);
const MacroToolkitPage = lazy(
  () => import("../features/macro-toolkit/pages/MacroToolkitPage"),
);
const CubeQueryPage = lazy(() => import("../features/cube-query/pages/CubeQueryPage"));
const StockAnalysisPage = lazy(
  () => import("../features/stock-analysis/pages/StockAnalysisPage"),
);
const EquityCockpitPrototypePage = lazy(
  () => import("../features/prototype/EquityCockpitPrototypePage"),
);
const DecisionItemsPage = lazy(
  () => import("../features/decision-items/pages/DecisionItemsPage"),
);
const NewsEventsPage = lazy(() => import("../features/news-events/NewsEventsPage"));
const AgentWorkbenchPage = lazy(() => import("../features/agent/AgentWorkbenchPage"));

function routeElement(element: ReactNode) {
  return (
    <Suspense fallback={<WorkbenchRouteFallback />}>
      {element}
    </Suspense>
  );
}

function themedRouteElement(element: ReactNode) {
  return routeElement(<ThemedRouteBoundary>{element}</ThemedRouteBoundary>);
}

function parseEnvDataSourceMode() {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  return typeof raw === "string" ? raw.trim().toLowerCase() : "";
}

const equityPrototypeRouteEnabled =
  import.meta.env.DEV === true && parseEnvDataSourceMode() === "mock";

function placeholderRoute(section: WorkbenchSection): RouteObject {
  return {
    path: section.path.slice(1),
    element: themedRouteElement(<WorkbenchPlaceholderPage />),
  };
}

function buildWorkbenchChildRoutes(): RouteObject[] {
  return workbenchNavigation.map((section) => {
    if (section.path === "/") {
      return {
        index: true,
        element: routeElement(<DashboardHomePage />),
      };
    }

    if (section.readiness !== "live") {
      return placeholderRoute(section);
    }

    if (section.path === "/operations-analysis") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<OperationsAnalysisPage />),
      };
    }

    if (section.path === "/portfolio") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PortfolioHomePage />),
      };
    }

    if (section.path === "/market-overview") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<MarketHomePage />),
      };
    }

    if (section.path === "/risk-overview") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<RiskOverviewPage />),
      };
    }

    if (section.path === "/performance") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<ModuleWorkbenchHomePage kind="performance" />),
      };
    }

    if (section.path === "/reports") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<ModuleWorkbenchHomePage kind="governance" />),
      };
    }

    if (section.path === "/balance-analysis") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<BalanceAnalysisPage />),
      };
    }

    if (section.path === "/balance-movement-analysis") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<BalanceMovementAnalysisPage />),
      };
    }

    if (section.path === "/decision-items") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<DecisionItemsPage />),
      };
    }

    if (section.path === "/liability-analytics") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<LiabilityAnalyticsPage />),
      };
    }

    if (section.path === "/pnl") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PnlPage />),
      };
    }

    if (section.path === "/pnl-by-business") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PnlByBusinessPage />),
      };
    }

    if (section.path === "/pnl-by-business-insights") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PnlByBusinessInsightsPage />),
      };
    }

    if (section.path === "/pnl-bridge") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PnlBridgePage />),
      };
    }

    if (section.path === "/pnl-attribution") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PnlAttributionPage />),
      };
    }

    if (section.path === "/product-category-pnl") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<ProductCategoryPnlPage />),
      };
    }

    if (section.path === "/risk-tensor") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<RiskTensorPage />),
      };
    }

    if (section.path === "/concentration-monitor") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<ConcentrationMonitorPage />),
      };
    }

    if (section.path === "/cashflow-projection") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<CashflowProjectionPage />),
      };
    }

    if (section.path === "/bond-dashboard") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<BondDashboardPage />),
      };
    }

    if (section.path === "/bond-analysis") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<BondAnalyticsView />),
      };
    }

    if (section.path === "/bond-trading-desk") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<BondTradingDeskPage />),
      };
    }

    if (section.path === "/cross-asset") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<CrossAssetPage />),
      };
    }

    if (section.path === "/market-data") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<MarketDataPage />),
      };
    }

    if (section.path === "/macro-observation") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<MacroToolkitPage mode="observation" />),
      };
    }

    if (section.path === "/macro-toolkit") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<MacroToolkitPage />),
      };
    }

    if (section.path === "/cube-query") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<CubeQueryPage />),
      };
    }

    if (section.path === "/stock-analysis") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<StockAnalysisPage />),
      };
    }

    if (section.path === "/news-events") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<NewsEventsPage />),
      };
    }

    if (section.path === "/agent") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<AgentWorkbenchPage />),
      };
    }

    if (section.path === "/positions") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PositionsPage />),
      };
    }

    if (section.path === "/average-balance") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<AverageBalancePage />),
      };
    }

    if (section.path === "/ledger-pnl") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<LedgerPnlPage />),
      };
    }

    if (section.path === "/bank-ledger-dashboard") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<LedgerDashboardPage />),
      };
    }

    if (section.path === "/kpi") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<KpiPerformancePage />),
      };
    }

    if (section.path === "/team-performance") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<TeamPerformancePage />),
      };
    }

    if (section.path === "/platform-config") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<PlatformConfigPage />),
      };
    }

    return {
      path: section.path.slice(1),
      element: themedRouteElement(<WorkbenchPlaceholderPage />),
    };
  });
}

export const workbenchSections: WorkbenchSection[] = primaryWorkbenchNavigation;

export const workbenchRoutes: RouteObject[] = [
  {
    path: "/",
    element: <WorkbenchShell />,
    errorElement: routeElement(<WorkbenchRouteErrorBoundary />),
    children: [
      {
        path: "macro-analysis",
        element: <Navigate to="/market-data" replace />,
      },
      {
        path: "adb",
        element: <Navigate to="/average-balance" replace />,
      },
      {
        path: "pnl-formal-v1",
        element: themedRouteElement(<FormalPnlV1Page />),
      },
      {
        path: "liabilities",
        element: <Navigate to="/liability-analytics" replace />,
      },
      {
        path: "bonds",
        element: <Navigate to="/bond-dashboard" replace />,
      },
      {
        path: "bond-analytics-advanced",
        element: <Navigate to="/bond-analysis" replace />,
      },
      {
        path: "market",
        element: <Navigate to="/market-data" replace />,
      },
      {
        path: "cross-asset-drivers",
        element: themedRouteElement(<CrossAssetPage />),
      },
      {
        path: "assets",
        element: <Navigate to="/bond-dashboard" replace />,
      },
      ...buildWorkbenchChildRoutes(),
      {
        path: "dashboard",
        element: routeElement(<DashboardHomePage />),
      },
      {
        path: "政策与资金面",
        element: routeElement(<DashboardHomePage />),
      },
      {
        path: "product-category-pnl/audit",
        element: themedRouteElement(<ProductCategoryAdjustmentAuditPage />),
      },
      {
        path: "*",
        element: themedRouteElement(<WorkbenchNotFoundPage />),
      },
    ],
  },
  ...(equityPrototypeRouteEnabled
    ? [
        {
          path: "/prototype/equity-cockpit",
          element: themedRouteElement(<EquityCockpitPrototypePage />),
        } satisfies RouteObject,
      ]
    : []),
];
