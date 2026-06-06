import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { preloadWorkbenchRouteModules } from "./preloadWorkbenchRouteModules";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("DecisionItemsRoute", () => {
  beforeAll(async () => {
    await preloadWorkbenchRouteModules("decision-items");
  }, 20_000);

  it("renders the decision-items workbench route", async () => {
    renderWorkbenchApp(["/decision-items"], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId("decision-items-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "决策事项" })).toBeInTheDocument();
  });
});
