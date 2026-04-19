import { render, type RenderResult } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryRouter,
  RouterProvider,
  type RouteObject,
} from "react-router-dom";

import { AppProviders } from "../app/providers";
import { ApiClientProvider, type ApiClient } from "../api/client";
import { routerFuture } from "../router/routerFuture";
import { workbenchRoutes } from "../router/routes";

export type RenderWorkbenchAppOptions = {
  routes?: RouteObject[];
  client?: ApiClient;
};

let requestCompatInstalled = false;

function isAbortSignalMismatch(error: unknown): error is TypeError {
  return (
    error instanceof TypeError &&
    error.message.includes('Expected signal ("AbortSignal {}") to be an instance of AbortSignal')
  );
}

function ensureRouterRequestCompat() {
  if (requestCompatInstalled || typeof Request === "undefined" || typeof AbortController === "undefined") {
    return;
  }

  try {
    void new Request("http://localhost/", { signal: new AbortController().signal });
    requestCompatInstalled = true;
    return;
  } catch (error) {
    if (!isAbortSignalMismatch(error)) {
      throw error;
    }
  }

  const NativeRequest = Request;

  function CompatibleRequest(input: RequestInfo | URL, init?: RequestInit) {
    try {
      return new NativeRequest(input, init);
    } catch (error) {
      if (!init?.signal || !isAbortSignalMismatch(error)) {
        throw error;
      }

      const { signal: _signal, ...requestInit } = init;
      return new NativeRequest(input, requestInit);
    }
  }

  CompatibleRequest.prototype = NativeRequest.prototype;
  globalThis.Request = CompatibleRequest as unknown as typeof Request;
  requestCompatInstalled = true;
}

export function createWorkbenchMemoryRouter(
  initialEntries: string[],
  routes: RouteObject[] = workbenchRoutes,
): ReturnType<typeof createMemoryRouter> {
  ensureRouterRequestCompat();
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

  if (options?.client) {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
      },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={options.client}>
          <RouterProvider router={router} future={routerFuture} />
        </ApiClientProvider>
      </QueryClientProvider>,
    );
  }

  return render(
    <AppProviders>
      <RouterProvider router={router} future={routerFuture} />
    </AppProviders>,
  );
}
