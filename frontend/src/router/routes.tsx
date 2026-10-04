import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { Navigate, type RouteObject } from "react-router-dom";

import { WorkbenchShell } from "../layouts/WorkbenchShell";
import {
  primaryWorkbenchNavigation,
  workbenchNavigation,
  type WorkbenchSection,
} from "../app/navigation";
import { AgentLabRoute } from "./AgentLabRoute";
import { AgentWorkbenchRoute } from "./AgentWorkbenchRoute";
import { PublicationShowcaseRoute } from "./PublicationShowcaseRoute";
import { WorkbenchRouteFallback } from "./WorkbenchRouteFallback";
import { WorkbenchNotFoundPage, WorkbenchRouteErrorBoundary } from "./WorkbenchRouteStatusPages";
import { SystemReadGenerationBoundary } from "./SystemReadGenerationBoundary";
import { lazyWorkbenchPage } from "./workbenchRouteModules";
import { WorkbenchRouteModulePreload } from "./WorkbenchRouteModulePreload";

const ThemedRouteBoundary = lazy(() => import("../app/ThemedRouteBoundary"));
const DashboardHomePage = lazyWorkbenchPage(
  () => import("../features/workbench/dashboard-home/DashboardHomePage"),
);
const ModuleWorkbenchHomePage = lazyWorkbenchPage(
  () => import("../features/workbench/module-home/ModuleWorkbenchHomePage"),
);
const RiskOverviewPage = lazyWorkbenchPage(
  () => import("../features/workbench/module-home/RiskOverviewPage"),
);
const PortfolioHomePage = lazyWorkbenchPage(
  () => import("../features/workbench/module-home/PortfolioHomePage"),
);
const MarketHomePage = lazyWorkbenchPage(
  () => import("../features/workbench/module-home/MarketHomePage"),
);
const OperationsAnalysisPage = lazyWorkbenchPage(
  () => import("../features/workbench/pages/OperationsAnalysisPage"),
);
const MarketFinanceWorkbenchPage = lazyWorkbenchPage(
  () => import("../features/market-finance/pages/MarketFinanceWorkbenchPage"),
);
const PnlPage = lazyWorkbenchPage(() => import("../features/pnl/PnlPage"));
const PnlByBusinessPage = lazyWorkbenchPage(() => import("../features/pnl/PnlByBusinessPage"));
const PnlByBusinessInsightsPage = lazyWorkbenchPage(
  () => import("../features/pnl-business-insights/PnlByBusinessInsightsPage"),
);
const PnlBridgePage = lazyWorkbenchPage(() => import("../features/pnl/PnlBridgePage"));
const PnlAttributionPage = lazyWorkbenchPage(
  () => import("../features/pnl-attribution/pages/PnlAttributionPage"),
);
const BalanceAnalysisPage = lazyWorkbenchPage(
  () => import("../features/balance-analysis/pages/BalanceAnalysisPage"),
);
const BalanceMovementAnalysisPage = lazyWorkbenchPage(
  () => import("../features/balance-movement-analysis/pages/BalanceMovementAnalysisPage"),
);
const LiabilityAnalyticsPage = lazyWorkbenchPage(
  () => import("../features/liability-analytics/pages/LiabilityAnalyticsPage"),
);
const ProductCategoryAdjustmentAuditPage = lazyWorkbenchPage(
  () => import("../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage"),
);
const ProductCategoryPnlPage = lazyWorkbenchPage(
  () => import("../features/product-category-pnl/pages/ProductCategoryPnlPage"),
);
const WorkbenchPlaceholderPage = lazy(
  () => import("../features/workbench/pages/WorkbenchPlaceholderPage"),
);
const RiskTensorPage = lazyWorkbenchPage(
  () => import("../features/risk-tensor/RiskTensorPage"),
);
const ConcentrationMonitorPage = lazyWorkbenchPage(
  () => import("../features/concentration-monitor/ConcentrationMonitorPage"),
);
const CashflowProjectionPage = lazyWorkbenchPage(
  () => import("../features/cashflow-projection/pages/CashflowProjectionPage"),
);
const BondAnalyticsView = lazyWorkbenchPage(
  () => import("../features/bond-analytics/components/BondAnalyticsView"),
);
const BondTradingDeskPage = lazyWorkbenchPage(
  () => import("../features/bond-trading-desk/pages/BondTradingDeskPage"),
);
const BondDashboardPage = lazyWorkbenchPage(
  () => import("../features/bond-dashboard/pages/BondDashboardPage"),
);
const PositionsPage = lazyWorkbenchPage(() => import("../features/positions/pages/PositionsPage"));
const AverageBalancePage = lazyWorkbenchPage(
  () => import("../features/average-balance/pages/AverageBalancePage"),
);
const LedgerPnlPage = lazyWorkbenchPage(
  () => import("../features/ledger-pnl/pages/LedgerPnlPage"),
);
const LedgerDashboardPage = lazyWorkbenchPage(
  () => import("../features/ledger-dashboard/pages/LedgerDashboardPage"),
);
const KpiPerformancePage = lazyWorkbenchPage(
  () => import("../features/kpi-performance/pages/KpiPerformancePage"),
);
const TeamPerformancePage = lazyWorkbenchPage(
  () => import("../features/team-performance/TeamPerformancePage"),
);
const PlatformConfigPage = lazyWorkbenchPage(
  () => import("../features/platform-config/PlatformConfigPage"),
);
const CrossAssetPage = lazyWorkbenchPage(() => import("../features/cross-asset/pages/CrossAssetPage"));
const MarketDataPage = lazyWorkbenchPage(
  () => import("../features/market-data/pages/MarketDataPage"),
);
const MacroToolkitPage = lazyWorkbenchPage(
  () => import("../features/macro-toolkit/pages/MacroToolkitPage"),
);
const MacroObservationPage = lazyWorkbenchPage(
  () => import("../features/macro-observation/pages/MacroObservationPage"),
);
const CubeQueryPage = lazyWorkbenchPage(() => import("../features/cube-query/pages/CubeQueryPage"));
const StockAnalysisPage = lazyWorkbenchPage(
  () => import("../features/stock-analysis/pages/StockAnalysisPage"),
);
const StockPortfolioConstructionPage = lazyWorkbenchPage(
  () => import("../features/stock-analysis/pages/StockPortfolioConstructionPage"),
);
const DecisionItemsPage = lazyWorkbenchPage(
  () => import("../features/decision-items/pages/DecisionItemsPage"),
);
const NewsEventsPage = lazyWorkbenchPage(() => import("../features/news-events/NewsEventsPage"));

