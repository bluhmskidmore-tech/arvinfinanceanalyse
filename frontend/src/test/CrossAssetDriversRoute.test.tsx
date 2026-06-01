import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("CrossAssetDriversRoute", () => {
  it("renders the cross-asset-drivers compatibility route", async () => {
    renderWorkbenchApp(["/cross-asset-drivers"], { client: createApiClient({ mode: "mock" }) });

    expect(await screen.findByTestId("cross-asset-drivers-page")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-research-views")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-transmission-axes")).toBeInTheDocument();
    expect(screen.getByTestId("cross-asset-ncd-proxy")).toBeInTheDocument();
  });
});
