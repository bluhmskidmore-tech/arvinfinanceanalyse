import type { RouteObject } from "react-router-dom";

import { DashboardPage } from "../features/workbench/pages/DashboardPage";
import { WorkbenchPlaceholderPage } from "../features/workbench/pages/WorkbenchPlaceholderPage";
import { WorkbenchShell } from "../layouts/WorkbenchShell";
import {
  workbenchNavigation,
  type WorkbenchSection,
} from "../mocks/navigation";

export const workbenchSections: WorkbenchSection[] = workbenchNavigation;

const childRoutes: RouteObject[] = workbenchSections.map((section) => {
  if (section.path === "/") {
    return {
      index: true,
      element: <DashboardPage />,
    };
  }

  return {
    path: section.path.slice(1),
    element: <WorkbenchPlaceholderPage />,
  };
});

export const workbenchRoutes: RouteObject[] = [
  {
    path: "/",
    element: <WorkbenchShell />,
    children: childRoutes,
  },
];
