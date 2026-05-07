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
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 28,
        zIndex: 9999,
        background: "linear-gradient(90deg, #ff6b35, #f7c948)",
        color: "#1a1a1a",
        fontSize: 12,
        fontWeight: 600,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        letterSpacing: "0.05em",
        pointerEvents: "none",
      }}
    >
      ⚠️ MOCK 模式 — 所有数据为前端模拟，不可用于业务决策
    </div>
  );
}
