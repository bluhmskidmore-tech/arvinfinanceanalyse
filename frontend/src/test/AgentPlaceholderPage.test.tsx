import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("/agent route when its frontend gate is closed", () => {
  it("renders the existing 404 status without requesting a placeholder snapshot", async () => {
    const getPlaceholderSnapshot = vi.fn();
    const client: ApiClient = {
      ...createApiClient({ mode: "mock" }),
      getPlaceholderSnapshot,
    };

    renderWorkbenchApp(["/agent"], { client });

    expect(await screen.findByTestId("workbench-not-found-page")).toHaveTextContent("/agent");
    expect(getPlaceholderSnapshot).not.toHaveBeenCalled();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });
});
