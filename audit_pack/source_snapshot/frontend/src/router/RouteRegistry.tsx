import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { routerFuture } from "./routerFuture";
import { workbenchRoutes } from "./routes";

const router = createBrowserRouter(workbenchRoutes, {
  future: routerFuture,
});

export function RouteRegistry() {
  return <RouterProvider router={router} future={routerFuture} />;
}
