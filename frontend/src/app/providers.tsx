import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiClientProvider, type ApiClient } from "../api/clientContext";

type AppProvidersProps = {
  children: ReactNode;
  client?: ApiClient;
};

export function AppProviders({ children, client }: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            retry: 0,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ApiClientProvider>
  );
}
