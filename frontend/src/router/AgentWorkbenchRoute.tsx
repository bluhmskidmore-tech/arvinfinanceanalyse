import { lazy } from "react";

import { isAgentFrontendEnabled } from "../app/navigation";
import { WorkbenchNotFoundPage } from "./WorkbenchRouteStatusPages";

const AgentWorkbenchPage = lazy(() => import("../features/agent/AgentWorkbenchPage"));

export function AgentWorkbenchRoute() {
  return isAgentFrontendEnabled() ? <AgentWorkbenchPage /> : <WorkbenchNotFoundPage />;
}
