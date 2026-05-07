import { useApiClient } from "../api/client";

/**
 * Fixed banner shown when the frontend is running in mock mode.
 * Prevents accidental use of simulated data for business decisions.
 * Renders nothing when mode === "real".
 */
export function DataModeRibbon() {
  const client = useApiClient();
  if (client.mode !== "mock") return null;

  return (
    <div
      id="data-mode-ribbon"
      className="moss-data-mode-ribbon"
    >
      ⚠️ MOCK 模式 — 所有数据为前端模拟，不可用于业务决策
    </div>
  );
}
