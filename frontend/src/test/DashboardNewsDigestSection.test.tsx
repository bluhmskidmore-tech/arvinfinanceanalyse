import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

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
});
