import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { type ApiClient, createApiClient } from "../../../api/client";
import { useDashboardResearchCalendarQuery } from "./useDashboardResearchCalendarQuery";

function createWrapper() {
  return function Wrapper({ children }: { children: ReactNode }) {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          staleTime: 0,
          gcTime: 0,
          refetchOnWindowFocus: false,
        },
      },
    });

    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function buildClientWithResearchCalendar(
  getResearchCalendarEvents: ApiClient["getResearchCalendarEvents"],
): ApiClient {
  const base = createApiClient({ mode: "real" });
  return {
    ...base,
    getResearchCalendarEvents,
  };
}

describe("useDashboardResearchCalendarQuery", () => {
  it("derives the calendar window from the provided today value", async () => {
    const getResearchCalendarEvents = vi.fn<ApiClient["getResearchCalendarEvents"]>(async () => []);
    const client = buildClientWithResearchCalendar(getResearchCalendarEvents);

    const { result } = renderHook(
      () =>
        useDashboardResearchCalendarQuery({
          dataClient: client,
          getTodayIsoDate: () => "2026-05-23",
        }),
      {
        wrapper: createWrapper(),
      },
    );

    await waitFor(() => {
      expect(result.current.researchCalendarQuery.isSuccess).toBe(true);
    });

    expect(result.current.calendarStartDate).toBe("2026-05-16");
    expect(result.current.calendarEndDate).toBe("2026-06-06");
  });

  it("requests research calendar events with the derived date window and exposes query data", async () => {
    const events = [
      {
        id: "calendar-1",
        date: "2026-05-24",
        title: "Rates briefing",
        kind: "macro" as const,
        severity: "medium" as const,
      },
    ];
    const getResearchCalendarEvents = vi.fn<ApiClient["getResearchCalendarEvents"]>(async () => events);
    const client = buildClientWithResearchCalendar(getResearchCalendarEvents);

    const { result } = renderHook(
      () =>
        useDashboardResearchCalendarQuery({
          dataClient: client,
          getTodayIsoDate: () => "2026-05-23",
        }),
      {
        wrapper: createWrapper(),
      },
    );

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalledWith({
        startDate: "2026-05-16",
        endDate: "2026-06-06",
      });
      expect(result.current.researchCalendarQuery.data).toEqual(events);
    });
  });
});
