import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import { useState, type ReactNode } from "react";

import { ApiClientProvider, type ApiClient } from "../api/client";
import { workbenchTheme } from "../theme/theme";

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
    <ConfigProvider theme={workbenchTheme}>
      <ApiClientProvider client={client}>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </ApiClientProvider>
    </ConfigProvider>
  );
}
