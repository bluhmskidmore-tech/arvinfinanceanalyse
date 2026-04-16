import type { RouteObject } from "react-router-dom";

import { createApiClient, useApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

function ClientModeProbe() {
  const client = useApiClient();
  return <div data-testid="render-workbench-app-client-mode">{client.mode}</div>;
}

const probeRoutes: RouteObject[] = [
  {
    path: "/",
    element: <ClientModeProbe />,
  },
];

describe("renderWorkbenchApp", () => {
  it("defaults to a mock client when no client override is provided", async () => {
    const { findByTestId } = renderWorkbenchApp(["/"], { routes: probeRoutes });

    expect(await findByTestId("render-workbench-app-client-mode")).toHaveTextContent("mock");
  });

  it("preserves an explicit client override", async () => {
    const { findByTestId } = renderWorkbenchApp(["/"], {
      routes: probeRoutes,
      client: createApiClient({ mode: "real" }),
    });

    expect(await findByTestId("render-workbench-app-client-mode")).toHaveTextContent("real");
  });
});
