import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ComponentType, type ReactNode } from "react";

import { ApiClientProvider, type ApiClient } from "../api/clientContext";
import { workbenchTheme } from "../theme/theme";

type AppProvidersProps = {
  children: ReactNode;
  client?: ApiClient;
  loadAntdTheme?: boolean;
};

type AntdConfigProviderComponent = ComponentType<{
  children?: ReactNode;
  theme: typeof workbenchTheme;
}>;

let antdConfigProviderPromise: Promise<AntdConfigProviderComponent> | null = null;

function loadAntdConfigProvider() {
  antdConfigProviderPromise ??= import("antd").then(
    ({ ConfigProvider }) => ConfigProvider as AntdConfigProviderComponent,
  );
  return antdConfigProviderPromise;
}

export function AppProviders({
  children,
  client,
  loadAntdTheme = import.meta.env.MODE !== "test",
}: AppProvidersProps) {
  const [ConfigProvider, setConfigProvider] = useState<AntdConfigProviderComponent | null>(null);
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

  useEffect(() => {
    if (!loadAntdTheme) {
      return undefined;
    }

    let active = true;
    void loadAntdConfigProvider().then((Provider) => {
      if (active) {
        setConfigProvider(() => Provider);
      }
    });
    return () => {
      active = false;
    };
  }, [loadAntdTheme]);

  const content = (
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ApiClientProvider>
  );

  return ConfigProvider ? <ConfigProvider theme={workbenchTheme}>{content}</ConfigProvider> : content;
}
