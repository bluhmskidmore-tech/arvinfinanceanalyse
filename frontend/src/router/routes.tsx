import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import type { RouteObject } from "react-router-dom";

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
const ProductCategoryPnlPage = lazy(
  () => import("../features/product-category-pnl/pages/ProductCategoryPnlPage"),
);
const ProductCategoryAdjustmentAuditPage = lazy(
  () => import("../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage"),
);
const WorkbenchPlaceholderPage = lazy(
  () => import("../features/workbench/pages/WorkbenchPlaceholderPage"),
);
const AgentPlaceholderPage = lazy(
  () => import("../features/agent/pages/AgentPlaceholderPage"),
);
const BondAnalyticsView = lazy(
  () => import("../features/bond-analytics/components/BondAnalyticsView"),
);

function routeElement(element: ReactNode) {
  return (
    <Suspense fallback={<WorkbenchRouteFallback />}>
      {element}
    </Suspense>
  );
}

function buildWorkbenchChildRoutes(): RouteObject[] {
  return workbenchNavigation.map((section) => {
    if (section.path === "/") {
      return {
        index: true,
        element: routeElement(<DashboardPage />),
      };
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
        element: routeElement(<AgentPlaceholderPage />),
      };
    }

    if (section.path === "/news-events") {
      return {
        path: section.path.slice(1),
        element: routeElement(<AgentPlaceholderPage />),
      };
    }

    if (section.path === "/bond-analysis") {
      return {
        path: section.path.slice(1),
        element: routeElement(<BondAnalyticsView />),
      };
    }

    if (section.path === "/product-category-pnl") {
      return {
        path: section.path.slice(1),
        element: routeElement(<ProductCategoryPnlPage />),
      };
    }

    if (section.path === "/market-data") {
      return {
        path: section.path.slice(1),
        element: routeElement(<MarketDataPage />),
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
      ...buildWorkbenchChildRoutes(),
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
