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

const DashboardPage = lazy(
  () => import("../features/workbench/pages/DashboardPage"),
);
const OperationsAnalysisPage = lazy(
  () => import("../features/workbench/pages/OperationsAnalysisPage"),
);
const PnlPage = lazy(() => import("../features/pnl/PnlPage"));
const FormalPnlV1Page = lazy(() => import("../features/pnl/FormalPnlV1Page"));
const PnlByBusinessPage = lazy(() => import("../features/pnl/PnlByBusinessPage"));
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
const DecisionItemsPage = lazy(
  () => import("../features/decision-items/pages/DecisionItemsPage"),
);

function routeElement(element: ReactNode) {
  return (
    <Suspense fallback={<WorkbenchRouteFallback />}>
      {element}
    </Suspense>
  );
}

function placeholderRoute(section: WorkbenchSection): RouteObject {
  return {
    path: section.path.slice(1),
    element: routeElement(<WorkbenchPlaceholderPage />),
  };
}

function buildWorkbenchChildRoutes(): RouteObject[] {
  return workbenchNavigation.map((section) => {
    if (section.path === "/") {
      return {
        index: true,
        element: routeElement(<DashboardPage />),
      };
    }

    if (section.readiness !== "live") {
      return placeholderRoute(section);
    }

    if (section.path === "/operations-analysis") {
      return {
        path: section.path.slice(1),
        element: routeElement(<OperationsAnalysisPage />),
      };
    }

    if (section.path === "/balance-analysis") {
      return {
        path: section.path.slice(1),
        element: routeElement(<BalanceAnalysisPage />),
      };
    }

    if (section.path === "/balance-movement-analysis") {
      return {
        path: section.path.slice(1),
        element: routeElement(<BalanceMovementAnalysisPage />),
      };
    }

    if (section.path === "/decision-items") {
      return {
        path: section.path.slice(1),
        element: routeElement(<DecisionItemsPage />),
      };
    }

    if (section.path === "/liability-analytics") {
      return {
        path: section.path.slice(1),
        element: routeElement(<LiabilityAnalyticsPage />),
      };
    }

    if (section.path === "/pnl") {
      return {
        path: section.path.slice(1),
        element: routeElement(<PnlPage />),
      };
    }

    if (section.path === "/pnl-bridge") {
      return {
        path: section.path.slice(1),
        element: routeElement(<PnlBridgePage />),
      };
    }

    if (section.path === "/pnl-attribution") {
      return {
        path: section.path.slice(1),
        element: routeElement(<PnlAttributionPage />),
      };
    }

    if (section.path === "/product-category-pnl") {
      return {
        path: section.path.slice(1),
        element: routeElement(<ProductCategoryPnlPage />),
      };
    }

    if (section.path === "/risk-tensor") {
      return {
        path: section.path.slice(1),
        element: routeElement(<RiskTensorPage />),
      };
    }

    if (section.path === "/concentration-monitor") {
      return {
        path: section.path.slice(1),
        element: routeElement(<ConcentrationMonitorPage />),
      };
    }

    if (section.path === "/cashflow-projection") {
      return {
        path: section.path.slice(1),
        element: routeElement(<CashflowProjectionPage />),
      };
    }

    if (section.path === "/bond-dashboard") {
      return {
        path: section.path.slice(1),
        element: routeElement(<BondDashboardPage />),
      };
    }

    if (section.path === "/bond-analysis") {
      return {
        path: section.path.slice(1),
        element: routeElement(<BondAnalyticsView />),
      };
    }

    if (section.path === "/cross-asset") {
      return {
        path: section.path.slice(1),
        element: routeElement(<CrossAssetPage />),
      };
    }

    if (section.path === "/market-data") {
      return {
        path: section.path.slice(1),
        element: routeElement(<MarketDataPage />),
      };
    }

    if (section.path === "/macro-toolkit") {
      return {
        path: section.path.slice(1),
        element: routeElement(<MacroToolkitPage />),
      };
    }

    if (section.path === "/positions") {
      return {
        path: section.path.slice(1),
        element: routeElement(<PositionsPage />),
      };
    }

    if (section.path === "/average-balance") {
      return {
        path: section.path.slice(1),
        element: routeElement(<AverageBalancePage />),
      };
    }

    if (section.path === "/ledger-pnl") {
      return {
        path: section.path.slice(1),
        element: routeElement(<LedgerPnlPage />),
      };
    }

    if (section.path === "/bank-ledger-dashboard") {
      return {
        path: section.path.slice(1),
        element: routeElement(<LedgerDashboardPage />),
      };
    }

    if (section.path === "/kpi") {
      return {
        path: section.path.slice(1),
        element: routeElement(<KpiPerformancePage />),
      };
    }

    if (section.path === "/team-performance") {
      return {
        path: section.path.slice(1),
        element: routeElement(<TeamPerformancePage />),
      };
    }

    if (section.path === "/platform-config") {
      return {
        path: section.path.slice(1),
        element: routeElement(<PlatformConfigPage />),
      };
    }

    return {
      path: section.path.slice(1),
      element: routeElement(<WorkbenchPlaceholderPage />),
    };
  });
}

export const workbenchSections: WorkbenchSection[] = primaryWorkbenchNavigation;

export const workbenchRoutes: RouteObject[] = [
  {
    path: "/",
    element: <WorkbenchShell />,
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
        path: "pnl-by-business",
        element: routeElement(<PnlByBusinessPage />),
      },
      {
        path: "pnl-formal-v1",
        element: routeElement(<FormalPnlV1Page />),
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
        element: routeElement(<CrossAssetPage />),
      },
      {
        path: "assets",
        element: <Navigate to="/bond-dashboard" replace />,
      },
      ...buildWorkbenchChildRoutes(),
      {
        path: "dashboard",
        element: routeElement(<DashboardPage />),
      },
      {
        path: "product-category-pnl/audit",
        element: routeElement(<ProductCategoryAdjustmentAuditPage />),
      },
    ],
  },
];
