import { theme } from "antd";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ThemedRouteBoundary from "../app/ThemedRouteBoundary";
import { workbenchTheme } from "../theme/theme";

function ThemeProbe() {
  const { token } = theme.useToken();

  return (
    <>
      <span data-testid="route-color-primary">{token.colorPrimary}</span>
      <span data-testid="route-bg-container">{token.colorBgContainer}</span>
    </>
  );
}

describe("ThemedRouteBoundary", () => {
  it("renders children inside a stable dark route theme owner", () => {
    const resolvedRouteTokens = theme.getDesignToken(workbenchTheme);
    const { container } = render(
      <ThemedRouteBoundary>
        <div data-testid="boundary-child">child content</div>
        <ThemeProbe />
      </ThemedRouteBoundary>,
    );

    expect(screen.getByTestId("boundary-child")).toBeInTheDocument();
    expect(screen.getByTestId("route-color-primary")).toHaveTextContent(
      resolvedRouteTokens.colorPrimary,
    );
    expect(screen.getByTestId("route-bg-container")).toHaveTextContent(
      resolvedRouteTokens.colorBgContainer,
    );

    const themeOwner = container.querySelector('[data-moss-theme="dark"].theme-dh-api');
    expect(themeOwner).not.toBeNull();
    expect(themeOwner).toHaveAttribute("data-moss-theme-scope", "route");
  });
});