function routeElement(element: ReactNode) {
  return (
    <Suspense fallback={<WorkbenchRouteFallback />}>
      <WorkbenchRouteModulePreload>{element}</WorkbenchRouteModulePreload>
    </Suspense>
  );
}

function themedRouteElement(element: ReactNode) {
  return routeElement(<ThemedRouteBoundary>{element}</ThemedRouteBoundary>);
}

function systemReadRouteElement(element: ReactNode, themed = true) {
  const scoped = <SystemReadGenerationBoundary>{element}</SystemReadGenerationBoundary>;
  return themed ? themedRouteElement(scoped) : routeElement(scoped);
}

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
        element: systemReadRouteElement(<DashboardHomePage />, false),
      };
    }

    if (section.readiness !== "live" && section.path !== "/agent") {
      return placeholderRoute(section);
    }

    if (section.path === "/operations-analysis") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<OperationsAnalysisPage />),
      };
    }

    if (section.path === "/market-finance") {
      return {
        path: section.path.slice(1),
        element: themedRouteElement(<MarketFinanceWorkbenchPage />),
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
        element: systemReadRouteElement(<BalanceAnalysisPage />),
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
        element: systemReadRouteElement(<PnlByBusinessInsightsPage />),
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
        element: systemReadRouteElement(<RiskTensorPage />),
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
        element: systemReadRouteElement(<BondAnalyticsView />),
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
        element: themedRouteElement(<MacroObservationPage />),
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
        element: systemReadRouteElement(<CubeQueryPage />),
      };
    }

    if (section.path === "/stock-analysis") {
      return {
        path: section.path.slice(1),
        element: systemReadRouteElement(<StockAnalysisPage />),
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
        element: themedRouteElement(<AgentWorkbenchRoute />),
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
    path: "/publication-showcase",
    element: themedRouteElement(<PublicationShowcaseRoute />),
    errorElement: routeElement(<WorkbenchRouteErrorBoundary />),
  },
  {
    path: "/",
    element: <WorkbenchShell />,
    errorElement: routeElement(<WorkbenchRouteErrorBoundary />),
    children: [
      {
        /*
         * 子路由级错误边界（pathless layout）：单页渲染崩溃或懒加载 chunk 失败时，
         * 错误页只替换 WorkbenchShell 的 Outlet 内容区，导航壳层保持可用；
         * 根级 errorElement 仅兜底壳层自身故障。
         *
         * 错误页必须仍套在 ThemedRouteBoundary 里：壳层的深色是
         * `.workbench-shell-grid:has(.themed-route-boundary.theme-dh-api)` 驱动的，
         * 裸渲染会让终端条、错误卡一起翻回 IB 浅色（2026-09-02 走查 /news-events 复现）。
         */
        errorElement: themedRouteElement(<WorkbenchRouteErrorBoundary />),
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
            element: <Navigate to="/pnl" replace />,
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
            element: <Navigate to="/cross-asset" replace />,
          },
          {
            path: "assets",
            element: <Navigate to="/bond-dashboard" replace />,
          },
          ...buildWorkbenchChildRoutes(),
          {
            path: "stock-analysis/portfolio",
            element: themedRouteElement(<StockPortfolioConstructionPage />),
          },
          {
            path: "stock-analysis/risk",
            element: themedRouteElement(<StockPortfolioConstructionPage />),
          },
          {
            path: "agent-lab",
            element: themedRouteElement(<AgentLabRoute />),
          },
          {
            path: "dashboard",
            element: systemReadRouteElement(<DashboardHomePage />, false),
          },
          {
            path: "政策与资金面",
            element: <Navigate to="/" replace />,
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
    ],
  },
];
