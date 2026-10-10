import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";
import { createRealAgentClient } from "./agentClient";
import { createRealBalanceAnalysisClient } from "./balanceAnalysisClient";
import { createRealBalanceMovementClient } from "./balanceMovementClient";
import {
  createRealBondAnalyticsClient,
  createRealBondDashboardClient,
} from "./bondAnalyticsClient";
import { bondDashboardLiveEndpoints } from "./bondDashboardWorkbenchEndpoints";
import { createRealCashflowClient } from "./cashflowClient";
import { createRealCubeClient } from "./cubeClient";
import { createRealExecutiveClient } from "./executiveClient";
import { createRealHealthClient } from "./healthClient";
import { createRealKpiClient } from "./kpiClient";
import { createRealLedgerClient } from "./ledgerClient";
import { createRealLiabilityAdbClient } from "./liabilityAdbClient";
import { createRealMacroToolkitClient } from "./macroToolkitClient";
import { createRealMarketDataClient } from "./marketDataClient";
import { createRealPnlAttributionClient } from "./pnlAttributionClient";
import { createRealPnlBusinessClient } from "./pnlClient";
import { createRealPnlCoreClient } from "./pnlCoreClient";
import { createRealPositionsClient } from "./positionsClient";
import { createRealProductCategoryClient } from "./productCategoryClient";
import { createRealQdbGlMonthlyAnalysisClient } from "./qdbGlMonthlyAnalysisClient";
import { createRealTeamPerformanceClient } from "./teamPerformanceClient";
import { dashboardWorkbenchLiveEndpoints } from "./workbenchDashboardApi";
import {
  requestActionJson,
  requestActionWithBody,
  requestBlob,
  requestJson,
  requestText,
} from "./transport";

// real 模式组合守卫（2026-09-28）。
//
// 根因：`createApiClient` 用 23 个 `...spread` 把各领域工厂合并成一个对象。同名方法不会
// 报错，而是被**后展开者静默覆盖**——顺序即语义，且没有任何检测。mock 路径有方法面完整性
// 断言（client.ts 的 `Demo ApiClient missing methods`），real 路径此前完全没有对应保护。
//
// 这里用「实际构造 23 个工厂 + 实际构造组合客户端」做行为断言，而不是断言源码字符串：
// 2026-09-28 实测 261 个方法名 0 冲突，故本守卫是**预防性**的——将来任何领域新增重名方法，
// 会在 CI 直接红，并报出争用的两个领域，而不是让某个方法悄悄消失。

const fetchImpl = vi.fn(async () => new Response("{}", { status: 200 })) as unknown as typeof fetch;
const baseUrl = "http://localhost:8000";

/** Domain factory bundles in the exact spread order used by `createApiClient`. */
function buildRealClientBundles(): Array<[domain: string, methods: Record<string, unknown>]> {
  return [
    ["healthClient", createRealHealthClient({ fetchImpl, baseUrl })],
    ["balanceMovementClient", createRealBalanceMovementClient({ fetchImpl, baseUrl })],
    ["ledgerClient", createRealLedgerClient({ fetchImpl, baseUrl })],
    ["marketDataClient", createRealMarketDataClient({ fetchImpl, baseUrl })],
    ["macroToolkitClient", createRealMacroToolkitClient({ fetchImpl, baseUrl })],
    ["kpiClient", createRealKpiClient({ fetchImpl, baseUrl })],
    ["teamPerformanceClient", createRealTeamPerformanceClient({ fetchImpl, baseUrl })],
    ["cubeClient", createRealCubeClient({ fetchImpl, baseUrl })],
    ["pnlClient", createRealPnlBusinessClient({ fetchImpl, baseUrl })],
    ["agentClient", createRealAgentClient({ fetchImpl, baseUrl })],
    ["executiveClient", createRealExecutiveClient({ fetchImpl, baseUrl, requestJson })],
    ["workbenchDashboardApi", dashboardWorkbenchLiveEndpoints({ fetchImpl, baseUrl, requestJson })],
    [
      "bondDashboardWorkbenchEndpoints",
      bondDashboardLiveEndpoints({ fetchImpl, baseUrl, requestJson }),
    ],
    [
      "bondAnalyticsClient",
      createRealBondAnalyticsClient({ fetchImpl, baseUrl, requestJson, requestActionJson }),
    ],
    ["bondDashboardClient", createRealBondDashboardClient({ fetchImpl, baseUrl, requestJson })],
    [
      "pnlCoreClient",
      createRealPnlCoreClient({ fetchImpl, baseUrl, requestJson, requestActionJson }),
    ],
    ["pnlAttributionClient", createRealPnlAttributionClient({ fetchImpl, baseUrl, requestJson })],
    ["positionsClient", createRealPositionsClient({ fetchImpl, baseUrl, requestJson })],
    ["cashflowClient", createRealCashflowClient({ fetchImpl, baseUrl, requestJson })],
    ["liabilityAdbClient", createRealLiabilityAdbClient({ fetchImpl, baseUrl, requestJson })],
    [
      "productCategoryClient",
      createRealProductCategoryClient({
        fetchImpl,
        baseUrl,
        requestJson,
        requestActionJson,
        requestText,
        requestActionWithBody,
      }),
    ],
    [
      "qdbGlMonthlyAnalysisClient",
      createRealQdbGlMonthlyAnalysisClient({
        fetchImpl,
        baseUrl,
        requestJson,
        requestActionJson,
        requestText,
        requestBlob,
        requestActionWithBody,
      }),
    ],
    [
      "balanceAnalysisClient",
      createRealBalanceAnalysisClient({
        fetchImpl,
        baseUrl,
        requestJson,
        requestActionJson,
        requestText,
        requestBlob,
      }),
    ],
  ] as Array<[string, Record<string, unknown>]>;
}

describe("real-mode ApiClient composition", () => {
  it("no method name is claimed by two domain factories", () => {
    const owners = new Map<string, string[]>();
    for (const [domain, methods] of buildRealClientBundles()) {
      for (const name of Object.keys(methods)) {
        owners.set(name, [...(owners.get(name) ?? []), domain]);
      }
    }

    const collisions = [...owners.entries()]
      .filter(([, domains]) => domains.length > 1)
      .map(([name, domains]) => `${name} <- ${domains.join(" | ")}`);

    // 失败信息必须点出争用的两个领域，否则定位成本高。
    expect(collisions).toEqual([]);
  });

  it("the composed client exposes every factory method and nothing else", () => {
    const bundles = buildRealClientBundles();
    const expected = new Set(bundles.flatMap(([, methods]) => Object.keys(methods)));

    const client = createApiClient({ mode: "real", baseUrl, fetchImpl });
    const actual = new Set(Object.keys(client).filter((key) => key !== "mode"));

    // 双向比较：既能抓到「重名导致某方法消失」，也能抓到「工厂漏进组合」。
    expect([...expected].filter((name) => !actual.has(name))).toEqual([]);
    expect([...actual].filter((name) => !expected.has(name))).toEqual([]);
  });
});
