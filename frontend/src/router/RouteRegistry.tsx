import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { workbenchRoutes } from "./routes";

const router = createBrowserRouter(workbenchRoutes);

export function RouteRegistry() {
  return <RouterProvider router={router} />;
}
