import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import type { RouteObject } from "react-router-dom";

import { WorkbenchShell } from "../layouts/WorkbenchShell";
import {
  workbenchNavigation,
  type WorkbenchSection,
} from "../mocks/navigation";

const DashboardPage = lazy(
  () => import("../features/workbench/pages/DashboardPage"),
);
const WorkbenchPlaceholderPage = lazy(
  () => import("../features/workbench/pages/WorkbenchPlaceholderPage"),
);

function routeElement(element: ReactNode) {
  return (
    <Suspense fallback={<div style={{ padding: 24, color: "#5c6b82" }}>页面载入中...</div>}>
      {element}
    </Suspense>
  );
}

export const workbenchSections: WorkbenchSection[] = workbenchNavigation;

const childRoutes: RouteObject[] = workbenchSections.map((section) => {
  if (section.path === "/") {
    return {
      index: true,
      element: routeElement(<DashboardPage />),
    };
  }

  return {
    path: section.path.slice(1),
    element: routeElement(<WorkbenchPlaceholderPage />),
  };
});

export const workbenchRoutes: RouteObject[] = [
  {
    path: "/",
    element: <WorkbenchShell />,
    children: childRoutes,
  },
];
