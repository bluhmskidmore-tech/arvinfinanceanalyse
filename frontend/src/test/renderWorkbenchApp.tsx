import { render, type RenderResult } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryRouter,
  RouterProvider,
  type RouteObject,
} from "react-router-dom";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
import { workbenchRoutes } from "../router/routes";

export type RenderWorkbenchAppOptions = {
  routes?: RouteObject[];
  client?: ApiClient;
};

export function createWorkbenchMemoryRouter(
  initialEntries: string[],
  routes: RouteObject[] = workbenchRoutes,
): ReturnType<typeof createMemoryRouter> {
  return createMemoryRouter(routes, {
    initialEntries,
    future: routerFuture,
  });
}

export function renderWorkbenchApp(
  initialEntries: string[],
  options?: RenderWorkbenchAppOptions,
): RenderResult {
  const routes = options?.routes ?? workbenchRoutes;
  const router = createWorkbenchMemoryRouter(initialEntries, routes);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });
  const client = options?.client ?? createApiClient({ mode: "mock" });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <RouterProvider router={router} future={routerFuture} />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}
