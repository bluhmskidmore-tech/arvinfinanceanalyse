import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("DecisionItemsRoute", () => {
  it("renders the decision-items workbench route", async () => {
    renderWorkbenchApp(["/decision-items"], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId("decision-items-page")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "决策事项" })).toBeInTheDocument();
  });
});
