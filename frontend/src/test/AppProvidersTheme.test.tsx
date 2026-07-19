import { act, fireEvent, render, screen } from "@testing-library/react";
import { theme } from "antd";
import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import ThemedRouteBoundary from "../app/ThemedRouteBoundary";
import { AppProviders } from "../app/providers";
import { workbenchTheme } from "../theme/theme";

function ThemeTokenProbe() {
  const { token } = theme.useToken();
  const [count, setCount] = useState(0);

  return (
    <>
      <span data-testid="route-color-primary">{token.colorPrimary}</span>
      <button type="button" onClick={() => setCount((value) => value + 1)}>
        count:{count}
      </button>
    </>
  );
}

describe("AppProviders theme boundary", () => {
  it("keeps descendants mounted while a legacy async-theme prop settles", async () => {
    const lifecycle: string[] = [];
    const LegacyCompatibleAppProviders = AppProviders as ComponentType<{
      children: ReactNode;
      loadAntdTheme?: boolean;
    }>;

    function MountProbe() {
      useEffect(() => {
        lifecycle.push("mount");
        return () => {
          lifecycle.push("cleanup");
        };
      }, []);
      return <span>mounted</span>;
    }

    render(
      <LegacyCompatibleAppProviders loadAntdTheme>
        <MountProbe />
      </LegacyCompatibleAppProviders>,
    );
    await act(async () => {
      await import("antd");
      await Promise.resolve();
    });

    expect(lifecycle).toEqual(["mount"]);
  });

  it("themes a workbench route before mount without resetting child state", () => {
    const tree = (
      <AppProviders>
        <ThemedRouteBoundary>
          <ThemeTokenProbe />
        </ThemedRouteBoundary>
      </AppProviders>
    );
    const { rerender } = render(tree);

    expect(screen.getByTestId("route-color-primary")).toHaveTextContent(
      String(workbenchTheme.token?.colorPrimary),
    );
    fireEvent.click(screen.getByRole("button", { name: "count:0" }));
    rerender(tree);
    expect(screen.getByRole("button", { name: "count:1" })).toBeInTheDocument();
  });
});
