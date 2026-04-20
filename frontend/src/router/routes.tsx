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
const SourcePreviewPage = lazy(
  () => import("../features/source-preview/pages/SourcePreviewPage"),
);
const MarketDataPage = lazy(
  () => import("../features/market-data/pages/MarketDataPage"),
);
const PnlPage = lazy(() => import("../features/pnl/PnlPage"));
const PnlBridgePage = lazy(() => import("../features/pnl/PnlBridgePage"));
const PnlAttributionPage = lazy(
  () => import("../features/pnl-attribution/pages/PnlAttributionPage"),
);
const BalanceAnalysisPage = lazy(
  () => import("../features/balance-analysis/pages/BalanceAnalysisPage"),
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
const AgentWorkbenchPage = lazy(
  () => import("../features/agent/AgentWorkbenchPage"),
);
const NewsEventsPage = lazy(
  () => import("../features/news-events/NewsEventsPage"),
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
const RiskOverviewPage = lazy(
  () => import("../features/risk-overview/RiskOverviewPage"),
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
const KpiPerformancePage = lazy(
  () => import("../features/kpi-performance/pages/KpiPerformancePage"),
);
const TeamPerformancePage = lazy(
  () => import("../features/team-performance/TeamPerformancePage"),
);
const PlatformConfigPage = lazy(
  () => import("../features/platform-config/PlatformConfigPage"),
);
const CubeQueryPage = lazy(() => import("../features/cube-query/pages/CubeQueryPage"));
const CrossAssetPage = lazy(() => import("../features/cross-asset/pages/CrossAssetPage"));

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

/**
 * Workbench paths whose React pages are implemented while navigation readiness is still "placeholder".
 * The readiness gate would otherwise render WorkbenchPlaceholderPage for those paths; listing them here
 * bypasses that until the route is promoted to `live` in navigation metadata (then the entry is redundant
 * and should be removed). Currently only routes that remain placeholder in `navigation.ts` need to appear.
 */
const READINESS_IMPLEMENTED_PATHS = new Set<string>(["/cube-query"]);

function buildWorkbenchChildRoutes(): RouteObject[] {
  return workbenchNavigation.map((section) => {
    if (section.path === "/") {
      return {
        index: true,
        element: routeElement(<DashboardPage />),
      };
    }

    const bypassReadiness =
      section.path === "/agent" || READINESS_IMPLEMENTED_PATHS.has(section.path);

    if (!bypassReadiness && section.readiness !== "live") {
      return placeholderRoute(section);
    }

    if (section.path === "/operations-analysis") {
      return {
        path: section.path.slice(1),
        element: routeElement(<OperationsAnalysisPage />),
      };
    }

    if (section.path === "/agent") {
      return {
        path: section.path.slice(1),
        element: routeElement(<AgentWorkbenchPage />),
      };
    }

    if (section.path === "/news-events") {
      return {
        path: section.path.slice(1),
        element: routeElement(<NewsEventsPage />),
      };
    }

    if (section.path === "/balance-analysis") {
      return {
        path: section.path.slice(1),
        element: routeElement(<BalanceAnalysisPage />),
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

    if (section.path === "/risk-overview") {
      return {
        path: section.path.slice(1),
        element: routeElement(<RiskOverviewPage />),
      };
    }

    if (section.path === "/market-data") {
      return {
        path: section.path.slice(1),
        element: routeElement(<MarketDataPage />),
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

    if (section.path === "/cube-query") {
      return {
        path: section.path.slice(1),
        element: routeElement(<CubeQueryPage />),
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
        element: <Navigate to="/ledger-pnl" replace />,
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
        path: "assets",
        element: <Navigate to="/bond-dashboard" replace />,
      },
      ...buildWorkbenchChildRoutes(),
      {
        path: "dashboard",
        element: routeElement(<DashboardPage />),
      },
      {
        path: "source-preview",
        element: routeElement(<SourcePreviewPage />),
      },
      {
        path: "product-category-pnl/audit",
        element: routeElement(<ProductCategoryAdjustmentAuditPage />),
      },
    ],
  },
];
