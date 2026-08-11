/**
 * Shared API contract surface, re-exported from domain-scoped files under ./contracts/.
 * This file is a pure barrel: it does not declare any types itself. See ./contracts/*.ts
 * for the actual definitions, grouped by business domain.
 */
export * from "./contracts/core";
export * from "./contracts/homeExecutive";
export * from "./contracts/bondAnalytics";
export * from "./contracts/riskTensor";
export * from "./contracts/sourcePreview";
export * from "./contracts/marketMacro";
export * from "./contracts/researchCalendar";
export * from "./contracts/pnl";
export * from "./contracts/balanceLedger";
export * from "./contracts/agent";
export * from "./contracts/positions";
export * from "./contracts/bondDashboard";
export * from "./contracts/cubeAdb";
