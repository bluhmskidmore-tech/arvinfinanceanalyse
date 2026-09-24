import { lazy } from "react";

import { isAgentFrontendEnabled } from "../app/navigation";
import { WorkbenchNotFoundPage } from "./WorkbenchRouteStatusPages";

const AgentLabPage = lazy(() => import("../features/agent-lab/AgentLabPage"));

export function AgentLabRoute() {
  return isAgentFrontendEnabled() ? <AgentLabPage /> : <WorkbenchNotFoundPage />;
}
