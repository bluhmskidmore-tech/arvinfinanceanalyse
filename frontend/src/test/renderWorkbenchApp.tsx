import { render, type RenderResult } from "@testing-library/react";
import {
  createMemoryRouter,
  RouterProvider,
  type RouteObject,
} from "react-router-dom";

import { AppProviders } from "../app/providers";
import { routerFuture } from "../router/routerFuture";
import { workbenchRoutes } from "../router/routes";

export type RenderWorkbenchAppOptions = {
  routes?: RouteObject[];
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

  return render(
    <AppProviders>
      <RouterProvider router={router} future={routerFuture} />
    </AppProviders>,
  );
}
