import type { DataSourceMode } from "./client";

/** Resolve both public client entry points through the same production boundary. */
export function resolveDataSourceMode(override?: DataSourceMode): DataSourceMode {
  const raw = import.meta.env.VITE_DATA_SOURCE;
  const envValue = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  const isProd = import.meta.env.PROD === true;

  if (override !== undefined) {
    if (override !== "real" && override !== "mock") {
      throw new Error(`Invalid API data source mode: ${String(override)}`);
    }
    if (override === "mock" && isProd) {
      throw new Error("API data source mode 'mock' is not allowed in production.");
    }
    return override;
  }

  if (envValue === "real") return "real";
  if (envValue === "mock") {
    if (isProd) throw new Error("VITE_DATA_SOURCE='mock' is not allowed in production.");
    return "mock";
  }

  if (isProd) {
    throw new Error(
      "VITE_DATA_SOURCE must be explicitly set to 'real' in production build. " +
        "Refusing to silently fall back to mock.",
    );
  }

  console.warn("[client] VITE_DATA_SOURCE not set or invalid (raw=%o). Defaulting to real.", raw);
  return "real";
}
