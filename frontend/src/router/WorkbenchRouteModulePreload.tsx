import type { ReactNode } from "react";

import { preloadWorkbenchRouteElement } from "./workbenchRouteModules";

export function WorkbenchRouteModulePreload({ children }: { children: ReactNode }) {
  preloadWorkbenchRouteElement(children);
  return children;
}
