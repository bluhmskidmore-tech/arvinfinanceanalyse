import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { DashboardNewsDigestSection } from "../features/executive-dashboard/components/DashboardNewsDigestSection";

function renderSection(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <DashboardNewsDigestSection />
      </ApiClientProvider>
    </QueryClientProvider>,
  );
}

function renderSectionWithQueryClient(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <DashboardNewsDigestSection />
      </ApiClientProvider>
    </QueryClientProvider>,
  );

  return { ...result, queryClient };
}

describe("DashboardNewsDigestSection", () => {
  it("keeps filtered tabs populated in mock mode", async () => {
    renderSection(createApiClient({ mode: "mock" }));

    const section = await screen.findByTestId("dashboard-news-digest-section");
    await waitFor(() => {
      expect(within(section).getByRole("combobox")).toBeInTheDocument();
    });

    const tabs = within(section).getAllByRole("tab");
    fireEvent.click(tabs[1] as HTMLElement);

    await waitFor(() => {
      const combobox = within(section).getByRole("combobox");
      expect(within(combobox).getAllByRole("option")).toHaveLength(1);
    });
  });

  it("uses freshness-aware polling options for the news digest query", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn((options) => base.getChoiceNewsEvents(options));

    const { queryClient } = renderSectionWithQueryClient({
      ...base,
      getChoiceNewsEvents,
    });

    expect(await screen.findByTestId("dashboard-news-digest-section")).toBeInTheDocument();
    await waitFor(() => {
      expect(getChoiceNewsEvents).toHaveBeenCalledTimes(1);
    });

    const newsQuery = queryClient.getQueryCache().find({
      queryKey: ["dashboard", "choice-news-digest", "mock", "all"],
      exact: true,
    });

    expect(newsQuery?.observers[0]?.options.refetchIntervalInBackground).toBe(false);
    expect(
      typeof newsQuery?.observers[0]?.options.refetchInterval === "function"
        ? newsQuery.observers[0].options.refetchInterval(newsQuery)
        : newsQuery?.observers[0]?.options.refetchInterval,
    ).toBe(false);
  });
});
