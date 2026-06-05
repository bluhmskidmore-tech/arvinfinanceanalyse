import { useMemo } from "react";

import type { AgentPageContext } from "../../api/contracts";
import { EmbeddedAgentCopilot } from "./AgentWorkbenchPage";

import "./AgentPanel.css";

export type AgentPanelProps = {
  pageId: string;
  reportDate?: string | null;
  currentFilters?: Record<string, unknown>;
  defaultFilters?: Record<string, unknown>;
  selectedRows?: Array<Record<string, unknown>>;
  contextNote?: string | null;
  defaultQuestion?: string;
};

export function AgentPanel({
  pageId,
  reportDate = null,
  currentFilters = {},
  defaultFilters = {},
  selectedRows,
  contextNote = null,
  defaultQuestion = "",
}: AgentPanelProps) {
  const pageContextPayload = useMemo<AgentPageContext>(
    () => ({
      page_id: pageId,
      current_filters:
        reportDate != null
          ? { ...defaultFilters, ...currentFilters, report_date: reportDate }
          : { ...defaultFilters, ...currentFilters },
      selected_rows: selectedRows ?? [],
      context_note: contextNote ?? null,
    }),
    [pageId, reportDate, currentFilters, defaultFilters, selectedRows, contextNote],
  );

  return (
    <EmbeddedAgentCopilot
      pageContext={pageContextPayload}
      variant="embedded"
      showHeader
      readOnly
      defaultQuestion={defaultQuestion}
    />
  );
}
