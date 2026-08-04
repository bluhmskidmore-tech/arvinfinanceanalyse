import { lazy } from "react";

import { isAgentFrontendEnabled } from "../mocks/navigation";
import { WorkbenchNotFoundPage } from "./WorkbenchRouteStatusPages";

const AgentWorkbenchPage = lazy(() => import("../features/agent/AgentWorkbenchPage"));

export function AgentWorkbenchRoute() {
  return isAgentFrontendEnabled() ? <AgentWorkbenchPage /> : <WorkbenchNotFoundPage />;
}
