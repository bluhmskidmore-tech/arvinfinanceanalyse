import { useApiClient } from "../api/clientContext";

/**
 * Fixed banner shown when the frontend is running in mock mode.
 * Prevents accidental use of simulated data for business decisions.
 * Renders nothing when mode === "real".
 */
type DataModeRibbonProps = {
  variant?: "default" | "cockpit";
};

export function DataModeRibbon({ variant = "default" }: DataModeRibbonProps) {
  const client = useApiClient();
  if (client.mode !== "mock") return null;

  return (
    <div
      id="data-mode-ribbon"
      className={`moss-data-mode-ribbon${
        variant === "cockpit" ? " moss-data-mode-ribbon--cockpit" : ""
      }`}
      data-variant={variant}
    >
      ⚠️ MOCK 模式 — 所有数据为前端模拟，不可用于业务决策
    </div>
  );
}
