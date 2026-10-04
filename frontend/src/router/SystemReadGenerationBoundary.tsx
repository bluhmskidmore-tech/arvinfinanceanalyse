import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";

import { ApiClientProvider, useApiClient } from "../api/clientContext";
import {
  createGenerationScopedApiClient,
  getSystemReadPublication,
  type SystemReadPublication,
} from "../api/systemReadGeneration";
import { WorkbenchRouteFallback } from "./WorkbenchRouteFallback";
import {
  SystemReadInteractionContext,
  type SystemReadInteraction,
} from "./systemReadInteractionContext";

type BoundaryState =
  | { status: "loading" }
  | { status: "disabled"; publication: SystemReadPublication }
  | {
      status: "ready";
      publication: SystemReadPublication & { enabled: true; generation: string };
      client: ReturnType<typeof createGenerationScopedApiClient>;
      queryClient: QueryClient;
    }
  | { status: "error"; error: Error };

// Retain only the latest confirmed generation per app/client, not a history of
// generations. A new page interaction must complete its handshake before reuse.
const confirmedReadScopes = new WeakMap<QueryClient, WeakMap<
  ReturnType<typeof useApiClient>, Extract<BoundaryState, { status: "ready" }>
>>();

export function SystemReadGenerationBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  // The home page controls its date from the URL and uses date-scoped query keys.
  // Other pages still initialize local date filters when an interaction opens.
  const interactionSearch = new URLSearchParams(location.search);
  if (location.pathname === "/" || location.pathname === "/dashboard") {
    interactionSearch.delete("report_date");
  }
  const interactionKey = `${location.pathname}?${interactionSearch.toString()}`;
  return <SystemReadInteractionBoundary key={interactionKey}>{children}</SystemReadInteractionBoundary>;
}

function SystemReadInteractionBoundary({ children }: { children: ReactNode }) {
  const sourceClient = useApiClient();
  const parentQueryClient = useQueryClient();
  const [refreshSequence, setRefreshSequence] = useState(0);
  const [state, setState] = useState<BoundaryState>(() =>
    sourceClient.mode === "mock"
      ? {
          status: "disabled",
          publication: { enabled: false, generation: null, coverage_dates: {} },
        }
      : { status: "loading" },
  );

  const refresh = useCallback(() => {
    setState({ status: "loading" });
    setRefreshSequence((current) => current + 1);
  }, []);

  useEffect(() => {
    if (sourceClient.mode === "mock") {
      setState({
        status: "disabled",
        publication: { enabled: false, generation: null, coverage_dates: {} },
      });
      return;
    }

    const controller = new AbortController();
    setState({ status: "loading" });
    void getSystemReadPublication(sourceClient, controller.signal)
      .then((publication) => {
        if (controller.signal.aborted) return;
        if (!publication.enabled) {
          confirmedReadScopes.get(parentQueryClient)?.delete(sourceClient);
          setState({ status: "disabled", publication });
          return;
        }
        const generation = publication.generation;
        if (!generation) {
          throw new Error("System read publication did not provide a generation.");
        }
        let clientScopes = confirmedReadScopes.get(parentQueryClient);
        if (!clientScopes) {
          clientScopes = new WeakMap();
          confirmedReadScopes.set(parentQueryClient, clientScopes);
        }
        const previous = clientScopes.get(sourceClient);
        if (refreshSequence === 0 && previous?.publication.generation === generation) {
          setState({ ...previous, publication: { ...publication, enabled: true, generation } });
          return;
        }
        const next: Extract<BoundaryState, { status: "ready" }> = {
          status: "ready",
          publication: { ...publication, enabled: true, generation },
          client: createGenerationScopedApiClient(sourceClient, generation),
          queryClient: new QueryClient({
            defaultOptions: parentQueryClient.getDefaultOptions(),
          }),
        };
        clientScopes.set(sourceClient, next);
        setState(next);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          error: error instanceof Error ? error : new Error(String(error)),
        });
      });

    return () => controller.abort();
  }, [parentQueryClient, refreshSequence, sourceClient]);

  const interaction = useMemo<SystemReadInteraction>(() => ({
    generation: state.status === "ready" ? state.publication.generation : null,
    coverageDates:
      state.status === "ready" || state.status === "disabled"
        ? state.publication.coverage_dates
        : {},
    refresh,
  }), [refresh, state]);

  if (state.status === "loading") {
    return <WorkbenchRouteFallback />;
  }
  if (state.status === "error") {
    throw state.error;
  }

  const content = (
    <SystemReadInteractionContext.Provider value={interaction}>
      {children}
    </SystemReadInteractionContext.Provider>
  );

  if (state.status === "disabled") {
    return content;
  }

  return (
    <ApiClientProvider client={state.client}>
      <QueryClientProvider client={state.queryClient}>
        {content}
      </QueryClientProvider>
    </ApiClientProvider>
  );
}
