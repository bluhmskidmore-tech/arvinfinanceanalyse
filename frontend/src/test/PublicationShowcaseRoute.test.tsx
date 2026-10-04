import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PublicationShowcaseRoute } from "../router/PublicationShowcaseRoute";
import { isPublicationShowcaseEnabled } from "../router/publicationShowcaseGate";

vi.mock("../router/WorkbenchRouteStatusPages", () => ({
  WorkbenchNotFoundPage: () => <section data-testid="workbench-not-found-page" />,
}));

vi.mock("../features/publication-showcase/PublicationShowcasePage", () => ({
  default: () => <section data-testid="publication-showcase-page" />,
}));

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("PublicationShowcaseRoute", () => {
  it("enables the route only in dev + mock mode", () => {
    expect(
      isPublicationShowcaseEnabled({
        DEV: true,
        VITE_DATA_SOURCE: "mock",
      }),
    ).toBe(true);

    expect(
      isPublicationShowcaseEnabled({
        DEV: true,
        VITE_DATA_SOURCE: "real",
      }),
    ).toBe(false);

    expect(
      isPublicationShowcaseEnabled({
        DEV: false,
        VITE_DATA_SOURCE: "mock",
      }),
    ).toBe(false);
  });

  it("renders the showcase page when enabled", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_DATA_SOURCE", "mock");

    render(<PublicationShowcaseRoute />);

    expect(await screen.findByTestId("publication-showcase-page")).toBeInTheDocument();
  });

  it("renders not found when disabled", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("PROD", false);
    vi.stubEnv("VITE_DATA_SOURCE", "real");

    render(<PublicationShowcaseRoute />);

    expect(await screen.findByTestId("workbench-not-found-page")).toBeInTheDocument();
  });
});
