import { lazy } from "react";
import { useLocation } from "react-router-dom";

import type { AgentPageContext } from "../api/contracts";
import { isAgentFrontendEnabled } from "../app/navigation";
import { WorkbenchNotFoundPage } from "./WorkbenchRouteStatusPages";

const AgentWorkbenchPage = lazy(() => import("../features/agent/AgentWorkbenchPage"));

const MAX_ROUTED_PAGE_CONTEXT_CHARS = 16_000;
const MAX_ROUTED_SELECTED_ROWS = 20;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readAgentPageContextFromRouteState(state: unknown): AgentPageContext | undefined {
  if (!isRecord(state) || !isRecord(state.agentPageContext)) {
    return undefined;
  }
  const candidate = state.agentPageContext;
  const pageId = typeof candidate.page_id === "string" ? candidate.page_id.trim() : "";
  if (!pageId || pageId.length > 128 || !isRecord(candidate.current_filters)) {
    return undefined;
  }
  if (
    !Array.isArray(candidate.selected_rows) ||
    candidate.selected_rows.length > MAX_ROUTED_SELECTED_ROWS ||
    candidate.selected_rows.some((row) => !isRecord(row))
  ) {
    return undefined;
  }
  if (
    candidate.context_note !== undefined &&
    candidate.context_note !== null &&
    (typeof candidate.context_note !== "string" || candidate.context_note.length > 1000)
  ) {
    return undefined;
  }

  const pageContext: AgentPageContext = {
    page_id: pageId,
    current_filters: candidate.current_filters,
    selected_rows: candidate.selected_rows as Array<Record<string, unknown>>,
    context_note: candidate.context_note as string | null | undefined,
  };
  try {
    return JSON.stringify(pageContext).length <= MAX_ROUTED_PAGE_CONTEXT_CHARS
      ? pageContext
      : undefined;
  } catch {
    return undefined;
  }
}

export function AgentWorkbenchRoute() {
  const location = useLocation();
  const pageContext = readAgentPageContextFromRouteState(location.state);
  return isAgentFrontendEnabled() ? (
    <AgentWorkbenchPage pageContext={pageContext} />
  ) : (
    <WorkbenchNotFoundPage />
  );
}
