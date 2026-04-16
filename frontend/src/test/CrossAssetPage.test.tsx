import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import CrossAssetPage from "../features/cross-asset/pages/CrossAssetPage";

function renderPage(client: ApiClient = createApiClient({ mode: "mock" })) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(
    <Wrapper>
      <CrossAssetPage />
    </Wrapper>,
  );
}

describe("CrossAssetPage", () => {
  it("renders the standardized shell and analytical linkage sections", async () => {
    renderPage();

    expect(await screen.findByTestId("cross-asset-page")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "跨资产驱动" })).toBeInTheDocument();
    expect(screen.getByText("环境概览")).toBeInTheDocument();
    expect(screen.getByText("判断、驱动与候选动作")).toBeInTheDocument();
    expect(screen.getByText("走势、事件与观察")).toBeInTheDocument();
    expect(screen.getByText("分析结果与输出")).toBeInTheDocument();
    expect(screen.getByText(/完整宏观序列仍在/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "市场数据" })).toBeInTheDocument();

    expect(screen.getByTestId("cross-asset-kpi-band")).toBeInTheDocument();
    expect(screen.getByText("市场判断")).toBeInTheDocument();
    expect(screen.getByText("驱动拆解")).toBeInTheDocument();
    expect(screen.getByText("跨资产走势")).toBeInTheDocument();
    expect(screen.getByText("跨资产传导链")).toBeInTheDocument();
    expect(screen.getByText("估值 / 分位热图")).toBeInTheDocument();

    expect(screen.getByText("宏观 — 债券联动（评分与组合影响）")).toBeInTheDocument();
  });
});
