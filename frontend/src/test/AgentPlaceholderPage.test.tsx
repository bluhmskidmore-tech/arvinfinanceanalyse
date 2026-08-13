import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

describe("/agent route when its frontend gate is closed", () => {
  beforeAll(async () => {
    // /agent 路由元素被懒加载的 ThemedRouteBoundary（antd 链）包裹；
    // 预热它，避免唯一用例的 5s findBy 超时为冷转换买单。
    await import("../app/ThemedRouteBoundary");
    // mock 客户端按需动态 import；本文件只有一个快速用例，预热避免
    // in-flight import 滞留到环境拆除（EnvironmentTeardownError）。
    await import("../api/mockApiClient");
    await import("../mocks/mockApiEnvelope");
    await import("../mocks/workbench");
  }, 30_000);
  it("renders the existing 404 status without requesting a placeholder snapshot", async () => {
    const getPlaceholderSnapshot = vi.fn();
    const client: ApiClient = {
      ...createApiClient({ mode: "mock" }),
      getPlaceholderSnapshot,
    };

    renderWorkbenchApp(["/agent"], { client });

    expect(await screen.findByTestId("workbench-not-found-page")).toHaveTextContent("/agent");
    expect(getPlaceholderSnapshot).not.toHaveBeenCalled();
    expect(screen.queryByTestId("workbench-readiness-banner")).not.toBeInTheDocument();
  });
});
