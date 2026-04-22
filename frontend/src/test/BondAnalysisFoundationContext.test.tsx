import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { UserPreferences } from "../bond-analysis-foundation/data-structures/UserPreferences";
import {
  BondProvider,
  useBondWorkspace,
} from "../bond-analysis-foundation/react-components/context/BondContext";

function WorkspaceProbe() {
  const {
    preferences,
    selectedBondId,
    watchlist,
    addToWatchlist,
    removeFromWatchlist,
    selectBond,
    toggleColorMode,
  } = useBondWorkspace();

  return (
    <div>
      <p data-testid="color-mode">{preferences.colorMode}</p>
      <p data-testid="selected-bond">{selectedBondId ?? "none"}</p>
      <p data-testid="watchlist">{watchlist.join(",") || "empty"}</p>
      <button type="button" onClick={() => addToWatchlist("240210")}>
        add
      </button>
      <button type="button" onClick={() => removeFromWatchlist("240210")}>
        remove
      </button>
      <button type="button" onClick={() => selectBond("240210")}>
        select
      </button>
      <button type="button" onClick={() => toggleColorMode()}>
        toggle
      </button>
    </div>
  );
}

describe("BondProvider", () => {
  it("tracks preferences, selected bond, and watchlist changes", async () => {
    const user = userEvent.setup();
    const initialPreferences: UserPreferences = {
      colorMode: "dark",
      language: "zh-CN",
      refreshIntervalSeconds: 15,
      favoriteBondCodes: [],
      customMetrics: ["yieldToMaturity", "creditSpreadBp"],
      defaultPortfolioId: "PF-CORE",
      dashboardLayout: "trader",
      enableMotion: true,
    };

    render(
      <BondProvider initialPreferences={initialPreferences}>
        <WorkspaceProbe />
      </BondProvider>,
    );

    expect(screen.getByTestId("color-mode")).toHaveTextContent("dark");
    expect(screen.getByTestId("selected-bond")).toHaveTextContent("none");
    expect(screen.getByTestId("watchlist")).toHaveTextContent("empty");

    await user.click(screen.getByRole("button", { name: "add" }));
    await user.click(screen.getByRole("button", { name: "select" }));
    await user.click(screen.getByRole("button", { name: "toggle" }));

    expect(screen.getByTestId("watchlist")).toHaveTextContent("240210");
    expect(screen.getByTestId("selected-bond")).toHaveTextContent("240210");
    expect(screen.getByTestId("color-mode")).toHaveTextContent("light");

    await user.click(screen.getByRole("button", { name: "remove" }));

    expect(screen.getByTestId("watchlist")).toHaveTextContent("empty");
  });
});
