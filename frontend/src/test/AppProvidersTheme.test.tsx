import { render, screen } from "@testing-library/react";
import { theme } from "antd";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { workbenchTheme } from "../theme/theme";

function ThemeTokenProbe() {
  const { token } = theme.useToken();

  return <span data-testid="root-color-primary">{token.colorPrimary}</span>;
}

describe("AppProviders theme boundary", () => {
  it("exposes the workbench AntD theme from the application root", () => {
    render(
      <AppProviders>
        <ThemeTokenProbe />
      </AppProviders>,
    );

    expect(screen.getByTestId("root-color-primary")).toHaveTextContent(
      String(workbenchTheme.token?.colorPrimary),
    );
  });
});
